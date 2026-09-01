"""Tests for pramaan.case.store."""

from __future__ import annotations

import pytest

from pramaan.case.store import Case, CaseError
from pramaan.recovery.carver import CarvedClip
from pramaan.recovery.index_walk import ClipRecord as IndexWalkClipRecord
from pramaan.timeline.model import SegmentKind


def _create_case(tmp_path, name="case.db"):
    return Case.create(
        tmp_path / name,
        case_id="SIH26150-001",
        title="Test case",
        investigating_agency="NTRO",
        examiner_name="A. Examiner",
    )


def test_create_sets_case_info(tmp_path):
    with _create_case(tmp_path) as case:
        info = case.info()
        assert info.case_id == "SIH26150-001"
        assert info.title == "Test case"
        assert info.investigating_agency == "NTRO"
        assert info.examiner_name == "A. Examiner"
        assert info.created_at


def test_create_raises_if_file_already_exists(tmp_path):
    path = tmp_path / "case.db"
    Case.create(path, case_id="c1", title="t", investigating_agency="a", examiner_name="e").close()
    with pytest.raises(CaseError):
        Case.create(path, case_id="c2", title="t2", investigating_agency="a2", examiner_name="e2")


def test_plain_constructor_rejects_a_path_that_does_not_exist(tmp_path):
    with pytest.raises(CaseError, match="Case.create"):
        Case(tmp_path / "does_not_exist.db")


def test_plain_constructor_opens_an_existing_case(tmp_path):
    path = tmp_path / "case.db"
    _create_case(tmp_path, "case.db").close()
    with Case(path) as reopened:
        assert reopened.info().case_id == "SIH26150-001"


def test_add_and_get_evidence_item_round_trips(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(
            description="Seized DVR hard disk",
            source_path="/evidence/disk001.dd",
            sha256="a" * 64,
            size_bytes=1_000_000,
            device_type="DVR",
            make_model="Dahua XVR",
            serial_number="SN12345",
            write_block_attestation={"path": "/dev/sdb", "write_open_refused": True, "detail": "blocked"},
        )
        fetched = case.get_evidence_item(item.id)
        assert fetched == item
        assert fetched.device_type == "DVR"
        assert fetched.write_block_attestation == {
            "path": "/dev/sdb", "write_open_refused": True, "detail": "blocked",
        }


def test_evidence_item_optional_fields_default_to_none(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(
            description="minimal item", source_path="/x", sha256="b" * 64, size_bytes=1,
        )
        assert item.device_type is None
        assert item.make_model is None
        assert item.write_block_attestation is None


def test_get_evidence_item_missing_raises(tmp_path):
    with _create_case(tmp_path) as case, pytest.raises(CaseError):
        case.get_evidence_item(999)


def test_list_evidence_items_returns_all_in_order(tmp_path):
    with _create_case(tmp_path) as case:
        a = case.add_evidence_item(description="first", source_path="/a", sha256="a" * 64, size_bytes=1)
        b = case.add_evidence_item(description="second", source_path="/b", sha256="b" * 64, size_bytes=1)
        items = case.list_evidence_items()
        assert [i.id for i in items] == [a.id, b.id]


def test_add_clip_rejects_invalid_kind(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        with pytest.raises(CaseError):
            case.add_clip(item.id, channel=0, kind="not-a-real-kind")


def test_add_clip_rejects_unknown_evidence_item(tmp_path):
    with _create_case(tmp_path) as case, pytest.raises(CaseError):
        case.add_clip(999, channel=0, kind=SegmentKind.RECORDED.value)


def test_add_and_list_clips(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        clip0 = case.add_clip(item.id, channel=0, kind=SegmentKind.RECORDED.value, start_offset=0, end_offset=100)
        clip1 = case.add_clip(item.id, channel=1, kind=SegmentKind.RECOVERED.value, start_offset=200, end_offset=300)

        all_clips = case.list_clips()
        assert {c.id for c in all_clips} == {clip0.id, clip1.id}

        channel0_clips = case.list_clips(channel=0)
        assert [c.id for c in channel0_clips] == [clip0.id]

        by_item = case.list_clips(evidence_item_id=item.id)
        assert len(by_item) == 2


def test_record_index_walk_clip_converts_fields_correctly(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        source = IndexWalkClipRecord(
            channel=2, start_offset=0, end_offset=1000, frame_count=10,
            first_sequence=0, last_sequence=9, format_id="dahua_dhav_chunk",
        )
        stored = case.record_index_walk_clip(item.id, source)
        assert stored.channel == 2
        assert stored.kind == SegmentKind.RECORDED.value
        assert stored.first_sequence == 0
        assert stored.last_sequence == 9
        assert stored.format_id == "dahua_dhav_chunk"


def test_record_carved_clip_requires_explicit_channel(tmp_path):
    """Carving never determines its own channel -- the case store must not
    silently invent one; the caller supplies it explicitly."""
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        source = CarvedClip(start_offset=500, end_offset=2000, frame_count=5, sha256="c" * 64)
        stored = case.record_carved_clip(item.id, 3, source)
        assert stored.channel == 3
        assert stored.kind == SegmentKind.RECOVERED.value
        assert stored.sha256 == "c" * 64
        assert stored.first_sequence is None  # carving never has sequence info


def test_set_clip_time_range_updates_and_returns_clip(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        clip = case.add_clip(item.id, channel=0, kind=SegmentKind.RECORDED.value)
        updated = case.set_clip_time_range(
            clip.id, "2026-01-01T00:00:00+00:00", "2026-01-01T00:05:00+00:00"
        )
        assert updated.start_time == "2026-01-01T00:00:00+00:00"
        assert updated.end_time == "2026-01-01T00:05:00+00:00"


def test_set_clip_time_range_missing_clip_raises(tmp_path):
    with _create_case(tmp_path) as case, pytest.raises(CaseError):
        case.set_clip_time_range(999, "2026-01-01T00:00:00+00:00", "2026-01-01T00:01:00+00:00")


def test_add_finding_with_and_without_clip(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        clip = case.add_clip(item.id, channel=0, kind=SegmentKind.RECORDED.value)

        f1 = case.add_finding(author="examiner", category="tamper", description="gap noted", clip_id=clip.id)
        f2 = case.add_finding(author="examiner", category="general", description="case opened")

        findings = case.list_findings()
        assert {f.id for f in findings} == {f1.id, f2.id}
        assert f1.clip_id == clip.id
        assert f2.clip_id is None


def test_add_finding_with_unknown_clip_raises(tmp_path):
    with _create_case(tmp_path) as case, pytest.raises(CaseError):
        case.add_finding(author="e", category="c", description="d", clip_id=999)


def test_get_finding_round_trips(tmp_path):
    with _create_case(tmp_path) as case:
        created = case.add_finding(author="e", category="c", description="d")
        assert case.get_finding(created.id) == created


def test_get_finding_missing_raises(tmp_path):
    with _create_case(tmp_path) as case, pytest.raises(CaseError):
        case.get_finding(999)


def test_info_on_a_case_file_with_no_case_info_row_raises(tmp_path):
    """A case file opened via the plain constructor is only required to
    exist, not to have been fully initialized by Case.create() -- an
    external tool (or a bug) could produce a database with the schema but
    no case_info row, and info() must fail clearly rather than return a
    row of Nones."""
    import sqlite3

    path = tmp_path / "malformed.db"
    conn = sqlite3.connect(path)
    conn.close()  # a valid, empty SQLite file, but with none of our tables yet

    case = Case(path)
    try:
        with pytest.raises(CaseError, match="Case.create"):
            case.info()
    finally:
        case.close()


def test_build_timeline_excludes_clips_without_a_time_range(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        no_time = case.add_clip(item.id, channel=0, kind=SegmentKind.RECOVERED.value)
        case.set_clip_time_range(
            case.add_clip(item.id, channel=0, kind=SegmentKind.RECORDED.value).id,
            "2026-01-01T00:00:00+00:00", "2026-01-01T00:10:00+00:00",
        )

        timeline = case.build_timeline()
        assert len(timeline.segments) == 1
        assert timeline.segments[0].kind is SegmentKind.RECORDED
        assert no_time.start_time is None  # sanity: this clip really had none


def test_build_timeline_preserves_channel_and_kind(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        clip = case.add_clip(
            item.id, channel=5, kind=SegmentKind.RECOVERED.value,
            first_sequence=1, last_sequence=2,
        )
        case.set_clip_time_range(clip.id, "2026-06-01T00:00:00+00:00", "2026-06-01T00:01:00+00:00")

        timeline = case.build_timeline()
        assert timeline.channels == (5,)
        seg = timeline.segments[0]
        assert seg.kind is SegmentKind.RECOVERED
        assert seg.first_sequence == 1
        assert seg.last_sequence == 2


# ---------------------------------------------------------------------------
# Ledger integration -- every mutation must actually be recorded
# ---------------------------------------------------------------------------

def test_every_mutating_action_is_recorded_in_the_ledger(tmp_path):
    with _create_case(tmp_path) as case:
        item = case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        clip = case.add_clip(item.id, channel=0, kind=SegmentKind.RECORDED.value)
        case.set_clip_time_range(clip.id, "2026-01-01T00:00:00+00:00", "2026-01-01T00:01:00+00:00")
        case.add_finding(author="e", category="c", description="d", clip_id=clip.id)

        actions = [e.action for e in case.ledger.entries]
        assert actions == [
            "create_case", "add_evidence_item", "add_clip",
            "set_clip_time_range", "add_finding",
        ]


def test_verify_integrity_reports_valid_for_an_untampered_case(tmp_path):
    with _create_case(tmp_path) as case:
        case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        result = case.verify_integrity()
        assert result.valid is True


def test_ledger_actor_defaults_to_the_case_examiner(tmp_path):
    with _create_case(tmp_path) as case:
        case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
        entry = case.ledger.entries[-1]
        assert entry.actor == "A. Examiner"


def test_ledger_actor_can_be_overridden_per_action(tmp_path):
    with _create_case(tmp_path) as case:
        case.add_evidence_item(
            description="d", source_path="/a", sha256="a" * 64, size_bytes=1, actor="different-examiner",
        )
        entry = case.ledger.entries[-1]
        assert entry.actor == "different-examiner"


def test_ledger_file_created_alongside_the_case_file(tmp_path):
    with _create_case(tmp_path, "case.db"):
        pass
    assert (tmp_path / "case.db.ledger.jsonl").exists()


def test_reopening_a_case_preserves_the_ledger_chain(tmp_path):
    path = tmp_path / "case.db"
    case = _create_case(tmp_path, "case.db")
    case.add_evidence_item(description="d", source_path="/a", sha256="a" * 64, size_bytes=1)
    case.close()

    reopened = Case(path)
    reopened.add_clip(1, channel=0, kind=SegmentKind.RECORDED.value)
    assert len(reopened.ledger.entries) == 3  # create_case, add_evidence_item, add_clip
    assert reopened.verify_integrity().valid is True
    reopened.close()
