from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MATINFIX"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./matinfix.db"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str | None = None
    accountant_codeword: str = "NSS"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
