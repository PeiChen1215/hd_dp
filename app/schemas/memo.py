from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from uuid import UUID


class MemoBase(BaseModel):
    content: str
    tags: Optional[List[str]] = None


class MemoCreate(MemoBase):
    pass


class MemoUpdate(BaseModel):
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class MemoOut(MemoBase):
    id: str
    user_id: str
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
            for field in ['created_at', 'updated_at']:
                if hasattr(obj, field):
                    data[field] = getattr(obj, field)
            return cls(**data)
        return super().model_validate(obj)

    class Config:
        from_attributes = True


class MemoList(BaseModel):
    items: list[MemoOut]
    total: int
    page: int
    size: int
