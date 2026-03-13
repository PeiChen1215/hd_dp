"""
Agent 对话历史 API
提供对话历史的查询、删除功能
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete, func

from app.schemas.agent_conversation import (
    AgentConversationOut,
    AgentConversationList,
    AgentConversationClearResponse,
)
from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.agent_conversation import AgentConversation

router = APIRouter()


@router.get("/conversations", response_model=AgentConversationList)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的 Agent 对话历史
    
    按时间倒序返回，最新的对话在前面
    """
    # 查询总数
    count_result = await db.execute(
        select(func.count()).where(AgentConversation.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    # 查询记录
    result = await db.execute(
        select(AgentConversation)
        .where(AgentConversation.user_id == current_user.id)
        .order_by(desc(AgentConversation.created_at))
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())
    
    return AgentConversationList(
        items=[
            AgentConversationOut(
                id=str(item.id),
                user_id=str(item.user_id),
                role=item.role,
                content=item.content,
                created_at=item.created_at
            )
            for item in items
        ],
        total=total
    )


@router.delete("/conversations", response_model=AgentConversationClearResponse)
async def clear_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    清空当前用户的 Agent 对话历史
    
    返回删除的记录数量
    """
    # 先查询数量
    count_result = await db.execute(
        select(func.count()).where(AgentConversation.user_id == current_user.id)
    )
    count = count_result.scalar()
    
    # 删除记录
    await db.execute(
        delete(AgentConversation).where(AgentConversation.user_id == current_user.id)
    )
    await db.commit()
    
    return AgentConversationClearResponse(
        status="success",
        message=f"已清空 {count} 条对话记录",
        deleted_count=count
    )
