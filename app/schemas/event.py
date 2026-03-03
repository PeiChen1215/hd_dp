from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None


class EventCreate(EventBase):
    pass


class EventOut(EventBase):
    id: str
    status: str

    class Config:
        orm_mode = True
