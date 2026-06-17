"""Document status route must not require OpenAI."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://finance:test@localhost:5432/finance_ai_test",
)
os.environ.setdefault("JWT_SECRET", "integration-test-jwt-secret-32chars")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("STORAGE_PATH", "/tmp/finance-ai-test-uploads")

import pytest
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_document_status_controller
from api.controllers.document_controller import DocumentController
from main import app
from services.document_service import DocumentService
from services.jwt_service import create_access_token


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_status_works_without_openai_client(monkeypatch):
    monkeypatch.setattr(
        "middleware.auth.token_version_valid",
        AsyncMock(return_value=True),
    )

    upload_row = MagicMock()
    upload_row.id = 5
    upload_row.uploaded_by = 1
    upload_row.original_filename = "invoice.pdf"
    upload_row.processing_status = "queued"
    upload_row.mime_type = "application/pdf"
    upload_row.file_size = 1200

    upload_repo = AsyncMock()
    upload_repo.get = AsyncMock(return_value=upload_row)
    invoice_repo = AsyncMock()

    service = DocumentService(upload_repo, invoice_repo, None, None)
    app.dependency_overrides[get_document_status_controller] = (
        lambda: DocumentController(service)
    )

    token = create_access_token(
        user_id=1,
        email="user@example.com",
        role="finance",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/documents/5/status",
            cookies={"access_token": token},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == 5
    assert body["upload_status"] == "queued"
