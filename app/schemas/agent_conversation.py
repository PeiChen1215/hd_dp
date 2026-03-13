"""
Agent 对话历史相关的 Pydantic Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AgentConversationBase(BaseModel):
    """对话历史基础模型"""
    role: str = Field(..., description="角色：user 或 assistant")
    content: str = Field(..., description="对话内容")


class AgentConversationCreate(AgentConversationBase):
    """创建对话历史"""
    pass


class AgentConversationOut(AgentConversationBase):
    """对话历史输出"""
    id: str = Field(..., description="对话记录ID")
    user_id: str = Field(..., description="用户ID")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class AgentConversationList(BaseModel):
    """对话历史列表"""
    items: List[AgentConversationOut]
    total: int = Field(..., description="总条数")


class AgentConversationClearResponse(BaseModel):
    """清空对话历史响应"""
    status: str = Field(..., description="状态：success")
    message: str = Field(..., description="提示信息")
    deleted_count: int = Field(..., description="删除的记录数")
