from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import User
from app import schemas


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """根据用户名获取用户"""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """根据 ID 获取用户"""
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, user_in: schemas.UserCreate) -> User:
    """
    注册新用户
    
    Args:
        db: 数据库会话
        user_in: 用户创建数据
        
    Returns:
        创建的用户对象
        
    Raises:
        ValueError: 用户名已存在
    """
    # 检查用户名是否已存在
    existing_user = await get_user_by_username(db, user_in.username)
    if existing_user:
        raise ValueError("Username already registered")
    
    # 创建新用户
    db_user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password)
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    """
    验证用户凭据
    
    Args:
        db: 数据库会话
        username: 用户名
        password: 明文密码
        
    Returns:
        验证成功的用户对象，失败返回 None
    """
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def login_user(
    db: AsyncSession, username: str, password: str
) -> tuple[User, str]:
    """
    用户登录，返回用户对象和 JWT token
    
    Args:
        db: 数据库会话
        username: 用户名
        password: 密码
        
    Returns:
        (用户对象, access_token) 元组
        
    Raises:
        ValueError: 认证失败
    """
    user = await authenticate_user(db, username, password)
    if not user:
        raise ValueError("Incorrect username or password")
    
    # 创建 JWT token
    access_token = create_access_token(subject=str(user.id))
    
    return user, access_token
