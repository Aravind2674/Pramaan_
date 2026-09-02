"""
Synthetic demonstration data for pramaan's API and UI.

:func:`pramaan.demo.seed.seed_demo_case` populates a
:class:`pramaan.api.workspace.CaseWorkspace` with a fictional but
internally consistent case -- evidence items, a multi-channel timeline
with a deliberate mix of intact, corrupted, and carved footage, and the
examiner findings that mix produces -- so the UI and API have something
realistic to show instead of an empty workspace.

Every hash here is a real SHA-256 computed over a deterministic
synthetic payload this module generates itself (see
``_synthetic_sha256``); none is a fabricated hex string standing in for
one. Nothing here represents an actual forensic acquisition, and no
production code path in :mod:`pramaan.core`, :mod:`pramaan.recovery`,
:mod:`pramaan.case`, :mod:`pramaan.export`, :mod:`pramaan.report`, or
:mod:`pramaan.api` imports this package.
"""

from pramaan.demo.seed import (
    DEFAULT_CASE_ID,
    DEFAULT_EXAMINER,
    DEFAULT_INVESTIGATING_AGENCY,
    DEFAULT_TITLE,
    SeedResult,
    seed_demo_case,
)

__all__ = [
    "DEFAULT_CASE_ID",
    "DEFAULT_EXAMINER",
    "DEFAULT_INVESTIGATING_AGENCY",
    "DEFAULT_TITLE",
    "SeedResult",
    "seed_demo_case",
]
