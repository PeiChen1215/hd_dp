from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.schemas.memo import MemoCreate, MemoOut
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get("/", response_model=List[MemoOut])
async def list_memos(page: int = 1, size: int = 20, user=Depends(get_current_user)):
    # TODO: implement DB query
    return []


@router.post("/", response_model=MemoOut, status_code=201)
async def create_memo(payload: MemoCreate, user=Depends(get_current_user)):
    # TODO: implement creation and return created memo
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{serverId}")
async def get_memo(serverId: str, user=Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/{serverId}")
async def update_memo(serverId: str, payload: MemoCreate, user=Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{serverId}")
async def delete_memo(serverId: str, user=Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Not implemented")
