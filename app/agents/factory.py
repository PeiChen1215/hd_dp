from typing import Optional
from app.core.config import settings
from .tongyi_agent import TongyiAgent
from .wenxin_agent import WenxinAgent


def get_agent(provider: Optional[str] = None):
    provider = provider or settings.DEFAULT_AI_PROVIDER
    if provider == "tongyi":
        return TongyiAgent()
    if provider == "wenxin":
        return WenxinAgent()
    return TongyiAgent()
