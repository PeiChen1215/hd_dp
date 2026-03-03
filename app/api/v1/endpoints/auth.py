from fastapi import APIRouter, HTTPException, Depends
from app import schemas

router = APIRouter()


@router.post("/register")
async def register(payload: schemas.UserCreate):
    # TODO: implement registration with DB and password hashing
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/login")
async def login(payload: schemas.UserCreate):
    # TODO: implement login and JWT token issuance
    raise HTTPException(status_code=501, detail="Not implemented")
