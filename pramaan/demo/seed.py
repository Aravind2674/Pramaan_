"""
Builds one synthetic demonstration case: a fictional warehouse
break-in, recorded across two multi-vendor recorders, with a mix of
intact, corrupted, and carved footage designed to exercise every
anomaly category :mod:`pramaan.timeline.gaps` recognizes.

This module never touches real evidence and is never imported by any
production code path -- see :mod:`pramaan.demo` for the full rationale.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pramaan.api.workspace import CaseWorkspace
from pramaan.case.store import Case, ClipRow
from pramaan.timeline.model import SegmentKind

DEFAULT_CASE_ID = "DEMO-2026-0001"
DEFAULT_TITLE = "Warehouse Break-In -- Multi-Camera DVR Recovery"
DEFAULT_INVESTIGATING_AGENCY = "Cyber Cell, City Police"
DEFAULT_EXAMINER = "Dr. A. Examiner"

# The incident's own clock, not wall-clock "now" -- a demo case should
# look the same today as it will next year, so it is generated relative
# to a fixed point in time rather than datetime.now().
_INCIDENT_START = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)

_WRITE_BLOCK_DETAIL = (
    "OS refused a read-write open (Access is denied); consistent with a "
    "hardware or OS-level write-blocker, but not a substitute for one."
)


def _synthetic_sha256(label: str) -> str:
    """A real SHA-256 over a deterministic synthetic payload, not a
    fabricated hex string -- running this twice for the same ``label``
    always reproduces the same hash."""
    payload = f"pramaan-demo-synthetic-payload::{label}".encode()
    return hashlib.sha256(payload).hexdigest()


def _iso(offset_minutes: int) -> str:
    return (_INCIDENT_START + timedelta(minutes=offset_minutes)).isoformat()


@dataclass(frozen=True)
class SeedResult:
    """What :func:`seed_demo_case` built, for a caller (a CLI, a test)
    that wants to report or inspect it without re-deriving it from the
    case store."""

    case: Case
    evidence_item_ids: dict[str, int]
    clips: list[ClipRow] = field(default_factory=list)
    finding_ids: list[int] = field(default_factory=list)


def seed_demo_case(
    workspace: CaseWorkspace,
    *,
    case_id: str = DEFAULT_CASE_ID,
    title: str = DEFAULT_TITLE,
    investigating_agency: str = DEFAULT_INVESTIGATING_AGENCY,
    examiner_name: str = DEFAULT_EXAMINER,
) -> SeedResult:
    """Create a brand-new case at ``case_id`` in ``workspace`` and
    populate it. Raises :class:`~pramaan.api.workspace.WorkspaceError`
    if a case with this ID already exists -- the same rule every other
    case creation in this project follows; a caller that wants to
    re-seed removes the existing demo case first.
    """
    case = workspace.create_case(
        case_id, title=title, investigating_agency=investigating_agency, examiner_name=examiner_name,
    )

    dvr = case.add_evidence_item(
        description="Dahua XVR5108HS hard disk image (main entrance + loading dock)",
        source_path="/evidence/dahua_xvr_disk1.img",
        sha256=_synthetic_sha256("dahua-xvr-disk1"),
        size_bytes=2_000_398_934_016,
        device_type="DVR",
        make_model="Dahua XVR5108HS",
        serial_number="XVR5108HS-2AK93B",
        write_block_attestation={
            "path": r"\\.\PhysicalDrive2",
            "write_open_refused": True,
            "detail": _WRITE_BLOCK_DETAIL,
        },
    )
    nvr = case.add_evidence_item(
        description="Hikvision DS-7608NI-K2 hard disk image (warehouse floor + rear exit)",
        source_path="/evidence/hikvision_nvr_disk1.img",
        sha256=_synthetic_sha256("hikvision-nvr-disk1"),
        size_bytes=3_998_642_774_016,
        device_type="NVR",
        make_model="Hikvision DS-7608NI-K2",
        serial_number="DS7608-77FQ21",
        write_block_attestation={
            "path": r"\\.\PhysicalDrive3",
            "write_open_refused": True,
            "detail": _WRITE_BLOCK_DETAIL,
        },
    )
    evidence_item_ids = {"dvr": dvr.id, "nvr": nvr.id}
    clips: list[ClipRow] = []

    def add_clip(
        evidence_item_id: int, channel: int, kind: str, start_min: int, end_min: int,
        *,
        first_sequence: int | None = None,
        last_sequence: int | None = None,
        frame_count: int | None = None,
        sha256: str | None = None,
        format_id: str | None = None,
        note: str = "",
    ) -> ClipRow:
        clip = case.add_clip(
            evidence_item_id, channel=channel, kind=kind,
            start_time=_iso(start_min), end_time=_iso(end_min),
            first_sequence=first_sequence, last_sequence=last_sequence,
            frame_count=frame_count, sha256=sha256, format_id=format_id, note=note,
        )
        clips.append(clip)
        return clip

    # Channel 0 -- main entrance: recording is intact, then a gap right
    # before the break-in window, later explained by carved footage
    # whose sequence numbers still don't reconnect cleanly.
    add_clip(dvr.id, 0, SegmentKind.RECORDED.value, 0, 180, first_sequence=1, last_sequence=1080, format_id="dhav")
    recovered_entrance = add_clip(
        dvr.id, 0, SegmentKind.RECOVERED.value, 180, 192, frame_count=360,
        sha256=_synthetic_sha256("entrance-recovered-180-192"),
        note="Carved from unallocated space; no index entry backs this range.",
    )
    add_clip(dvr.id, 0, SegmentKind.RECORDED.value, 195, 360, first_sequence=1200, last_sequence=2160, format_id="dhav")

    # Channel 1 -- loading dock: fully intact throughout.
    add_clip(dvr.id, 1, SegmentKind.RECORDED.value, 0, 360, first_sequence=1, last_sequence=2160, format_id="dhav")

    # Channel 2 -- warehouse floor (NVR): a corrupted stretch, not a gap.
    add_clip(nvr.id, 2, SegmentKind.RECORDED.value, 0, 150, first_sequence=1, last_sequence=900, format_id="hikvision")
    corrupt_floor = add_clip(
        nvr.id, 2, SegmentKind.CORRUPT.value, 150, 175, frame_count=420,
        note="Header partially overwritten; frame count is a lower bound.",
    )
    add_clip(nvr.id, 2, SegmentKind.RECORDED.value, 175, 360, first_sequence=1150, last_sequence=2160, format_id="hikvision")

    # Channel 3 -- rear exit (NVR): a sequence discontinuity with no
    # carved footage filling it -- the payload itself, not just its
    # index entry, appears to be gone.
    add_clip(nvr.id, 3, SegmentKind.RECORDED.value, 0, 170, first_sequence=1, last_sequence=1020, format_id="hikvision")
    add_clip(nvr.id, 3, SegmentKind.RECORDED.value, 185, 360, first_sequence=1200, last_sequence=2160, format_id="hikvision")

    finding_ids = [
        case.add_finding(
            author=examiner_name, category="tamper_indicator",
            description=(
                "Channel 0 (main entrance) has a 12-minute gap beginning at "
                "01:03 UTC. No index entry covers this range, but footage "
                "was recovered by carving unallocated space. The recorder's "
                "own sequence counter jumps from 1080 to 1200 (expected "
                "1081), consistent with a deliberately deleted index entry "
                "whose payload was left in place -- not ordinary "
                "ring-buffer recycling."
            ),
            clip_id=recovered_entrance.id,
        ).id,
        case.add_finding(
            author=examiner_name, category="note",
            description=(
                "Channel 2 (warehouse floor) has a 25-minute corrupted "
                "segment. Frame count for this range is a lower bound; "
                "header damage prevented a full decode. Recommend "
                "re-attempting recovery with a byte-level carve once "
                "container-level parsing is exhausted."
            ),
            clip_id=corrupt_floor.id,
        ).id,
        case.add_finding(
            author=examiner_name, category="tamper_indicator",
            description=(
                "Channel 3 (rear exit) shows a 15-minute gap with a "
                "sequence discontinuity (1020 -> 1200, expected 1021) but "
                "no recovered footage in unallocated space -- consistent "
                "with the payload itself having been overwritten, not "
                "merely its index entry."
            ),
        ).id,
    ]

    return SeedResult(case=case, evidence_item_ids=evidence_item_ids, clips=clips, finding_ids=finding_ids)
