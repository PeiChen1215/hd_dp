from pydantic import BaseModel
from typing import List, Optional


class Provider(BaseModel):
    id: str
    name: str
    capabilities: Optional[List[str]] = None


class SyncItem(BaseModel):
    clientId: Optional[int]
    serverId: Optional[str]
    status: Optional[str]
    updated_at: Optional[str]


class SyncRequest(BaseModel):
    items: List[dict]


class SyncResponse(BaseModel):
    items: List[SyncItem]
