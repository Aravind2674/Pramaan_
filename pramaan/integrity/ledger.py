"""
An append-only, hash-chained audit log — the chain-of-custody record.

Every operator action, acquisition job, and export gets one entry. Each
entry's hash commits to its own content *and* the previous entry's hash, so
altering any past entry — even just one field — changes that entry's hash,
which no longer matches what the next entry recorded as ``prev_hash``, which
breaks every hash after it. :meth:`Ledger.verify_chain` walks the whole
thing and reports exactly where a break happens, if one exists.

This is deliberately not a Merkle tree (see :mod:`pramaan.integrity.merkle`
for that, used for a different purpose — proving one artifact's membership
in a case's evidence set without disclosing the rest). A custody log is
read start to finish by an examiner or a court; there is no scenario where
someone needs to prove one entry exists without showing the others, so a
straight hash chain is the correct primitive here, not a fancier structure
standing in for one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The `prev_hash` value for the first entry in a ledger — there is no
#: real previous entry to point to, so this is an explicit, documented
#: constant rather than an empty string or None that a bug could produce
#: by accident.
GENESIS_HASH = "0" * 64


class LedgerError(Exception):
    """Raised for a ledger usage error (e.g. content that cannot be hashed)."""


def _canonical_content(
    index: int,
    timestamp: str,
    actor: str,
    action: str,
    target: str,
    detail: dict[str, Any],
    prev_hash: str,
) -> bytes:
    """Deterministic byte encoding of one entry's content, everything
    except its own hash. Sorted keys and compact separators so the same
    logical content always encodes to the same bytes regardless of how a
    dict was constructed."""
    payload = {
        "index": index,
        "timestamp": timestamp,
        "actor": actor,
        "action": action,
        "target": target,
        "detail": detail,
        "prev_hash": prev_hash,
    }
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LedgerError(f"entry content is not JSON-serializable: {exc}") from exc


@dataclass(frozen=True)
class LedgerEntry:
    index: int
    timestamp: str
    actor: str
    action: str
    target: str
    detail: dict[str, Any]
    prev_hash: str
    entry_hash: str

    def recompute_hash(self) -> str:
        """The hash this entry's content *should* have — recomputed fresh
        from every field except ``entry_hash`` itself, never read from it.
        Comparing this against ``entry_hash`` is the whole tamper check."""
        content = _canonical_content(
            self.index, self.timestamp, self.actor, self.action,
            self.target, self.detail, self.prev_hash,
        )
        return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class ChainVerification:
    valid: bool
    break_at_index: int | None
    reason: str | None


def verify_entries(entries: Sequence[LedgerEntry]) -> ChainVerification:
    """The chain-verification logic itself, over a plain sequence of
    entries — not tied to a file-backed :class:`Ledger` instance.

    Exists as its own function (rather than only as a method) so a caller
    holding entries from somewhere other than an open ``Ledger`` — an
    excerpt embedded in a :mod:`pramaan.export` bundle, say — can run the
    exact same check :meth:`Ledger.verify_chain` uses, not a re-implementation
    of it that could drift out of sync.
    """
    expected_prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        if entry.index != i:
            return ChainVerification(
                False, i, f"entry at position {i} declares index {entry.index}"
            )
        if entry.prev_hash != expected_prev:
            return ChainVerification(
                False, i, f"entry {i}'s prev_hash does not match entry {i - 1}'s hash"
            )
        if entry.recompute_hash() != entry.entry_hash:
            return ChainVerification(
                False, i,
                f"entry {i}'s content does not match its recorded hash "
                "-- the entry has been altered since it was appended",
            )
        expected_prev = entry.entry_hash
    return ChainVerification(True, None, None)


class Ledger:
    """An in-memory, optionally file-backed hash chain of entries.

    When ``path`` is given, every :meth:`append` is written to that file
    immediately (one JSON object per line, opened-appended-closed per
    call) — a crash right after an action must not lose the record of it.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._entries: list[LedgerEntry] = []
        if self._path is not None and self._path.exists():
            self._load()

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    @property
    def head_hash(self) -> str:
        """The hash a new entry must chain from. :data:`GENESIS_HASH` for
        an empty ledger."""
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def append(
        self,
        actor: str,
        action: str,
        target: str,
        detail: dict[str, Any] | None = None,
        *,
        timestamp: str | None = None,
    ) -> LedgerEntry:
        """Record one entry, chained from the current head.

        ``detail`` is copied on the way in — the entry stored here must
        never change just because a caller went on to mutate a dict they
        happened to still hold a reference to.
        """
        if detail:
            try:
                detail_copy: dict[str, Any] = json.loads(json.dumps(detail))
            except (TypeError, ValueError) as exc:
                raise LedgerError(f"detail must be JSON-serializable: {exc}") from exc
        else:
            detail_copy = {}
        index = len(self._entries)
        ts = timestamp if timestamp is not None else datetime.now(UTC).isoformat()
        prev_hash = self.head_hash

        content = _canonical_content(index, ts, actor, action, target, detail_copy, prev_hash)
        entry_hash = hashlib.sha256(content).hexdigest()
        entry = LedgerEntry(
            index=index, timestamp=ts, actor=actor, action=action, target=target,
            detail=detail_copy, prev_hash=prev_hash, entry_hash=entry_hash,
        )
        self._entries.append(entry)
        if self._path is not None:
            self._append_to_file(entry)
        return entry

    def verify_chain(self) -> ChainVerification:
        """Walk every entry, recomputing and checking its hash and its
        link to the previous one. Reports the first break found, if any —
        not just whether the chain is valid, but where it stopped being so."""
        return verify_entries(self._entries)

    def _append_to_file(self, entry: LedgerEntry) -> None:
        assert self._path is not None
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(entry), sort_keys=True) + "\n")

    def _load(self) -> None:
        assert self._path is not None
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                self._entries.append(LedgerEntry(**record))
