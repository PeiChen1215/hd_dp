from fastapi import Depends

from app.api.v1.deps import get_current_user

def optional_current_user(user=Depends(get_current_user)):
    return user
