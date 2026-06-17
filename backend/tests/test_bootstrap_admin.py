"""Bootstrap admin user creation on startup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import bootstrap_admin


@pytest.mark.asyncio
async def test_bootstrap_creates_admin_when_database_empty(monkeypatch):
    monkeypatch.setattr(
        "services.bootstrap_admin.settings.bootstrap_admin_email",
        "admin@borek.com",
    )
    monkeypatch.setattr(
        "services.bootstrap_admin.settings.bootstrap_admin_password",
        "longpassword1",
    )
    monkeypatch.setattr(
        "services.bootstrap_admin.settings.bootstrap_admin_role",
        "admin",
    )

    session = AsyncMock()
    session.scalar.side_effect = [None, 0]
    cm = MagicMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None

    with patch("services.bootstrap_admin.async_session", return_value=cm):
        await bootstrap_admin.ensure_bootstrap_admin()

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
