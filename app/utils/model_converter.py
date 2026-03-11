"""
SQLAlchemy 模型到 Pydantic 模型的转换工具
处理 UUID、datetime 等类型的自动转换
"""

from uuid import UUID
from datetime import datetime
from typing import Any, Optional


def sqlalchemy_to_dict(obj: Any, fields: list[str]) -> dict:
    """
    将 SQLAlchemy 模型转换为字典
    
    Args:
        obj: SQLAlchemy 模型实例
        fields: 需要转换的字段列表
        
    Returns:
        转换后的字典
    """
    result = {}
    for field in fields:
        if hasattr(obj, field):
            val = getattr(obj, field)
            # 处理 UUID
            if isinstance(val, UUID):
                result[field] = str(val)
            # 处理 datetime（保持原样，JSON 序列化时会处理）
            elif isinstance(val, datetime):
                result[field] = val
            else:
                result[field] = val
    return result


def event_to_dict(event) -> dict:
    """转换 Event 模型为字典"""
    return sqlalchemy_to_dict(event, [
        "id", "user_id", "title", "description", 
        "start_time", "end_time", "location", 
        "status", "type", "priority",  # 新增字段
        "created_at", "updated_at"
    ])


def memo_to_dict(memo) -> dict:
    """转换 Memo 模型为字典"""
    return sqlalchemy_to_dict(memo, [
        "id", "user_id", "content", "tags",
        "created_at", "updated_at"
    ])


def user_to_dict(user) -> dict:
    """转换 User 模型为字典"""
    return sqlalchemy_to_dict(user, [
        "id", "username", "created_at", "updated_at"
    ])
