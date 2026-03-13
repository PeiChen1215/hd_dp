"""
Agent 对话历史模型
存储用户与万机 Agent 的多轮对话记录
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Text, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.base import Base


class AgentConversation(Base):
    """Agent 对话历史表"""
    __tablename__ = "agent_conversations"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' 或 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<AgentConversation {self.role} {self.created_at}>"
