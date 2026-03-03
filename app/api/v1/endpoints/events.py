from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app import schemas
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/", response_model=List[schemas.EventOut])
async def list_events(page: int = 1, size: int = 20, db: AsyncSession = Depends(get_db)):
    # TODO: implement DB query - returns empty list for now
    return []


@router.post("/", response_model=schemas.EventOut)
async def create_event(payload: schemas.EventCreate, db: AsyncSession = Depends(get_db)):
    # TODO: implement creation
    raise HTTPException(status_code=501, detail="Not implemented")
