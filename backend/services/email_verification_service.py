"""Email verification code generation and validation."""

from __future__ import annotations

import math
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from config import settings
from core.debug_logger import get_logger
from models.user import User
from services.email_delivery import email_delivery_configured, send_email
from services.email_types import EmailPayload, EmailSendResult
from services.verification_email_template import (
    build_verification_email_html,
    build_verification_email_plain,
)

logger = get_logger(__name__)

VERIFICATION_CODE_TTL_MINUTES = 10
VERIFICATION_RESEND_COOLDOWN_MINUTES = 2


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verification_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_TTL_MINUTES
    )


def verification_code_issued_at(user: User) -> datetime | None:
    """Infer when the current code was sent from its expiry timestamp."""
    if user.email_verification_expires_at is None:
        return None
    expires = user.email_verification_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires - timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES)


def resend_cooldown_remaining_seconds(user: User) -> int:
    """Seconds until the user may request another verification email."""
    if user.email_verified_at is not None:
        return 0
    issued = verification_code_issued_at(user)
    if issued is None:
        return 0
    elapsed = (datetime.now(timezone.utc) - issued).total_seconds()
    cooldown = VERIFICATION_RESEND_COOLDOWN_MINUTES * 60
    remaining = cooldown - elapsed
    return max(0, math.ceil(remaining))


def resend_cooldown_message(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    if minutes and secs:
        return f"You can request a new code in {minutes}m {secs}s."
    if minutes:
        return f"You can request a new code in {minutes} minute{'s' if minutes != 1 else ''}."
    return f"You can request a new code in {secs} seconds."


def verify_code(user: User, code: str) -> bool:
    if not user.email_verification_code_hash:
        return False
    if user.email_verification_expires_at is None:
        return False
    expires = user.email_verification_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return False
    return bcrypt.checkpw(
        code.encode("utf-8"),
        user.email_verification_code_hash.encode("utf-8"),
    )


def log_verification_code_for_local(email: str, code: str) -> None:
    """Local dev without email provider: codes go to backend logs."""
    if settings.environment != "local":
        return
    if email_delivery_configured() and not settings.log_verification_codes:
        return
    logger.info(
        "Email verification code for %s: %s (expires in %s minutes)",
        email,
        code,
        VERIFICATION_CODE_TTL_MINUTES,
    )


def send_verification_code(email: str, code: str) -> EmailSendResult:
    if not email_delivery_configured():
        log_verification_code_for_local(email, code)
        return EmailSendResult(delivered=False, error="email_not_configured")

    payload = EmailPayload(
        from_addr=settings.smtp_from_email,
        to_addr=email,
        subject="Your Borek Finance verification code",
        text=build_verification_email_plain(code, ttl_minutes=VERIFICATION_CODE_TTL_MINUTES),
        html=build_verification_email_html(
            code,
            ttl_minutes=VERIFICATION_CODE_TTL_MINUTES,
            logo_src=None,
        ),
    )
    return send_email(payload, context="verification_code")
