"""
FastAPI dependency providers and shared error translation for the API
layer.

Every route that needs an existing case depends on :func:`get_case`
rather than opening one itself — one place decides that "no such case"
is a 404, not scattered ``try/except`` blocks with slightly different
status codes across route modules.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import HTTPException, Request

from pramaan.api.workspace import CaseWorkspace, WorkspaceError
from pramaan.case.store import Case


def get_workspace(request: Request) -> CaseWorkspace:
    workspace = request.app.state.workspace
    assert isinstance(workspace, CaseWorkspace)  # set by create_app; documents the invariant to mypy
    return workspace


def get_case(case_id: str, request: Request) -> Iterator[Case]:
    """Open ``case_id`` for the duration of one request, closing its
    SQLite connection afterward regardless of how the request ends --
    a generator dependency rather than a plain return so FastAPI runs
    the teardown (:meth:`Case.close`) after the response is built."""
    workspace = get_workspace(request)
    try:
        case = workspace.open_case(case_id)
    except WorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        yield case
    finally:
        case.close()
