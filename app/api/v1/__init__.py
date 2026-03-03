from fastapi import APIRouter
from app.api.v1.endpoints import health, events, auth, memos, agent, chat, providers, sync

api_router = APIRouter()

api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(memos.router, prefix="/memos", tags=["memos"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(sync.router, prefix="/sync/events", tags=["sync"])

