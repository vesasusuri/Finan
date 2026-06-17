"""Password reset token generation, validation, and email delivery."""

from __future__ import annotations

import math
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import bcrypt

from config import settings
from core.debug_logger import get_logger
from models.user import User
from services.email_delivery import email_delivery_configured, send_email
from services.email_types import EmailPayload, EmailSendResult
from services.password_reset_email_template import (
    build_password_reset_email_html,
    build_password_reset_email_plain,
)

logger = get_logger(__name__)

PASSWORD_RESET_TTL_MINUTES = 60
PASSWORD_RESET_RESEND_COOLDOWN_MINUTES = 2

FORGOT_PASSWORD_MESSAGE = (
    "If an account exists for that email, you will receive a password reset link shortly."
)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def reset_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)


def reset_cooldown_remaining_seconds(user: User) -> int:
    if user.password_reset_requested_at is None:
        return 0
    requested = user.password_reset_requested_at
    if requested.tzinfo is None:
        requested = requested.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - requested).total_seconds()
    cooldown = PASSWORD_RESET_RESEND_COOLDOWN_MINUTES * 60
    remaining = cooldown - elapsed
    return max(0, math.ceil(remaining))


def verify_reset_token(user: User, token: str) -> bool:
    if not user.password_reset_token_hash:
        return False
    if user.password_reset_expires_at is None:
        return False
    expires = user.password_reset_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return False
    return bcrypt.checkpw(
        token.encode("utf-8"),
        user.password_reset_token_hash.encode("utf-8"),
    )


def build_reset_url(email: str, token: str) -> str:
    base = settings.app_base_url.rstrip("/")
    return f"{base}/reset-password?email={quote(email)}&token={quote(token)}"


def log_reset_link_for_local(email: str, reset_url: str) -> None:
    if settings.environment == "local":
        print(
            f"[auth] Password reset link for {email}: {reset_url} "
            f"(expires in {PASSWORD_RESET_TTL_MINUTES} minutes)"
        )


def send_password_reset_email(email: str, token: str) -> EmailSendResult:
    reset_url = build_reset_url(email, token)
    if not email_delivery_configured():
        log_reset_link_for_local(email, reset_url)
        return EmailSendResult(delivered=False, error="email_not_configured")

    payload = EmailPayload(
        from_addr=settings.smtp_from_email,
        to_addr=email,
        subject="Reset your Borek Finance password",
        text=build_password_reset_email_plain(reset_url, ttl_minutes=PASSWORD_RESET_TTL_MINUTES),
        html=build_password_reset_email_html(
            reset_url,
            ttl_minutes=PASSWORD_RESET_TTL_MINUTES,
            logo_src=None,
        ),
    )
    return send_email(payload, context="password_reset")
