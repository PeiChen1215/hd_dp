from fastapi import APIRouter, Depends
from app.schemas.misc import SyncRequest, SyncResponse
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get("/")
async def sync_get(since: str = None, user=Depends(get_current_user)):
    # TODO: return changes since `since`
    return {"items": [], "cursor": None}


@router.post("/", response_model=SyncResponse)
async def sync_post(payload: SyncRequest, user=Depends(get_current_user)):
    # TODO: implement batch upsert and return mapping results
    return SyncResponse(items=[])
