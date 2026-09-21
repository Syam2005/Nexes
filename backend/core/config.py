"""NEXUS — Application Configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    GROQ_API_KEY: str = ""

    # Auth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    SECRET_KEY: str = "dev-secret-change-in-production-min-32-chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"

    # Email — Resend (HTTPS, works on Render free tier)
    # Gmail SMTP ports 465/587 are blocked by Render free tier
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "NEXUS <onboarding@resend.dev>"
    # Temporary override — set to your Resend account email (someshkalyan5@gmail.com)
    # until you verify a domain at resend.com/domains.
    # Remove this once domain is verified.
    EMAIL_OVERRIDE_TO: str = ""

    # Legacy Gmail — not used (Render blocks SMTP)
    GMAIL_USER: str = ""
    GMAIL_PASSWORD: str = ""

    # Webhook
    WEBHOOK_SECRET: str = "webhook-secret"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost/nexus"

    # Limits
    MAX_FILE_SIZE_KB: int = 500
    MAX_REPO_FILES: int = 200
    LLM_CHUNK_LINES: int = 300
    LLM_MAX_RETRIES: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()