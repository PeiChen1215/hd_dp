try:
    from pydantic_settings import BaseSettings
except Exception:
    from pydantic import BaseSettings
from pydantic import AnyUrl


class Settings(BaseSettings):
    APP_NAME: str = "ChronoSync"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: AnyUrl

    DEFAULT_AI_PROVIDER: str = "tongyi"
    
    # DeepSeek / 阿里云配置
    DASHSCOPE_API_KEY: str = "sk-49141e05df7f4584966fac0f8cddbb7d"
    DASHSCOPE_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_MODEL: str = "deepseek-v3"

    class Config:
        env_file = ".env"


settings = Settings()
