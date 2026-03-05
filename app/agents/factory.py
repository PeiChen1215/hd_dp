from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from .tongyi_agent import TongyiAgent
from .wenxin_agent import WenxinAgent
from .wanji_agent import WanjiAgent


def get_agent(provider: Optional[str] = None, db: Optional[AsyncSession] = None, user_id: Optional[str] = None):
    """
    获取 Agent 实例
    
    Args:
        provider: 提供商名称 (wanji/tongyi/wenxin)
        db: 数据库会话（wanji agent 需要）
        user_id: 用户ID（wanji agent 需要）
    """
    provider = provider or settings.DEFAULT_AI_PROVIDER
    
    if provider == "wanji":
        if db is None or user_id is None:
            raise ValueError("WanjiAgent requires db and user_id")
        return WanjiAgent(db=db, user_id=user_id)
    
    if provider == "tongyi":
        return TongyiAgent()
    
    if provider == "wenxin":
        return WenxinAgent()
    
    # 默认使用 wanji（如果配置了 DeepSeek API Key）
    if settings.DASHSCOPE_API_KEY and db and user_id:
        return WanjiAgent(db=db, user_id=user_id)
    
    return TongyiAgent()
