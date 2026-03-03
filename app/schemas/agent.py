from pydantic import BaseModel
from typing import Optional


class AgentRequest(BaseModel):
    text: str
    conversation_id: Optional[str] = None


class AgentResponse(BaseModel):
    action: str
    entity: str
    data: dict
    reply: str
