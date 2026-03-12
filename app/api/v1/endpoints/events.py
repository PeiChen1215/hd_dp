from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app import schemas
from app.services import event_service
from app.utils.model_converter import event_to_dict

router = APIRouter()


@router.get("/")
async def list_events(
    start_date: datetime | None = Query(None, description="开始日期过滤 (ISO 8601)"),
    end_date: datetime | None = Query(None, description="结束日期过滤 (ISO 8601)"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的日程列表
    
    支持时间范围过滤和分页
    """
    events, total = await event_service.list_events(
        db=db,
        user_id=str(current_user.id),
        start_date=start_date,
        end_date=end_date,
        page=page,
        size=size
    )
    
    # 转换所有事件为字典
    event_dicts = [event_to_dict(e) for e in events]
    
    return {
        "items": event_dicts,
        "total": total,
        "page": page,
        "size": size
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: schemas.EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新日程
    
    - **title**: 标题（必填）
    - **description**: 描述（可选）
    - **start_time**: 开始时间（ISO 8601，必填）
    - **end_time**: 结束时间（可选）
    - **location**: 地点（可选）
    """
    event = await event_service.create_event(
        db=db,
        user_id=str(current_user.id),
        event_in=payload
    )
    return event_to_dict(event)


@router.get("/{serverId}")
async def get_event(
    serverId: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取单个日程详情
    """
    event = await event_service.get_event_by_id(
        db=db,
        event_id=serverId,
        user_id=str(current_user.id)
    )
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return event_to_dict(event)


@router.put("/{serverId}")
async def update_event(
    serverId: str,
    payload: schemas.EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新日程（全量或部分更新）
    """
    event = await event_service.update_event(
        db=db,
        event_id=serverId,
        user_id=str(current_user.id),
        event_in=payload
    )
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return event_to_dict(event)


class StatusUpdateRequest:
    """状态更新请求模型"""
    def __init__(self, status: str):
        self.status = status


@router.patch("/{serverId}/status")
async def update_event_status(
    serverId: str,
    payload: dict,  # 接收 JSON body
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新日程状态
    
    请求体: {"status": "pending|completed|cancelled"}
    """
    status = payload.get("status")
    if not status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'status' field in request body"
        )
    
    # 验证状态值
    valid_statuses = ["pending", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    event = await event_service.update_event_status(
        db=db,
        event_id=serverId,
        user_id=str(current_user.id),
        status=status
    )
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return event_to_dict(event)


@router.delete("/{serverId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    serverId: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除日程
    """
    success = await event_service.delete_event(
        db=db,
        event_id=serverId,
        user_id=str(current_user.id)
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return None
