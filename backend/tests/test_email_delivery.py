"""Tests for HTTP email providers."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.email_delivery import send_email
from services.email_types import EmailPayload


def _payload() -> EmailPayload:
    return EmailPayload(
        from_addr="Borek Finance <noreply@borek.com>",
        to_addr="user@example.com",
        subject="Test",
        text="plain body",
        html="<p>html body</p>",
    )


def test_send_email_via_resend(monkeypatch):
    monkeypatch.setattr("services.email_delivery.settings.email_provider", "resend")
    monkeypatch.setattr("services.email_delivery.settings.resend_api_key", "re_test")
    monkeypatch.setattr(
        "services.email_delivery.settings.smtp_from_email",
        "noreply@borek.com",
    )

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "msg_123"}
    response.text = '{"id":"msg_123"}'

    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response
    monkeypatch.setattr("services.email_delivery.httpx.Client", lambda **kwargs: client)

    result = send_email(_payload(), context="test")

    assert result.delivered is True
    client.post.assert_called_once()
    call_kwargs = client.post.call_args.kwargs
    assert call_kwargs["json"]["to"] == ["user@example.com"]


def test_send_email_resend_api_error(monkeypatch):
    monkeypatch.setattr("services.email_delivery.settings.email_provider", "resend")
    monkeypatch.setattr("services.email_delivery.settings.resend_api_key", "re_test")
    monkeypatch.setattr(
        "services.email_delivery.settings.smtp_from_email",
        "noreply@borek.com",
    )

    response = MagicMock()
    response.status_code = 403
    response.text = "domain not verified"
    response.json.return_value = {}

    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response
    monkeypatch.setattr("services.email_delivery.httpx.Client", lambda **kwargs: client)

    result = send_email(_payload(), context="test")

    assert result.delivered is False
    assert "resend_api_error" in (result.error or "")


def test_effective_provider_auto_detects_resend(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_SECRET", "local-dev-jwt-secret-minimum-32-chars")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("EMAIL_PROVIDER", "")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")

    from config import Settings

    settings = Settings()
    assert settings.effective_email_provider == "resend"
