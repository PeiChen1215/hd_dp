from app.schemas.chat import ChatRequest, ChatResponse


async def answer_question(user_id: str, request: ChatRequest) -> ChatResponse:
    # TODO: implement embedding, vector search and LLM generation
    raise NotImplementedError
