"""
The case workspace: a directory of named case files, addressed by a
short case ID instead of a filesystem path.

:class:`pramaan.case.store.Case` is deliberately path-based and knows
nothing about a "workspace" — a case file is meant to be exactly as
portable as any other SQLite file. An HTTP API, though, needs to address
a case by a short, URL-safe identifier without ever trusting a
client-supplied filesystem path — that would mean either accepting a
real path-traversal risk, or building an entirely separate addressing
scheme just for the API. :class:`CaseWorkspace` is that scheme: one
directory, one case file per case ID, and a strict identifier format
that makes path traversal structurally impossible rather than merely
checked for after the fact.
"""

from __future__ import annotations

import re
from pathlib import Path

from pramaan.case.store import Case

#: 1-100 characters, must start and end with a letter or digit, and
#: contain only letters, digits, '_', '-', or '.' in between. Chosen
#: specifically so a case ID can never be interpreted as a path
#: component that escapes the workspace directory: no '/', no leading
#: '.' (so it can never resolve to '.' or '..'), no leading '-' (so it
#: can never be mistaken for a command-line flag by anything that later
#: shells out with it).
_CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?$")
_CASE_FILE_SUFFIX = ".case"


class WorkspaceError(Exception):
    """Raised for a workspace usage error: an invalid case ID, a case
    that already exists, or a case that doesn't."""


def _validate_case_id(case_id: str) -> None:
    if not _CASE_ID_PATTERN.match(case_id):
        raise WorkspaceError(
            f"invalid case ID {case_id!r} -- must be 1-100 characters, start "
            "and end with a letter or digit, and contain only letters, "
            "digits, '_', '-', or '.' in between"
        )


class CaseWorkspace:
    """A directory of case files, each named ``<case_id>.case`` directly
    under ``root`` — flat, never nested, so a validated case ID can
    never be made to traverse into a subdirectory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, case_id: str) -> Path:
        _validate_case_id(case_id)
        return self._root / f"{case_id}{_CASE_FILE_SUFFIX}"

    def create_case(
        self, case_id: str, *, title: str, investigating_agency: str, examiner_name: str,
    ) -> Case:
        """Create a brand-new case with this workspace-level ``case_id``
        used as both the file's name and the case's own stored
        ``case_id`` field. Raises :class:`WorkspaceError` if a case with
        this ID already exists in this workspace."""
        path = self._path_for(case_id)
        if path.exists():
            raise WorkspaceError(f"a case with ID {case_id!r} already exists in this workspace")
        return Case.create(
            path, case_id=case_id, title=title,
            investigating_agency=investigating_agency, examiner_name=examiner_name,
        )

    def open_case(self, case_id: str) -> Case:
        """Open an existing case by its workspace ID. Raises
        :class:`WorkspaceError` if no such case exists.

        Deliberately no ``except CaseError`` here: :class:`Case`'s plain
        constructor only raises :class:`~pramaan.case.store.CaseError`
        when the path doesn't exist, which this method has already
        checked for above -- wrapping a call that cannot raise it would
        be untestable dead code, not defensive programming.
        """
        path = self._path_for(case_id)
        if not path.exists():
            raise WorkspaceError(f"no case with ID {case_id!r} exists in this workspace")
        return Case(path)

    def list_case_ids(self) -> list[str]:
        """Every case ID currently in this workspace, sorted."""
        return sorted(p.stem for p in self._root.glob(f"*{_CASE_FILE_SUFFIX}"))
