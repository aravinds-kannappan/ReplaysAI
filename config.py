from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    youtube_api_key: str = ""
    redis_url: str = ""
    clerk_secret_key: str = ""
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
