"""The FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from pramaan.api.routes import api_router
from pramaan.api.workspace import CaseWorkspace


def create_app(workspace_root: str | Path) -> FastAPI:
    """Build the Pramaan API service, backed by a
    :class:`~pramaan.api.workspace.CaseWorkspace` rooted at
    ``workspace_root``. Each call builds a fresh, independent
    application and workspace binding -- there is no shared global
    state, so a test suite (or an embedding process hosting more than
    one workspace) can call this any number of times safely.
    """
    app = FastAPI(
        title="Pramaan",
        description="Multi-vendor DVR/NVR forensic acquisition, recovery, and analysis API.",
        version="0.1.0",
    )
    app.state.workspace = CaseWorkspace(workspace_root)
    app.include_router(api_router)
    return app
