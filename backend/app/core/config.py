from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Database
    DATABASE_URL: str

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_CHAT_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"

    # Billing
    STRIPE_SECRET_KEY: str = "sandbox_no_bank"
    STRIPE_WEBHOOK_SECRET: str = "whsec_sandbox_local_secret"
    STRIPE_PRO_PRICE_ID: str = ""

    # Optional n8n webhook
    N8N_WEBHOOK_URL: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Accept a raw Neon connection string and make it asyncpg-compatible."""
        parsed = urlparse(value)
        scheme = parsed.scheme
        if scheme in ("postgres", "postgresql"):
            scheme = "postgresql+asyncpg"
        query = dict(parse_qsl(parsed.query))
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)
        if sslmode and sslmode != "disable" and "ssl" not in query:
            query["ssl"] = "require"
        return urlunparse(parsed._replace(scheme=scheme, query=urlencode(query)))

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def stripe_sandbox_mode(self) -> bool:
        return self.STRIPE_SECRET_KEY == "sandbox_no_bank"


settings = Settings()