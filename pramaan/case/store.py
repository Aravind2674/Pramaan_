"""
The case store: one portable SQLite file per investigation, plus the
tamper-evident audit ledger every mutation is automatically recorded into.

Deliberately plain ``sqlite3`` from the standard library, not an ORM — a
case file needs to be openable by a court's own tooling, by ``sqlite3``
from the command line, by anything, without this project's dependency
stack installed. WAL mode is enabled for the same reason acquisition uses
streaming reads: an investigator working a live case should not have a
long-running query block a concurrent write, or vice versa.

Every mutating method appends one entry to this case's
:class:`pramaan.integrity.ledger.Ledger` before returning — not as an
optional extra a caller has to remember to wire up, but as part of what
"adding an evidence item" or "recording a clip" *means* in this tool. A
case action that happened but left no trace in the ledger is exactly the
gap this project's whole integrity layer exists to close.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from pramaan.integrity.ledger import ChainVerification, Ledger
from pramaan.recovery.carver import CarvedClip
from pramaan.recovery.index_walk import ClipRecord as IndexWalkClipRecord
from pramaan.timeline.model import Segment, SegmentKind, Timeline

_SCHEMA = """
CREATE TABLE IF NOT EXISTS case_info (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    case_id TEXT NOT NULL,
    title TEXT NOT NULL,
    investigating_agency TEXT NOT NULL,
    examiner_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    device_type TEXT,
    make_model TEXT,
    serial_number TEXT,
    source_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    acquired_at TEXT NOT NULL,
    write_block_attestation TEXT
);

CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_item_id INTEGER NOT NULL REFERENCES evidence_items(id),
    channel INTEGER NOT NULL,
    kind TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    start_time TEXT,
    end_time TEXT,
    first_sequence INTEGER,
    last_sequence INTEGER,
    frame_count INTEGER,
    sha256 TEXT,
    format_id TEXT,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    author TEXT NOT NULL,
    clip_id INTEGER REFERENCES clips(id),
    category TEXT NOT NULL,
    description TEXT NOT NULL
);
"""

_VALID_CLIP_KINDS = frozenset(k.value for k in SegmentKind)


class CaseError(Exception):
    """Raised for a case-store usage error (not a SQLite internal error,
    which is left to surface as-is — this is for misuse this layer itself
    can detect, like creating a case that already exists)."""


@dataclass(frozen=True)
class CaseInfo:
    case_id: str
    title: str
    investigating_agency: str
    examiner_name: str
    created_at: str


@dataclass(frozen=True)
class EvidenceItem:
    id: int
    description: str
    device_type: str | None
    make_model: str | None
    serial_number: str | None
    source_path: str
    sha256: str
    size_bytes: int
    acquired_at: str
    write_block_attestation: dict[str, Any] | None


@dataclass(frozen=True)
class ClipRow:
    id: int
    evidence_item_id: int
    channel: int
    kind: str
    start_offset: int | None
    end_offset: int | None
    start_time: str | None
    end_time: str | None
    first_sequence: int | None
    last_sequence: int | None
    frame_count: int | None
    sha256: str | None
    format_id: str | None
    note: str


@dataclass(frozen=True)
class Finding:
    id: int
    created_at: str
    author: str
    clip_id: int | None
    category: str
    description: str


def _row_to_evidence_item(row: sqlite3.Row) -> EvidenceItem:
    attestation = json.loads(row["write_block_attestation"]) if row["write_block_attestation"] else None
    return EvidenceItem(
        id=row["id"], description=row["description"], device_type=row["device_type"],
        make_model=row["make_model"], serial_number=row["serial_number"],
        source_path=row["source_path"], sha256=row["sha256"], size_bytes=row["size_bytes"],
        acquired_at=row["acquired_at"], write_block_attestation=attestation,
    )


def _row_to_clip(row: sqlite3.Row) -> ClipRow:
    return ClipRow(
        id=row["id"], evidence_item_id=row["evidence_item_id"], channel=row["channel"],
        kind=row["kind"], start_offset=row["start_offset"], end_offset=row["end_offset"],
        start_time=row["start_time"], end_time=row["end_time"],
        first_sequence=row["first_sequence"], last_sequence=row["last_sequence"],
        frame_count=row["frame_count"], sha256=row["sha256"], format_id=row["format_id"],
        note=row["note"],
    )


def _row_to_finding(row: sqlite3.Row) -> Finding:
    return Finding(
        id=row["id"], created_at=row["created_at"], author=row["author"],
        clip_id=row["clip_id"], category=row["category"], description=row["description"],
    )


class Case:
    """One investigation's persistent state: case metadata, evidence
    items, recovered clips, examiner findings, and (via :attr:`ledger`) a
    complete audit trail of every mutation made to any of them.
    """

    def __init__(self, path: str | Path, *, _allow_create: bool = False) -> None:
        self._path = Path(path)
        if not self._path.exists() and not _allow_create:
            raise CaseError(
                f"no case file exists at {self._path} -- use Case.create() to "
                "make a new one; the plain constructor only opens an existing "
                "case, so a typo'd path fails loudly instead of silently "
                "creating an empty, uninitialized file there"
            )
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._ledger = Ledger(self._path.with_name(self._path.name + ".ledger.jsonl"))

    @classmethod
    def create(
        cls,
        path: str | Path,
        *,
        case_id: str,
        title: str,
        investigating_agency: str,
        examiner_name: str,
        created_at: str | None = None,
    ) -> Case:
        """Create a brand-new case file. Raises :class:`CaseError` if one
        already exists at ``path`` — a case is created exactly once; every
        later open is a plain :class:`Case` construction."""
        path = Path(path)
        if path.exists():
            raise CaseError(f"a case file already exists at {path}")
        case = cls(path, _allow_create=True)
        ts = created_at if created_at is not None else datetime.now(UTC).isoformat()
        case._conn.execute(
            "INSERT INTO case_info (id, case_id, title, investigating_agency, "
            "examiner_name, created_at) VALUES (1, ?, ?, ?, ?, ?)",
            (case_id, title, investigating_agency, examiner_name, ts),
        )
        case._conn.commit()
        case._ledger.append(
            actor=examiner_name, action="create_case", target=case_id,
            detail={"title": title, "investigating_agency": investigating_agency},
            timestamp=ts,
        )
        return case

    @property
    def ledger(self) -> Ledger:
        return self._ledger

    def verify_integrity(self) -> ChainVerification:
        """Verify this case's audit ledger. Does not itself re-verify
        evidence-item hashes against their source files — that is
        acquisition-time work already recorded at intake; this checks that
        the *record of what happened* hasn't been altered since."""
        return self._ledger.verify_chain()

    def info(self) -> CaseInfo:
        row = self._conn.execute("SELECT * FROM case_info WHERE id = 1").fetchone()
        if row is None:
            raise CaseError(f"{self._path} has no case_info row — was it created with Case.create?")
        return CaseInfo(
            case_id=row["case_id"], title=row["title"],
            investigating_agency=row["investigating_agency"],
            examiner_name=row["examiner_name"], created_at=row["created_at"],
        )

    def add_evidence_item(
        self,
        *,
        description: str,
        source_path: str,
        sha256: str,
        size_bytes: int,
        device_type: str | None = None,
        make_model: str | None = None,
        serial_number: str | None = None,
        acquired_at: str | None = None,
        write_block_attestation: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> EvidenceItem:
        ts = acquired_at if acquired_at is not None else datetime.now(UTC).isoformat()
        attestation_json = json.dumps(write_block_attestation) if write_block_attestation else None
        cursor = self._conn.execute(
            "INSERT INTO evidence_items (description, device_type, make_model, "
            "serial_number, source_path, sha256, size_bytes, acquired_at, "
            "write_block_attestation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (description, device_type, make_model, serial_number, source_path,
             sha256, size_bytes, ts, attestation_json),
        )
        self._conn.commit()
        assert cursor.lastrowid is not None  # just inserted; sqlite3's stub types it Optional regardless
        item = self.get_evidence_item(cursor.lastrowid)
        self._ledger.append(
            actor=actor or self.info().examiner_name,
            action="add_evidence_item",
            target=f"evidence:{item.id}",
            detail={"description": description, "source_path": source_path, "sha256": sha256},
        )
        return item

    def get_evidence_item(self, item_id: int) -> EvidenceItem:
        row = self._conn.execute("SELECT * FROM evidence_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise CaseError(f"no evidence item with id {item_id}")
        return _row_to_evidence_item(row)

    def list_evidence_items(self) -> list[EvidenceItem]:
        rows = self._conn.execute("SELECT * FROM evidence_items ORDER BY id").fetchall()
        return [_row_to_evidence_item(r) for r in rows]

    def add_clip(
        self,
        evidence_item_id: int,
        *,
        channel: int,
        kind: str,
        start_offset: int | None = None,
        end_offset: int | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        first_sequence: int | None = None,
        last_sequence: int | None = None,
        frame_count: int | None = None,
        sha256: str | None = None,
        format_id: str | None = None,
        note: str = "",
        actor: str | None = None,
    ) -> ClipRow:
        if kind not in _VALID_CLIP_KINDS:
            raise CaseError(f"kind {kind!r} is not one of {sorted(_VALID_CLIP_KINDS)}")
        self.get_evidence_item(evidence_item_id)  # raises CaseError if it doesn't exist
        cursor = self._conn.execute(
            "INSERT INTO clips (evidence_item_id, channel, kind, start_offset, "
            "end_offset, start_time, end_time, first_sequence, last_sequence, "
            "frame_count, sha256, format_id, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (evidence_item_id, channel, kind, start_offset, end_offset, start_time,
             end_time, first_sequence, last_sequence, frame_count, sha256, format_id, note),
        )
        self._conn.commit()
        assert cursor.lastrowid is not None  # just inserted; sqlite3's stub types it Optional regardless
        clip = self._get_clip(cursor.lastrowid)
        self._ledger.append(
            actor=actor or self.info().examiner_name,
            action="add_clip",
            target=f"clip:{clip.id}",
            detail={"evidence_item_id": evidence_item_id, "channel": channel, "kind": kind},
        )
        return clip

    def record_index_walk_clip(
        self, evidence_item_id: int, clip: IndexWalkClipRecord, *, actor: str | None = None
    ) -> ClipRow:
        """Store a :class:`pramaan.recovery.index_walk.ClipRecord` — a
        clip found via an intact index, so its channel and sequence range
        are already known."""
        return self.add_clip(
            evidence_item_id, channel=clip.channel, kind=SegmentKind.RECORDED.value,
            start_offset=clip.start_offset, end_offset=clip.end_offset,
            first_sequence=clip.first_sequence, last_sequence=clip.last_sequence,
            frame_count=clip.frame_count, format_id=clip.format_id, actor=actor,
        )

    def record_carved_clip(
        self, evidence_item_id: int, channel: int, clip: CarvedClip, *, actor: str | None = None
    ) -> ClipRow:
        """Store a :class:`pramaan.recovery.carver.CarvedClip` — carving
        never determines its own channel, so the caller must supply one
        explicitly (from examiner judgement, cross-referencing, or however
        it was actually established) rather than this method guessing."""
        return self.add_clip(
            evidence_item_id, channel=channel, kind=SegmentKind.RECOVERED.value,
            start_offset=clip.start_offset, end_offset=clip.end_offset,
            frame_count=clip.frame_count, sha256=clip.sha256, actor=actor,
        )

    def set_clip_time_range(
        self, clip_id: int, start_time: str, end_time: str, *, actor: str | None = None
    ) -> ClipRow:
        """Attach a wall-clock time range to a clip after the fact — e.g.
        once OSD OCR or clock-drift correction has established one for a
        carved clip that had none at recovery time."""
        self._get_clip(clip_id)  # raises if missing
        self._conn.execute(
            "UPDATE clips SET start_time = ?, end_time = ? WHERE id = ?",
            (start_time, end_time, clip_id),
        )
        self._conn.commit()
        clip = self._get_clip(clip_id)
        self._ledger.append(
            actor=actor or self.info().examiner_name,
            action="set_clip_time_range",
            target=f"clip:{clip_id}",
            detail={"start_time": start_time, "end_time": end_time},
        )
        return clip

    def _get_clip(self, clip_id: int) -> ClipRow:
        row = self._conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
        if row is None:
            raise CaseError(f"no clip with id {clip_id}")
        return _row_to_clip(row)

    def list_clips(
        self, *, evidence_item_id: int | None = None, channel: int | None = None
    ) -> list[ClipRow]:
        query = "SELECT * FROM clips WHERE 1=1"
        params: list[Any] = []
        if evidence_item_id is not None:
            query += " AND evidence_item_id = ?"
            params.append(evidence_item_id)
        if channel is not None:
            query += " AND channel = ?"
            params.append(channel)
        query += " ORDER BY channel, start_offset"
        rows = self._conn.execute(query, params).fetchall()
        return [_row_to_clip(r) for r in rows]

    def add_finding(
        self,
        *,
        author: str,
        category: str,
        description: str,
        clip_id: int | None = None,
        created_at: str | None = None,
    ) -> Finding:
        if clip_id is not None:
            self._get_clip(clip_id)  # raises if missing
        ts = created_at if created_at is not None else datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO findings (created_at, author, clip_id, category, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, author, clip_id, category, description),
        )
        self._conn.commit()
        assert cursor.lastrowid is not None  # just inserted; sqlite3's stub types it Optional regardless
        finding = self.get_finding(cursor.lastrowid)
        self._ledger.append(
            actor=author, action="add_finding", target=f"finding:{finding.id}",
            detail={"category": category, "clip_id": clip_id},
        )
        return finding

    def get_finding(self, finding_id: int) -> Finding:
        row = self._conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        if row is None:
            raise CaseError(f"no finding with id {finding_id}")
        return _row_to_finding(row)

    def list_findings(self) -> list[Finding]:
        rows = self._conn.execute("SELECT * FROM findings ORDER BY id").fetchall()
        return [_row_to_finding(r) for r in rows]

    def build_timeline(self) -> Timeline:
        """A :class:`pramaan.timeline.model.Timeline` over every clip in
        this case that has a known time range.

        A clip with no ``start_time``/``end_time`` yet (a carved clip
        whose time hasn't been established) is excluded, not defaulted to
        anything — a timeline addresses wall-clock time, and a clip with
        no known time literally has nowhere on one to go until
        :meth:`set_clip_time_range` gives it one.
        """
        segments = []
        for clip in self.list_clips():
            if clip.start_time is None or clip.end_time is None:
                continue
            segments.append(
                Segment(
                    channel=clip.channel,
                    start=datetime.fromisoformat(clip.start_time),
                    end=datetime.fromisoformat(clip.end_time),
                    kind=SegmentKind(clip.kind),
                    first_sequence=clip.first_sequence,
                    last_sequence=clip.last_sequence,
                    note=clip.note,
                )
            )
        return Timeline(segments)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
