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

    class Config:
        env_file = ".env"


settings = Settings()
