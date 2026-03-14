from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID, uuid4
from datetime import datetime

from app.models.memo import Memo
from app.models.sync_record import SyncRecord
from app import schemas
from app.core.websocket import notify_data_change
from app.core.timezone import get_beijing_time


async def get_memo_by_id(db: AsyncSession, memo_id: str, user_id: str) -> Memo | None:
    """获取指定用户的单个备忘录"""
    result = await db.execute(
        select(Memo).where(
            and_(Memo.id == UUID(memo_id), Memo.user_id == UUID(user_id))
        )
    )
    return result.scalar_one_or_none()


async def list_memos(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    size: int = 20
) -> tuple[list[Memo], int]:
    """
    获取备忘录列表（支持分页）
    
    Returns:
        (备忘录列表, 总数) 元组
    """
    # 构建查询
    query = select(Memo).where(Memo.user_id == UUID(user_id))
    count_query = select(func.count()).select_from(Memo).where(Memo.user_id == UUID(user_id))
    
    # 排序：按更新时间降序
    query = query.order_by(Memo.updated_at.desc())
    
    # 分页
    query = query.offset((page - 1) * size).limit(size)
    
    # 执行查询
    result = await db.execute(query)
    memos = result.scalars().all()
    
    # 获取总数
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return list(memos), total


async def create_memo(
    db: AsyncSession,
    user_id: str,
    memo_in: schemas.MemoCreate
) -> Memo:
    """
    创建新备忘录
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        memo_in: 备忘录创建数据
        
    Returns:
        创建的备忘录对象
    """
    now = get_beijing_time()
    db_memo = Memo(
        user_id=UUID(user_id),
        content=memo_in.content,
        tags=memo_in.tags or []
    )
    db.add(db_memo)
    await db.flush()  # 先 flush 获取 memo.id
    
    # 创建同步记录（用于增量同步）
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="memo",
        entity_id=db_memo.id,
        client_id=None,
        action="create",
        payload={
            "id": str(db_memo.id),
            "content": memo_in.content,
            "tags": memo_in.tags or []
        },
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    await db.refresh(db_memo)
    
    # WebSocket 实时推送
    notify_data_change(
        user_id=user_id,
        change_type="created",
        entity_type="memo",
        data=_memo_to_dict(db_memo),
        require_ack=True
    )
    
    return db_memo


async def update_memo(
    db: AsyncSession,
    memo_id: str,
    user_id: str,
    memo_in: schemas.MemoUpdate
) -> Memo | None:
    """
    更新备忘录
    
    Args:
        db: 数据库会话
        memo_id: 备忘录ID
        user_id: 用户ID（用于权限验证）
        memo_in: 更新的数据
        
    Returns:
        更新后的备忘录对象，不存在返回 None
    """
    memo = await get_memo_by_id(db, memo_id, user_id)
    if not memo:
        return None
    
    # 更新字段
    update_data = memo_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(memo, field, value)
    
    await db.flush()
    
    # 创建同步记录（用于增量同步）
    now = get_beijing_time()
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="memo",
        entity_id=memo.id,
        client_id=None,
        action="update",
        payload={
            "id": str(memo.id),
            **update_data
        },
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    await db.refresh(memo)
    
    # WebSocket 实时推送
    notify_data_change(
        user_id=user_id,
        change_type="updated",
        entity_type="memo",
        data=_memo_to_dict(memo),
        require_ack=True
    )
    
    return memo


async def delete_memo(db: AsyncSession, memo_id: str, user_id: str) -> bool:
    """
    删除备忘录
    
    Returns:
        是否成功删除
    """
    memo = await get_memo_by_id(db, memo_id, user_id)
    if not memo:
        return False
    
    # 先获取数据用于通知
    memo_data = _memo_to_dict(memo)
    memo_uuid = memo.id
    
    await db.delete(memo)
    await db.flush()
    
    # 创建同步记录（用于增量同步）
    now = get_beijing_time()
    sync_record = SyncRecord(
        id=uuid4(),
        user_id=UUID(user_id),
        entity_type="memo",
        entity_id=memo_uuid,
        client_id=None,
        action="delete",
        payload={"id": str(memo_uuid)},
        client_modified_at=now,
        server_modified_at=now
    )
    db.add(sync_record)
    await db.commit()
    
    # WebSocket 实时推送
    notify_data_change(
        user_id=user_id,
        change_type="deleted",
        entity_type="memo",
        data=memo_data,
        require_ack=True
    )
    
    return True


def _memo_to_dict(memo: Memo) -> dict:
    """将 Memo 对象转换为字典（用于 WebSocket 推送）"""
    return {
        "id": str(memo.id),
        "user_id": str(memo.user_id),
        "content": memo.content,
        "tags": memo.tags or [],
        "created_at": memo.created_at.isoformat() if memo.created_at else None,
        "updated_at": memo.updated_at.isoformat() if memo.updated_at else None
    }
