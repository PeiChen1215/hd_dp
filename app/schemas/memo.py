from pydantic import BaseModel
from typing import Optional, List


class MemoBase(BaseModel):
    content: str
    tags: Optional[List[str]] = None


class MemoCreate(MemoBase):
    pass


class MemoOut(MemoBase):
    id: str

    class Config:
        orm_mode = True
