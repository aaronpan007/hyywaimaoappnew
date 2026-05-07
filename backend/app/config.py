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
    replicate_model: str = "openai/gpt-4.1-nano"
    serper_api_key: str = ""
    resend_api_key: str = ""
    resend_webhook_secret: str = ""
    mail_domain: str = "clientconnet.com"
    from_email: str = ""
    reply_to_email: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003"
    api_secret: str = "change-me-in-production"
    better_auth_secret: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
