from fastapi import APIRouter, Depends
from app.schemas.agent import AgentRequest, AgentResponse
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post("/process", response_model=AgentResponse)
async def process_agent(req: AgentRequest, user=Depends(get_current_user)):
    # TODO: call agent service and execute instruction
    return AgentResponse(action="noop", entity="none", data={}, reply="未实现")
