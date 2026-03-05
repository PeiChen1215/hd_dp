from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime

from app.models.event import Event
from app import schemas


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
    db_event = Event(
        user_id=UUID(user_id),
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        location=event_in.location,
        status="pending"  # 默认状态
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    
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
    
    await db.commit()
    await db.refresh(event)
    
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
    await db.commit()
    await db.refresh(event)
    
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
    
    await db.delete(event)
    await db.commit()
    
    return True
