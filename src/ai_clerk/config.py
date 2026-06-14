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
    secret_key: str          # signs invite tokens
    fernet_key: str          # encrypts PII at rest

    # Persistence
    database_url: str = "sqlite+aiosqlite:///./ai_clerk.db"

    # Access / onboarding
    admin_telegram_ids: list[int] = []
    invite_ttl_seconds: int = 86400  # 24h

    # Ops
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
