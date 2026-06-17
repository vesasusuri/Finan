"""Tests for SMTP delivery helpers."""

from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from services.smtp_service import send_email_message


@pytest.fixture
def smtp_settings(monkeypatch):
    monkeypatch.setattr("services.smtp_service.settings.smtp_host", "smtp.gmail.com")
    monkeypatch.setattr("services.smtp_service.settings.smtp_port", 587)
    monkeypatch.setattr("services.smtp_service.settings.smtp_username", "user@example.com")
    monkeypatch.setattr("services.smtp_service.settings.smtp_password", "secret")
    monkeypatch.setattr("services.smtp_service.settings.smtp_use_tls", True)
    monkeypatch.setattr("services.smtp_service.settings.smtp_from_email", "user@example.com")


def test_send_email_message_returns_error_when_host_missing(monkeypatch):
    monkeypatch.setattr("services.smtp_service.settings.smtp_host", "")
    message = EmailMessage()
    message["To"] = "to@example.com"

    result = send_email_message(message, context="test")

    assert result.delivered is False
    assert result.error == "smtp_host_missing"


def test_send_email_message_handles_connection_failure(smtp_settings, monkeypatch):
    message = EmailMessage()
    message["To"] = "to@example.com"

    smtp = MagicMock()
    smtp.__enter__.side_effect = OSError(101, "Network is unreachable")
    monkeypatch.setattr("services.smtp_service.smtplib.SMTP", lambda *args, **kwargs: smtp)

    result = send_email_message(message, context="test")

    assert result.delivered is False
    assert result.error is not None
    assert "smtp_connection_failed" in result.error


def test_send_email_message_succeeds(smtp_settings, monkeypatch):
    message = EmailMessage()
    message["To"] = "to@example.com"

    smtp = MagicMock()
    monkeypatch.setattr("services.smtp_service.smtplib.SMTP", lambda *args, **kwargs: smtp)

    result = send_email_message(message, context="test")

    assert result.delivered is True
    assert result.error is None
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once()
    smtp.send_message.assert_called_once_with(message)
