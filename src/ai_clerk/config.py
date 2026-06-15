from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str

    # Security
    secret_key: str          # general-purpose signing secret
    fernet_key: str          # encrypts PII at rest

    # Persistence
    database_url: str = "sqlite+aiosqlite:///./ai_clerk.db"

    # Access / onboarding
    admin_telegram_ids: list[int] = []
    invite_ttl_seconds: int = Field(86400, gt=0)  # 24h

    # Ops
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
