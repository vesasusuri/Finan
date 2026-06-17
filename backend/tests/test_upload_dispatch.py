"""Tests for OCR dispatch (queue vs inline)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from config import settings


def test_dispatch_inline_schedules_background_task(monkeypatch):
    monkeypatch.setattr(settings, "ocr_processing_mode", "inline")
    scheduled: list[tuple[int, int]] = []

    def _schedule(upload_id: int, user_id: int) -> None:
        scheduled.append((upload_id, user_id))

    monkeypatch.setattr(
        "services.invoice_processing_service.schedule_invoice_ocr",
        _schedule,
    )

    from core.upload_enqueue import dispatch_invoice_ocr

    dispatch_invoice_ocr(42, 7)

    assert scheduled == [(42, 7)]


def test_dispatch_queue_enqueues_rq_job(monkeypatch):
    monkeypatch.setattr(settings, "ocr_processing_mode", "queue")
    enqueued: list[tuple[int, int, dict]] = []

    def _enqueue(upload_id: int, user_id: int, **kwargs):
        enqueued.append((upload_id, user_id, kwargs))
        return "job-123"

    monkeypatch.setattr("core.upload_enqueue.enqueue_process_invoice_upload", _enqueue)

    from core.upload_enqueue import dispatch_invoice_ocr

    dispatch_invoice_ocr(99, 3, priority="high")

    assert enqueued == [(99, 3, {"priority": "high"})]


def test_ocr_runs_inline_property(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_SECRET", "local-dev-jwt-secret-minimum-32-chars")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("OCR_PROCESSING_MODE", "inline")

    from config import Settings

    assert Settings().ocr_runs_inline is True
