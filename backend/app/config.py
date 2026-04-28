from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root .env (shared by all tools)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # backend/app/config.py -> project root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/waimao"
    replicate_api_token: str = ""
    serper_api_key: str = ""
    resend_api_key: str = ""
    mail_domain: str = "@yourdomain.com"
    from_email: str = ""
    reply_to_email: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"
    api_secret: str = "change-me-in-production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
