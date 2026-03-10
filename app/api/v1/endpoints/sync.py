"""
离线同步 API 模块
支持增量同步、冲突解决、多端数据一致性
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from typing import Optional, List
from datetime import datetime, timezone
from uuid import uuid4, UUID
import json

from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.event import Event
from app.models.memo import Memo
from app.models.sync_record import SyncRecord
from app import schemas

router = APIRouter()


class SyncConflictError(Exception):
    """同步冲突异常"""
    pass


@router.get("/pull")
async def sync_pull(
    since: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    增量拉取：获取服务器上自 `since` 时间戳之后的变更
    
    Args:
        since: 上次同步时间戳（ISO格式），为空则拉取全量
        limit: 单次最大返回条数
        
    Returns:
        {
            "items": [...],      # 变更记录列表
            "nextCursor": "...", # 下一页游标，为空表示没有更多
            "hasMore": false,
            "serverTime": "..."  # 服务器当前时间，用于下次拉取
        }
    """
    user_id = user.id
    
    # 构建基础查询
    query = select(SyncRecord).where(
        SyncRecord.user_id == user_id
    ).order_by(SyncRecord.server_modified_at.asc())
    
    # 时间戳过滤
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.where(SyncRecord.server_modified_at > since_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid since timestamp")
    
    # 限制条数
    query = query.limit(limit + 1)  # 多查一条判断是否还有数据
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    has_more = len(records) > limit
    records = records[:limit]  # 只取 limit 条
    
    # 构建响应
    items = []
    for record in records:
        item = {
            "server_id": str(record.entity_id),
            "client_id": record.client_id,
            "entity_type": record.entity_type,
            "action": record.action,  # create/update/delete
            "payload": record.payload,
            "client_modified_at": record.client_modified_at.isoformat() if record.client_modified_at else None,
            "server_modified_at": record.server_modified_at.isoformat()
        }
        items.append(item)
    
    # 计算 nextCursor
    next_cursor = None
    if has_more and records:
        next_cursor = records[-1].server_modified_at.isoformat()
    
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "server_time": datetime.now(timezone.utc).isoformat()
    }


@router.post("/push")
async def sync_push(
    payload: schemas.SyncPushRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    增量推送：将客户端的变更推送到服务器
    
    Args:
        payload: {
            "items": [
                {
                    "clientId": "123",           # 本地ID
                    "serverId": null,            # 云端ID（新数据为空）
                    "entityType": "event",       # event/memo
                    "action": "create",          # create/update/delete
                    "payload": {...},            # 实体数据
                    "modifiedAt": "2026-03-08..." # 客户端修改时间
                }
            ],
            "lastSyncedAt": "2026-03-01..."      # 上次同步时间
        }
        
    Returns:
        {
            "results": [
                {
                    "clientId": "123",
                    "serverId": "uuid",
                    "status": "success",      # success/conflict/error
                    "message": "...",
                    "serverModifiedAt": "..."
                }
            ],
            "conflicts": [...]  # 需要客户端解决的冲突列表
        }
    """
    user_id = user.id
    results = []
    conflicts = []
    
    for item in payload.items:
        try:
            result = await _process_sync_item(
                db=db,
                user_id=user_id,
                item=item,
                last_synced_at=payload.last_synced_at
            )
            results.append(result)
            
            if result.get("status") == "conflict":
                conflicts.append(result)
                
        except Exception as e:
            results.append({
                "client_id": item.client_id,
                "server_id": item.server_id,
                "status": "error",
                "message": str(e),
                "server_modified_at": datetime.now(timezone.utc).isoformat()
            })
    
    await db.commit()
    
    return {
        "results": results,
        "conflicts": conflicts,
        "serverTime": datetime.now(timezone.utc).isoformat()
    }


async def _process_sync_item(
    db: AsyncSession,
    user_id: UUID,
    item: schemas.SyncItemPush,
    last_synced_at: Optional[str]
) -> dict:
    """
    处理单个同步项
    
    冲突检测策略：
    1. 如果服务端没有该记录 -> 直接应用客户端变更
    2. 如果服务端有记录，且服务端修改时间 <= lastSyncedAt -> 无冲突，应用变更
    3. 如果服务端有记录，且服务端修改时间 > lastSyncedAt -> 冲突！需要解决
    """
    now = datetime.now(timezone.utc)
    client_modified_at = datetime.fromisoformat(
        item.modified_at.replace('Z', '+00:00')
    )
    
    # 1. 尝试获取已有记录
    existing_record = None
    existing_entity = None
    
    if item.server_id:
        # 通过 serverId 查找
        if item.entity_type == "event":
            result = await db.execute(
                select(Event).where(
                    and_(Event.id == UUID(item.server_id), Event.user_id == user_id)
                )
            )
            existing_entity = result.scalar_one_or_none()
        else:  # memo
            result = await db.execute(
                select(Memo).where(
                    and_(Memo.id == UUID(item.server_id), Memo.user_id == user_id)
                )
            )
            existing_entity = result.scalar_one_or_none()
    
    if not existing_entity and item.client_id:
        # 尝试通过 clientId 查找映射
        result = await db.execute(
            select(SyncRecord).where(
                and_(
                    SyncRecord.user_id == user_id,
                    SyncRecord.entity_type == item.entity_type,
                    SyncRecord.client_id == item.client_id
                )
            ).order_by(desc(SyncRecord.server_modified_at))
        )
        existing_record = result.scalar_one_or_none()
        if existing_record:
            item.server_id = str(existing_record.entity_id)
            # 重新获取实体
            if item.entity_type == "event":
                result = await db.execute(
                    select(Event).where(Event.id == existing_record.entity_id)
                )
                existing_entity = result.scalar_one_or_none()
            else:
                result = await db.execute(
                    select(Memo).where(Memo.id == existing_record.entity_id)
                )
                existing_entity = result.scalar_one_or_none()
    
    # 2. 冲突检测
    if existing_entity and last_synced_at:
        last_sync_dt = datetime.fromisoformat(last_synced_at.replace('Z', '+00:00'))
        
        # 检查服务端是否有新变更
        result = await db.execute(
            select(SyncRecord).where(
                and_(
                    SyncRecord.entity_id == existing_entity.id,
                    SyncRecord.server_modified_at > last_sync_dt
                )
            ).order_by(desc(SyncRecord.server_modified_at))
        )
        server_change = result.scalar_one_or_none()
        
        if server_change and server_change.action != "delete":
            # 冲突！服务器和客户端都修改了
            return {
                "client_id": item.client_id,
                "server_id": str(existing_entity.id),
                "status": "conflict",
                "message": "Server has newer version",
                "server_data": _entity_to_dict(existing_entity, item.entity_type),
                "client_modified_at": item.modified_at,
                "server_modified_at": server_change.server_modified_at.isoformat()
            }
    
    # 3. 应用变更
    if item.action == "delete":
        if existing_entity:
            await db.delete(existing_entity)
        entity_id = UUID(item.server_id) if item.server_id else uuid4()
    else:
        # create or update
        if item.entity_type == "event":
            entity_id = await _apply_event_change(db, user_id, item, existing_entity)
        else:
            entity_id = await _apply_memo_change(db, user_id, item, existing_entity)
    
    # 4. 记录同步日志
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=user_id,
        entity_type=item.entity_type,
        entity_id=entity_id,
        client_id=str(item.client_id) if item.client_id else None,
        action=item.action,
        payload=item.payload if item.payload else None,
        client_modified_at=client_modified_at,
        server_modified_at=now
    )
    db.add(sync_record)
    
    return {
        "client_id": item.client_id,
        "server_id": str(entity_id),
        "status": "success",
        "message": f"{item.action} {item.entity_type} succeeded",
        "server_modified_at": now.isoformat()
    }


async def _apply_event_change(
    db: AsyncSession,
    user_id: UUID,
    item: schemas.SyncItemPush,
    existing: Optional[Event]
) -> UUID:
    """应用事件变更"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    payload = item.payload or {}
    
    if existing:
        # 更新
        existing.title = payload.get("title", existing.title)
        existing.description = payload.get("description", existing.description)
        if payload.get("start_time"):
            existing.start_time = datetime.fromisoformat(payload["start_time"].replace('Z', '+00:00'))
        if payload.get("end_time"):
            existing.end_time = datetime.fromisoformat(payload["end_time"].replace('Z', '+00:00'))
        existing.location = payload.get("location", existing.location)
        existing.status = payload.get("status", existing.status)
        return existing.id
    else:
        # 新建
        event_id = uuid4()
        new_event = Event(
            id=event_id,
            user_id=user_id,
            title=payload.get("title", "Untitled"),
            description=payload.get("description"),
            start_time=datetime.fromisoformat(payload["start_time"].replace('Z', '+00:00')) if payload.get("start_time") else now,
            end_time=datetime.fromisoformat(payload["end_time"].replace('Z', '+00:00')) if payload.get("end_time") else None,
            location=payload.get("location"),
            status=payload.get("status", "pending")
        )
        db.add(new_event)
        return event_id


async def _apply_memo_change(
    db: AsyncSession,
    user_id: UUID,
    item: schemas.SyncItemPush,
    existing: Optional[Memo]
) -> UUID:
    """应用备忘录变更"""
    payload = item.payload or {}
    
    if existing:
        existing.content = payload.get("content", existing.content)
        existing.tags = payload.get("tags", existing.tags)
        return existing.id
    else:
        memo_id = uuid4()
        new_memo = Memo(
            id=memo_id,
            user_id=user_id,
            content=payload.get("content", ""),
            tags=payload.get("tags", [])
        )
        db.add(new_memo)
        return memo_id


def _entity_to_dict(entity, entity_type: str) -> dict:
    """将实体转换为字典"""
    if entity_type == "event":
        return {
            "id": str(entity.id),
            "title": entity.title,
            "description": entity.description,
            "start_time": entity.start_time.isoformat() if entity.start_time else None,
            "end_time": entity.end_time.isoformat() if entity.end_time else None,
            "location": entity.location,
            "status": entity.status,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None
        }
    else:  # memo
        return {
            "id": str(entity.id),
            "content": entity.content,
            "tags": entity.tags,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None
        }


@router.post("/resolve-conflict")
async def resolve_conflict(
    resolution: schemas.ConflictResolution,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    手动解决冲突
    
    Args:
        resolution: {
            "clientId": "123",
            "serverId": "uuid",
            "entityType": "event",
            "resolution": "client" | "server" | "merge",
            "mergedData": {...}  # merge 时使用
        }
    """
    user_id = user.id
    
    if resolution.resolution == "server":
        # 使用服务器版本，无需操作
        return {"status": "ok", "message": "Kept server version"}
    
    elif resolution.resolution == "client":
        # 强制使用客户端版本，重新推送
        # 这里删除服务器记录，让下次 push 创建新的
        if resolution.entity_type == "event":
            result = await db.execute(
                select(Event).where(
                    and_(Event.id == UUID(resolution.server_id), Event.user_id == user_id)
                )
            )
            entity = result.scalar_one_or_none()
        else:
            result = await db.execute(
                select(Memo).where(
                    and_(Memo.id == UUID(resolution.server_id), Memo.user_id == user_id)
                )
            )
            entity = result.scalar_one_or_none()
        
        if entity:
            await db.delete(entity)
            await db.commit()
        
        return {"status": "ok", "message": "Removed server version, please re-push"}
    
    elif resolution.resolution == "merge":
        # 合并数据，更新服务器版本
        # TODO: 实现合并逻辑
        return {"status": "pending", "message": "Merge not fully implemented"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution type")


@router.post("/full-sync")
async def full_sync(
    request: schemas.FullSyncRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    全量同步（首次安装或数据恢复时使用）
    
    客户端上传所有本地数据，服务器进行合并
    """
    user_id = user.id
    
    # 获取服务器全量数据
    events_result = await db.execute(
        select(Event).where(Event.user_id == user_id)
    )
    events = events_result.scalars().all()
    
    memos_result = await db.execute(
        select(Memo).where(Memo.user_id == user_id)
    )
    memos = memos_result.scalars().all()
    
    server_data = {
        "events": [_entity_to_dict(e, "event") for e in events],
        "memos": [_entity_to_dict(m, "memo") for m in memos]
    }
    
    # 处理客户端上传的数据
    push_results = []
    if request.items:
        push_response = await sync_push(
            payload=schemas.SyncPushRequest(
                items=request.items,
                last_synced_at=None
            ),
            db=db,
            user=user
        )
        push_results = push_response.get("results", [])
    
    return {
        "server_data": server_data,
        "push_results": push_results,
        "server_time": datetime.now(timezone.utc).isoformat()
    }
