from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MATINFIX"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./matinfix.db"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str | None = None
    accountant_codeword: str = "NSS"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return a driver URL SQLAlchemy can use in async mode."""
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://") :]
        return url


settings = Settings()
