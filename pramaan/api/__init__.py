"""
API layer — the FastAPI service exposing case management, evidence and
clip bookkeeping, the timeline, audit-ledger integrity, both report
documents, and SEF export as one coherent HTTP interface.

:func:`pramaan.api.app.create_app` is the only entry point a deployment
needs: it wires a :class:`pramaan.api.workspace.CaseWorkspace` (a
directory of named case files, addressed by a short URL-safe case ID
instead of a filesystem path) to a full set of REST routes built
directly on the already-tested :mod:`pramaan.case`,
:mod:`pramaan.timeline`, :mod:`pramaan.report`, and :mod:`pramaan.export`
modules. This layer adds no forensic logic of its own — only HTTP
plumbing, request/response validation, and error translation around what
those layers already do and already test.
"""

from pramaan.api.app import create_app
from pramaan.api.workspace import CaseWorkspace, WorkspaceError

__all__ = ["CaseWorkspace", "WorkspaceError", "create_app"]
