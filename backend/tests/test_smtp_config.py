"""Config alias tests for SMTP environment variables."""

from config import Settings


def test_smtp_tls_alias(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_SECRET", "local-dev-jwt-secret-minimum-32-chars")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("SMTP_TLS", "false")

    settings = Settings()

    assert settings.smtp_use_tls is False
