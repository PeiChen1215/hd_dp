from fastapi import Depends, HTTPException
from app.core.security import verify_password
from app.db.session import get_db

async def get_current_user():
    # Placeholder: implement JWT extraction and DB lookup
    raise HTTPException(status_code=401, detail="Not implemented")
