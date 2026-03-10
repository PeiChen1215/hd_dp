import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class SyncRecord(Base):
    """
    同步变更记录表
    记录每个实体的变更历史，用于增量同步
    """
    __tablename__ = "sync_records"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 实体信息
    entity_type = Column(String(20), nullable=False)  # 'event' 或 'memo'
    entity_id = Column(PG_UUID(as_uuid=True), nullable=False)  # 对应的 event/memo id
    client_id = Column(String(50), nullable=True)  # 客户端本地ID（如 "123"）
    
    # 变更信息
    action = Column(String(10), nullable=False)  # 'create', 'update', 'delete'
    
    # 变更内容（JSON格式，delete时可为null）
    payload = Column(JSONB, nullable=True)
    
    # 客户端时间戳（用于冲突检测）
    client_modified_at = Column(DateTime(timezone=True), nullable=False)
    
    # 服务端时间戳（作为同步游标）
    server_modified_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    
    # 软删除标记
    is_deleted = Column(String(1), server_default='0', nullable=False)
    
    # 索引优化
    __table_args__ = (
        Index('idx_sync_user_time', 'user_id', 'server_modified_at'),
        Index('idx_sync_entity', 'entity_type', 'entity_id'),
        Index('idx_sync_client_id', 'user_id', 'entity_type', 'client_id'),
    )
