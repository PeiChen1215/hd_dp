from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.event import Event
from app.models.sync_record import SyncRecord
from app import schemas
from app.core.websocket import notify_data_change


async def get_event_by_id(db: AsyncSession, event_id: str, user_id: str) -> Event | None:
    """获取指定用户的单个日程"""
    result = await db.execute(
        select(Event).where(
            and_(Event.id == UUID(event_id), Event.user_id == UUID(user_id))
        )
    )
    return result.scalar_one_or_none()


async def list_events(
    db: AsyncSession,
    user_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    size: int = 20
) -> tuple[list[Event], int]:
    """
    获取日程列表（支持时间范围过滤和分页）
    
    Returns:
        (日程列表, 总数) 元组
    """
    # 构建基础查询
    query = select(Event).where(Event.user_id == UUID(user_id))
    count_query = select(func.count()).select_from(Event).where(Event.user_id == UUID(user_id))
    
    # 时间范围过滤
    if start_date:
        query = query.where(Event.start_time >= start_date)
        count_query = count_query.where(Event.start_time >= start_date)
    if end_date:
        query = query.where(Event.start_time <= end_date)
        count_query = count_query.where(Event.start_time <= end_date)
    
    # 排序：按开始时间升序
    query = query.order_by(Event.start_time.asc())
    
    # 分页
    query = query.offset((page - 1) * size).limit(size)
    
    # 执行查询
    result = await db.execute(query)
    events = result.scalars().all()
    
    # 获取总数
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return list(events), total


async def create_event(
    db: AsyncSession, user_id: str, event_in: schemas.EventCreate
) -> Event:
    """
    创建新日程
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        event_in: 日程创建数据
        
    Returns:
        创建的日程对象
    """
    now = datetime.now(timezone.utc)
    db_event = Event(
        user_id=UUID(user_id),
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        location=event_in.location,
        status="pending",  # 默认状态
        type=event_in.type or "WORK",
        priority=event_in.priority or 2
    )
    db.add(db_event)
    await db.flush()  # 先 flush 获取 event.id
    
    # 创建同步记录（用于增量同步）
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="event",
        entity_id=db_event.id,
        client_id=None,  # HTTP 直接修改没有 client_id
        action="create",
        payload={
            "title": event_in.title,
            "description": event_in.description,
            "start_time": event_in.start_time.isoformat() if event_in.start_time else None,
            "end_time": event_in.end_time.isoformat() if event_in.end_time else None,
            "location": event_in.location,
            "status": "pending",
            "type": event_in.type or "WORK",
            "priority": event_in.priority or 2
        },
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    await db.refresh(db_event)
    
    # WebSocket 实时推送（异步，不阻塞）
    notify_data_change(
        user_id=user_id,
        change_type="created",
        entity_type="event",
        data=_event_to_dict(db_event),
        require_ack=True
    )
    
    return db_event


async def update_event(
    db: AsyncSession,
    event_id: str,
    user_id: str,
    event_in: schemas.EventUpdate
) -> Event | None:
    """
    更新日程
    
    Args:
        db: 数据库会话
        event_id: 日程ID
        user_id: 用户ID（用于权限验证）
        event_in: 更新的数据
        
    Returns:
        更新后的日程对象，不存在返回 None
    """
    event = await get_event_by_id(db, event_id, user_id)
    if not event:
        return None
    
    # 更新字段
    update_data = event_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)
    
    await db.flush()
    
    # 创建同步记录（用于增量同步）
    now = datetime.now(timezone.utc)
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="event",
        entity_id=event.id,
        client_id=None,
        action="update",
        payload={
            "id": str(event.id),
            **{k: v.isoformat() if isinstance(v, datetime) else v 
               for k, v in update_data.items()}
        },
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    await db.refresh(event)
    
    # WebSocket 实时推送
    notify_data_change(
        user_id=user_id,
        change_type="updated",
        entity_type="event",
        data=_event_to_dict(event),
        require_ack=True
    )
    
    return event


async def update_event_status(
    db: AsyncSession,
    event_id: str,
    user_id: str,
    status: str
) -> Event | None:
    """
    更新日程状态
    
    Args:
        status: pending, completed, cancelled
    """
    event = await get_event_by_id(db, event_id, user_id)
    if not event:
        return None
    
    event.status = status
    await db.flush()
    
    # 创建同步记录（用于增量同步）
    now = datetime.now(timezone.utc)
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="event",
        entity_id=event.id,
        client_id=None,
        action="update",
        payload={
            "id": str(event.id),
            "status": status
        },
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    await db.refresh(event)
    
    # WebSocket 实时推送
    notify_data_change(
        user_id=user_id,
        change_type="updated",
        entity_type="event",
        data=_event_to_dict(event),
        require_ack=True
    )
    
    return event


async def delete_event(db: AsyncSession, event_id: str, user_id: str) -> bool:
    """
    删除日程
    
    Returns:
        是否成功删除
    """
    event = await get_event_by_id(db, event_id, user_id)
    if not event:
        return False
    
    # 先获取数据用于通知
    event_data = _event_to_dict(event)
    event_uuid = event.id  # 保存 ID 用于同步记录
    
    await db.delete(event)
    await db.flush()
    
    # 创建同步记录（用于增量同步）
    now = datetime.now(timezone.utc)
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="event",
        entity_id=event_uuid,
        client_id=None,
        action="delete",
        payload={"id": str(event_uuid)},  # 删除时只存 ID
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    
    # WebSocket 实时推送
    notify_data_change(
        user_id=user_id,
        change_type="deleted",
        entity_type="event",
        data=event_data,
        require_ack=True
    )
    
    return True


def _event_to_dict(event: Event) -> dict:
    """将 Event 对象转换为字典（用于 WebSocket 推送）"""
    return {
        "id": str(event.id),
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time.isoformat() if event.start_time else None,
        "end_time": event.end_time.isoformat() if event.end_time else None,
        "location": event.location,
        "status": event.status,
        "type": event.type,  # 新增
        "priority": event.priority,  # 新增
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None
    }
