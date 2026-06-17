"""Shared SMTP delivery with logging and safe failure handling."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from config import settings
from core.debug_logger import get_logger
from services.email_types import EmailSendResult

logger = get_logger(__name__)


def log_smtp_config(*, context: str) -> None:
    """Log resolved SMTP settings used at runtime (never log the password)."""
    logger.info(
        "SMTP config (%s, source=environment): host=%s port=%s user=%s "
        "password_set=%s tls=%s from=%s",
        context,
        settings.smtp_host or "(empty)",
        settings.smtp_port,
        settings.smtp_username or "(empty)",
        bool(settings.smtp_password),
        settings.smtp_use_tls,
        settings.smtp_from_email,
    )


def _validate_smtp_config(*, context: str) -> EmailSendResult | None:
    log_smtp_config(context=context)

    if not settings.smtp_host.strip():
        logger.warning("SMTP send skipped (%s): SMTP_HOST is empty", context)
        return EmailSendResult(delivered=False, error="smtp_host_missing")

    if not isinstance(settings.smtp_port, int) or settings.smtp_port <= 0:
        logger.error(
            "SMTP send skipped (%s): invalid SMTP_PORT=%r",
            context,
            settings.smtp_port,
        )
        return EmailSendResult(delivered=False, error="smtp_port_invalid")

    if settings.smtp_username and not settings.smtp_password:
        logger.error(
            "SMTP send skipped (%s): SMTP_USERNAME set but SMTP_PASSWORD is empty",
            context,
        )
        return EmailSendResult(delivered=False, error="smtp_password_missing")

    return None


def send_email_message(message: EmailMessage, *, context: str) -> EmailSendResult:
    """Send an email via SMTP. Never raises — returns EmailSendResult instead."""
    validation_error = _validate_smtp_config(context=context)
    if validation_error is not None:
        return validation_error

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=10,
        ) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        logger.info(
            "SMTP delivery succeeded (%s): to=%s host=%s port=%s",
            context,
            message.get("To", "(unknown)"),
            settings.smtp_host,
            settings.smtp_port,
        )
        return EmailSendResult(delivered=True)
    except OSError as exc:
        logger.exception(
            "SMTP connection failed (%s): host=%s port=%s errno=%s — "
            "many PaaS hosts block outbound SMTP; use an HTTP email API instead",
            context,
            settings.smtp_host,
            settings.smtp_port,
            getattr(exc, "errno", None),
        )
        return EmailSendResult(
            delivered=False,
            error=f"smtp_connection_failed: {exc}",
        )
    except smtplib.SMTPException as exc:
        logger.exception(
            "SMTP protocol error (%s): host=%s port=%s",
            context,
            settings.smtp_host,
            settings.smtp_port,
        )
        return EmailSendResult(delivered=False, error=f"smtp_protocol_error: {exc}")
    except Exception as exc:
        logger.exception(
            "Unexpected SMTP error (%s): host=%s port=%s",
            context,
            settings.smtp_host,
            settings.smtp_port,
        )
        return EmailSendResult(delivered=False, error=f"smtp_unexpected_error: {exc}")
