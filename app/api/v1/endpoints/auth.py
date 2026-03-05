from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import settings
from app import schemas
from app.services import auth_service
from app.utils.model_converter import user_to_dict

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: schemas.UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册
    
    - **username**: 用户名
    - **password**: 密码
    """
    try:
        user = await auth_service.register_user(db, payload)
        return user_to_dict(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录（OAuth2 密码模式）
    
    - **username**: 用户名
    - **password**: 密码
    
    返回 JWT access_token，后续请求需在 Header 中携带:
    `Authorization: Bearer <token>`
    """
    try:
        user, access_token = await auth_service.login_user(
            db, form_data.username, form_data.password
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
