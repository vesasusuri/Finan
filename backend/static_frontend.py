"""Serve the Vite production build from FastAPI (single-domain Render deploy)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_RESERVED = frozenset({"api", "docs", "openapi.json", "redoc"})


def register_frontend(app: FastAPI, static_root: Path) -> bool:
    """Mount SPA assets and fallback when a production build is present."""
    index = static_root / "index.html"
    if not index.is_file():
        return False

    assets = static_root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        first = full_path.split("/", 1)[0] if full_path else ""
        if first in _RESERVED or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        if full_path:
            candidate = static_root / full_path
            if candidate.is_file():
                return FileResponse(candidate)

        return FileResponse(index)

    return True
