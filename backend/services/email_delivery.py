"""Email delivery — SMTP (local) or HTTP API providers (Render production)."""

from __future__ import annotations

import httpx

from config import settings
from core.debug_logger import get_logger
from services.email_types import EmailPayload, EmailSendResult
from services.smtp_service import send_email_message

logger = get_logger(__name__)

HTTP_PROVIDERS = frozenset({"resend", "sendgrid", "mailgun", "postmark"})


def effective_email_provider() -> str:
    return settings.effective_email_provider


def email_delivery_configured() -> bool:
    provider = effective_email_provider()
    if provider == "none":
        return False
    if not settings.smtp_from_email.strip():
        return False
    if provider == "resend":
        return bool(settings.resend_api_key.strip())
    if provider == "sendgrid":
        return bool(settings.sendgrid_api_key.strip())
    if provider == "mailgun":
        return bool(
            settings.mailgun_api_key.strip() and settings.mailgun_domain.strip()
        )
    if provider == "postmark":
        return bool(settings.postmark_server_token.strip())
    if provider == "smtp":
        return bool(settings.smtp_host.strip())
    return False


def log_email_config(*, context: str) -> None:
    provider = effective_email_provider()
    logger.info(
        "Email config (%s, source=environment): provider=%s from=%s "
        "resend_key_set=%s sendgrid_key_set=%s mailgun_key_set=%s "
        "postmark_token_set=%s smtp_host=%s",
        context,
        provider,
        settings.smtp_from_email,
        bool(settings.resend_api_key),
        bool(settings.sendgrid_api_key),
        bool(settings.mailgun_api_key),
        bool(settings.postmark_server_token),
        settings.smtp_host or "(empty)",
    )


def _validate_payload(payload: EmailPayload, *, context: str) -> EmailSendResult | None:
    log_email_config(context=context)
    provider = effective_email_provider()

    if provider == "none":
        logger.warning("Email send skipped (%s): no provider configured", context)
        return EmailSendResult(delivered=False, error="email_provider_not_configured")

    if not payload.from_addr.strip():
        return EmailSendResult(delivered=False, error="email_from_missing")

    if not payload.to_addr.strip():
        return EmailSendResult(delivered=False, error="email_to_missing")

    if provider == "resend" and not settings.resend_api_key.strip():
        return EmailSendResult(delivered=False, error="resend_api_key_missing")
    if provider == "sendgrid" and not settings.sendgrid_api_key.strip():
        return EmailSendResult(delivered=False, error="sendgrid_api_key_missing")
    if provider == "mailgun" and (
        not settings.mailgun_api_key.strip() or not settings.mailgun_domain.strip()
    ):
        return EmailSendResult(delivered=False, error="mailgun_config_missing")
    if provider == "postmark" and not settings.postmark_server_token.strip():
        return EmailSendResult(delivered=False, error="postmark_token_missing")
    if provider == "smtp" and not settings.smtp_host.strip():
        return EmailSendResult(delivered=False, error="smtp_host_missing")

    return None


def _http_error_result(*, context: str, provider: str, exc: Exception) -> EmailSendResult:
    logger.exception("Email delivery failed (%s) via %s", context, provider)
    return EmailSendResult(delivered=False, error=f"{provider}_delivery_failed: {exc}")


def _send_via_resend(payload: EmailPayload, *, context: str) -> EmailSendResult:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": payload.from_addr,
                    "to": [payload.to_addr],
                    "subject": payload.subject,
                    "html": payload.html,
                    "text": payload.text,
                },
            )
        if response.status_code >= 400:
            logger.error(
                "Resend API error (%s): status=%s body=%s",
                context,
                response.status_code,
                response.text,
            )
            return EmailSendResult(
                delivered=False,
                error=f"resend_api_error: {response.status_code} {response.text}",
            )
        logger.info(
            "Resend delivery succeeded (%s): to=%s id=%s",
            context,
            payload.to_addr,
            response.json().get("id", ""),
        )
        return EmailSendResult(delivered=True)
    except Exception as exc:
        return _http_error_result(context=context, provider="resend", exc=exc)


def _send_via_sendgrid(payload: EmailPayload, *, context: str) -> EmailSendResult:
    body = {
        "personalizations": [{"to": [{"email": payload.to_addr}]}],
        "from": {"email": payload.from_addr},
        "subject": payload.subject,
        "content": [
            {"type": "text/plain", "value": payload.text},
            {"type": "text/html", "value": payload.html},
        ],
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {settings.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        if response.status_code >= 400:
            logger.error(
                "SendGrid API error (%s): status=%s body=%s",
                context,
                response.status_code,
                response.text,
            )
            return EmailSendResult(
                delivered=False,
                error=f"sendgrid_api_error: {response.status_code} {response.text}",
            )
        logger.info("SendGrid delivery succeeded (%s): to=%s", context, payload.to_addr)
        return EmailSendResult(delivered=True)
    except Exception as exc:
        return _http_error_result(context=context, provider="sendgrid", exc=exc)


def _send_via_mailgun(payload: EmailPayload, *, context: str) -> EmailSendResult:
    region = (settings.mailgun_region or "us").strip().lower()
    base = "https://api.mailgun.net" if region == "us" else "https://api.eu.mailgun.net"
    url = f"{base}/v3/{settings.mailgun_domain}/messages"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                auth=("api", settings.mailgun_api_key),
                data={
                    "from": payload.from_addr,
                    "to": payload.to_addr,
                    "subject": payload.subject,
                    "text": payload.text,
                    "html": payload.html,
                },
            )
        if response.status_code >= 400:
            logger.error(
                "Mailgun API error (%s): status=%s body=%s",
                context,
                response.status_code,
                response.text,
            )
            return EmailSendResult(
                delivered=False,
                error=f"mailgun_api_error: {response.status_code} {response.text}",
            )
        logger.info("Mailgun delivery succeeded (%s): to=%s", context, payload.to_addr)
        return EmailSendResult(delivered=True)
    except Exception as exc:
        return _http_error_result(context=context, provider="mailgun", exc=exc)


def _send_via_postmark(payload: EmailPayload, *, context: str) -> EmailSendResult:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.postmarkapp.com/email",
                headers={
                    "X-Postmark-Server-Token": settings.postmark_server_token,
                    "Content-Type": "application/json",
                },
                json={
                    "From": payload.from_addr,
                    "To": payload.to_addr,
                    "Subject": payload.subject,
                    "HtmlBody": payload.html,
                    "TextBody": payload.text,
                },
            )
        if response.status_code >= 400:
            logger.error(
                "Postmark API error (%s): status=%s body=%s",
                context,
                response.status_code,
                response.text,
            )
            return EmailSendResult(
                delivered=False,
                error=f"postmark_api_error: {response.status_code} {response.text}",
            )
        logger.info("Postmark delivery succeeded (%s): to=%s", context, payload.to_addr)
        return EmailSendResult(delivered=True)
    except Exception as exc:
        return _http_error_result(context=context, provider="postmark", exc=exc)


def _payload_to_mime(payload: EmailPayload):
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = payload.subject
    message["From"] = payload.from_addr
    message["To"] = payload.to_addr
    message.set_content(payload.text)
    message.add_alternative(payload.html, subtype="html")
    return message


def send_email(payload: EmailPayload, *, context: str) -> EmailSendResult:
    """Deliver email via configured provider. Never raises."""
    validation_error = _validate_payload(payload, context=context)
    if validation_error is not None:
        return validation_error

    provider = effective_email_provider()
    if provider == "resend":
        return _send_via_resend(payload, context=context)
    if provider == "sendgrid":
        return _send_via_sendgrid(payload, context=context)
    if provider == "mailgun":
        return _send_via_mailgun(payload, context=context)
    if provider == "postmark":
        return _send_via_postmark(payload, context=context)
    if provider == "smtp":
        return send_email_message(_payload_to_mime(payload), context=context)

    return EmailSendResult(
        delivered=False,
        error=f"unsupported_email_provider: {provider}",
    )
