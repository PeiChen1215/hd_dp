from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID


class UserCreate(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    @classmethod
    def model_validate(cls, obj):
        # 处理 SQLAlchemy 模型，将 UUID 转为字符串
        if hasattr(obj, '__dict__'):
            data = obj.__dict__.copy()
            if hasattr(obj, 'id') and obj.id is not None:
                val = obj.id
                if isinstance(val, UUID):
                    data['id'] = str(val)
            if hasattr(obj, 'created_at'):
                data['created_at'] = obj.created_at
            if hasattr(obj, 'updated_at'):
                data['updated_at'] = obj.updated_at
            return cls(**data)
        return super().model_validate(obj)

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str | None = None
