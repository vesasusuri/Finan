"""Create or update the first admin user from environment variables on startup."""

from __future__ import annotations

from sqlalchemy import func, select

from config import settings
from core.debug_logger import get_logger
from core.roles import is_valid_role
from db.pool import async_session
from models.user import User
from utils.password_hashing import hash_password

logger = get_logger(__name__)


async def ensure_bootstrap_admin() -> None:
    """Create bootstrap admin when env vars are set and the account is missing."""
    email = settings.bootstrap_admin_email.strip().lower()
    password = settings.bootstrap_admin_password
    role = settings.bootstrap_admin_role.strip().lower() or "admin"

    if not email or not password:
        return
    if len(password) < 12:
        logger.warning(
            "BOOTSTRAP_ADMIN_PASSWORD is shorter than 12 characters — skipping bootstrap"
        )
        return
    if not is_valid_role(role):
        logger.warning(
            "BOOTSTRAP_ADMIN_ROLE=%s is invalid — skipping bootstrap", role
        )
        return

    async with async_session() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            logger.info("Bootstrap admin skipped — user already exists for %s", email)
            return

        user_count = await session.scalar(select(func.count()).select_from(User))
        if user_count and user_count > 0:
            logger.warning(
                "Bootstrap admin skipped — users already exist in database "
                "(set credentials for an existing account or use scripts/create_user.py)"
            )
            return

        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
                must_change_password=False,
            )
        )
        await session.commit()
        logger.info("Bootstrap admin created for %s (role=%s)", email, role)
