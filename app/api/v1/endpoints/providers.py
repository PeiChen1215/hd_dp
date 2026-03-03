from fastapi import APIRouter
from typing import List
from app.schemas.misc import Provider

router = APIRouter()


@router.get("/", response_model=List[Provider])
async def list_providers():
    # Return configured AI providers; TODO: load from config
    return [
        {"id": "tongyi", "name": "通义", "capabilities": ["function_call", "embed"]},
        {"id": "wenxin", "name": "文心", "capabilities": ["function_call", "embed"]},
    ]
