from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    # Default to Haiku for speed across the app (recaps, reels, briefings, sims).
    # Opus is intentionally not used: it is far slower for this product's needs.
    anthropic_model: str = "claude-haiku-4-5"
    anthropic_fallback_models: str = "claude-sonnet-4-6"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    youtube_api_key: str = ""
    redis_url: str = ""
    allowed_origins: str = "*"

    # Trained agents (Newsletter writer + Broadcast writer). These are our own
    # fine-tuned open models, served over an OpenAI-compatible API (Baseten /
    # Orthogonal). When set, they are the primary path for those two surfaces;
    # both still fall back to the Anthropic LLM and then the deterministic
    # template, so nothing hard-fails when they are unset. See training/README.md.
    trained_base_url: str = ""       # e.g. https://model-xxxx.api.baseten.co/environments/production/sync/v1
    trained_api_key: str = ""
    newsletter_model: str = ""       # deployed adapter id for the newsletter writer
    broadcast_model: str = ""        # deployed adapter id for the broadcast writer

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
        "allowed_origins",
        "trained_base_url",
        "trained_api_key",
        "newsletter_model",
        "broadcast_model",
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

    @property
    def anthropic_fast_models(self) -> list[str]:
        """Fastest model (Haiku) first, for latency-sensitive text (dashboard
        briefing, what-ifs)."""
        models = self.anthropic_models
        fast = [m for m in models if "haiku" in m]
        return fast + [m for m in models if m not in fast]


@lru_cache
def get_settings() -> Settings:
    return Settings()
