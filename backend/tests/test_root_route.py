"""Smoke tests for public deployment routes."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://finance:test@localhost:5432/finance_ai_test",
)
os.environ.setdefault("JWT_SECRET", "integration-test-jwt-secret-32chars")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("STORAGE_PATH", "/tmp/finance-ai-test-uploads")
os.environ.setdefault("ENABLE_OPENAPI", "true")

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_root_returns_ok() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "API is running"}


@pytest.mark.asyncio
async def test_openapi_enabled_when_configured() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Borek Finance Invoice Automation"
