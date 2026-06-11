from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    # Keep the default on a current Anthropic API ID. If an account lacks
    # access to Opus, calls fall back through ANTHROPIC_FALLBACK_MODELS.
    anthropic_model: str = "claude-opus-4-8"
    anthropic_fallback_models: str = "claude-sonnet-4-6,claude-haiku-4-5"
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

    @field_validator(
        "anthropic_api_key",
        "anthropic_model",
        "anthropic_fallback_models",
        "openai_api_key",
        "openai_model",
        "youtube_api_key",
        "redis_url",
        "clerk_secret_key",
        "clerk_issuer",
        "allowed_origins",
        mode="before",
    )
    @classmethod
    def _clean_env_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def anthropic_models(self) -> list[str]:
        models = [self.anthropic_model]
        models.extend(model.strip() for model in self.anthropic_fallback_models.split(","))
        return list(dict.fromkeys(model for model in models if model))


@lru_cache
def get_settings() -> Settings:
    return Settings()
