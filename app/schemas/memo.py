from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


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

    class Config:
        from_attributes = True


class MemoList(BaseModel):
    items: list[MemoOut]
    total: int
    page: int
    size: int
