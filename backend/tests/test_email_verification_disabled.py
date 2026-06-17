"""Auth behaviour when email verification is disabled."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest

from api.controllers.auth_controller import AuthController
from models.user import User
from schemas.auth import LoginRequest


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@pytest.mark.asyncio
async def test_login_skips_verification_email_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "api.controllers.auth_controller.settings.email_verification_enabled",
        False,
    )
    user = User(
        id=1,
        email="finance@example.com",
        password_hash=_hash_password("correcthorse1"),
        role="finance",
        is_active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(timezone.utc),
    )
    user_repo = AsyncMock()
    user_repo.find_by_email.return_value = user
    user_repo.mark_email_verified.return_value = user
    response = MagicMock()
    controller = AuthController(user_repo)

    with (
        patch("api.controllers.auth_controller.revoke_all_refresh_tokens"),
        patch("api.controllers.auth_controller.set_auth_cookies"),
        patch("api.controllers.auth_controller.send_verification_code") as send_code,
        patch("api.controllers.auth_controller.generate_verification_code") as gen_code,
    ):
        result = await controller.login(
            LoginRequest(email=user.email, password="correcthorse1"),
            response,
        )

    assert result.email == user.email
    assert result.email_verified is True
    gen_code.assert_not_called()
    send_code.assert_not_called()
    user_repo.mark_email_verified.assert_awaited_once()
