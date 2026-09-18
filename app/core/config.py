from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MATINFIX"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./matinfix.db"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str | None = None
    telegram_workspace_id: str = "telegram-default"
    accountant_codeword: str = "NSS"
    master_api_key: str | None = None
    master_telegram_user_ids: str = ""
    cors_origins: str = "https://matinfix-dtceinuc.manus.space,http://localhost:3000"
    public_web_url: str = "https://matinfix-dtceinuc.manus.space"
    price_sheet_url: str = ""
    reball_sheet_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return a driver URL SQLAlchemy can use in async mode."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
            return url + ("&" if "?" in url else "?") + "ssl=require"
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
            return url + ("&" if "?" in url else "?") + "ssl=require"
        return url

    @property
    def master_telegram_ids(self) -> set[str]:
        return {item.strip() for item in self.master_telegram_user_ids.split(",") if item.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
