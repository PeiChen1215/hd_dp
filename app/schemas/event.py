from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None


class EventOut(EventBase):
    id: str
    user_id: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    @classmethod
    def model_validate(cls, obj):
        # 处理 SQLAlchemy 模型，将 UUID 转为字符串
        if hasattr(obj, '__dict__'):
            data = obj.__dict__.copy()
            # 转换 UUID 字段为字符串
            for field in ['id', 'user_id']:
                if hasattr(obj, field) and getattr(obj, field) is not None:
                    val = getattr(obj, field)
                    if isinstance(val, UUID):
                        data[field] = str(val)
            # 复制时间字段
            for field in ['created_at', 'updated_at', 'start_time', 'end_time']:
                if hasattr(obj, field):
                    data[field] = getattr(obj, field)
            return cls(**data)
        return super().model_validate(obj)

    class Config:
        from_attributes = True


class EventList(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    size: int
