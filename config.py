from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    youtube_api_key: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/replaysai"
    redis_url: str = "redis://localhost:6379"
    clerk_secret_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
