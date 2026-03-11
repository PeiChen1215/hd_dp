from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    # 新增字段
    type: Optional[str] = Field(default="WORK", description="事件类型: WORK/LIFE/STUDY")
    priority: Optional[int] = Field(default=2, description="优先级: 1(低)/2(中)/3(高)")


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    # 新增字段（更新时可选）
    type: Optional[str] = Field(default=None, description="事件类型: WORK/LIFE/STUDY")
    priority: Optional[int] = Field(default=None, description="优先级: 1(低)/2(中)/3(高)")


class EventOut(EventBase):
    id: str
    user_id: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    @classmethod
    def model_validate(cls, obj):
        # 处理 SQLAlchemy 模型，将 UUID 转为字符串
        if hasattr(obj, '__table__') or hasattr(obj, '__dict__'):
            # 直接从 SQLAlchemy 对象获取所有字段
            data = {
                'id': str(obj.id) if obj.id else None,
                'user_id': str(obj.user_id) if obj.user_id else None,
                'title': obj.title,
                'description': obj.description,
                'start_time': obj.start_time,
                'end_time': obj.end_time,
                'location': obj.location,
                'status': obj.status,
                'type': getattr(obj, 'type', 'WORK'),
                'priority': getattr(obj, 'priority', 2),
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
            }
            return cls(**data)
        return super().model_validate(obj)

    class Config:
        from_attributes = True


class EventList(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    size: int
