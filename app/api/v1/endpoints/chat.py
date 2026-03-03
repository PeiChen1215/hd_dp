from fastapi import APIRouter, Depends
from app.schemas.chat import ChatRequest, ChatResponse
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    # TODO: implement RAG flow
    return ChatResponse(answer="未实现", sources=[])
