from pydantic import BaseModel
from typing import List, Optional


class ChatRequest(BaseModel):
    query: str


class SourceItem(BaseModel):
    type: str
    id: str
    title: Optional[str]
    start_time: Optional[str]


class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[SourceItem]] = None
