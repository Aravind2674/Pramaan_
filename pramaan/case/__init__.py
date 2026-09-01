"""
Case layer — the aggregation point everything else composes at.

Every earlier layer deliberately left composition to its caller:
:mod:`pramaan.recovery` doesn't know about the integrity ledger, the
timeline model doesn't know about disk images, and the ledger doesn't know
what a "clip" is. :class:`pramaan.case.store.Case` is where those pieces
actually meet — evidence items, recovered clips, and every mutating action
recorded automatically into a tamper-evident audit ledger, all backed by
one portable SQLite file that can travel to court on its own.
"""

from pramaan.case.store import Case, CaseError, CaseInfo, ClipRow, EvidenceItem, Finding

__all__ = ["Case", "CaseError", "CaseInfo", "ClipRow", "EvidenceItem", "Finding"]
