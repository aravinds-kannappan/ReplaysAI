from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    # claude-3-5-sonnet-latest was retired in Oct 2025 and now 404s.
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    youtube_api_key: str = ""
    redis_url: str = ""
    clerk_secret_key: str = ""
    clerk_issuer: str = ""  # e.g. https://clerk.yourdomain.com for custom Clerk domains
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
