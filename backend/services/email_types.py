"""Shared email delivery types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailPayload:
    from_addr: str
    to_addr: str
    subject: str
    text: str
    html: str


@dataclass(frozen=True)
class EmailSendResult:
    delivered: bool
    error: str | None = None
