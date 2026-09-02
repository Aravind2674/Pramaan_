"""Tests for pramaan.demo.seed."""

from __future__ import annotations

import pytest

from pramaan.api.workspace import CaseWorkspace, WorkspaceError
from pramaan.demo import DEFAULT_CASE_ID, seed_demo_case
from pramaan.timeline.gaps import AnomalyCategory, find_anomalies
from pramaan.timeline.model import SegmentKind


def test_seed_creates_two_evidence_items_and_nine_clips(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    assert set(result.evidence_item_ids) == {"dvr", "nvr"}
    assert len(result.case.list_evidence_items()) == 2
    assert len(result.clips) == 9
    assert len(result.case.list_clips()) == 9


def test_seed_records_three_findings(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    assert len(result.finding_ids) == 3
    assert len(result.case.list_findings()) == 3


def test_seed_produces_a_valid_ledger_chain(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    verification = result.case.verify_integrity()
    assert verification.valid is True
    assert verification.break_at_index is None


def test_seed_timeline_spans_all_four_channels(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    timeline = result.case.build_timeline()
    assert timeline.channels == (0, 1, 2, 3)


def test_seed_includes_every_segment_kind(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    kinds = {clip.kind for clip in result.clips}
    assert kinds == {
        SegmentKind.RECORDED.value,
        SegmentKind.RECOVERED.value,
        SegmentKind.CORRUPT.value,
    }


def test_seed_channel_0_has_a_recovered_from_unallocated_anomaly(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    timeline = result.case.build_timeline()
    segments = timeline.segments_for(0)
    window_start = min(s.start for s in segments)
    window_end = max(s.end for s in segments)
    anomalies = find_anomalies(timeline, 0, window_start, window_end)

    categories = {a.category for a in anomalies}
    assert AnomalyCategory.RECOVERED_FROM_UNALLOCATED in categories


def test_seed_channel_3_has_a_sequence_discontinuity(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)

    timeline = result.case.build_timeline()
    segments = timeline.segments_for(3)
    window_start = min(s.start for s in segments)
    window_end = max(s.end for s in segments)
    anomalies = find_anomalies(timeline, 3, window_start, window_end)

    categories = {a.category for a in anomalies}
    assert AnomalyCategory.SEQUENCE_DISCONTINUITY in categories


def test_seed_raises_if_the_case_id_already_exists(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    seed_demo_case(workspace)

    with pytest.raises(WorkspaceError):
        seed_demo_case(workspace)


def test_seed_hashes_are_deterministic_across_separate_workspaces(tmp_path):
    """The evidence hashes are real SHA-256 values over a fixed synthetic
    payload, not randomly generated -- re-seeding (even into a different
    workspace) must reproduce byte-identical hashes."""
    workspace_a = CaseWorkspace(tmp_path / "a")
    workspace_b = CaseWorkspace(tmp_path / "b")

    result_a = seed_demo_case(workspace_a, case_id="X")
    result_b = seed_demo_case(workspace_b, case_id="Y")

    dvr_a = result_a.case.get_evidence_item(result_a.evidence_item_ids["dvr"])
    dvr_b = result_b.case.get_evidence_item(result_b.evidence_item_ids["dvr"])
    assert dvr_a.sha256 == dvr_b.sha256
    assert len(dvr_a.sha256) == 64


def test_seed_uses_the_default_case_id_unless_overridden(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(workspace)
    assert result.case.info().case_id == DEFAULT_CASE_ID


def test_seed_accepts_custom_case_metadata(tmp_path):
    workspace = CaseWorkspace(tmp_path)
    result = seed_demo_case(
        workspace, case_id="CUSTOM-1", title="Custom Title",
        investigating_agency="Custom Agency", examiner_name="Custom Examiner",
    )
    info = result.case.info()
    assert info.case_id == "CUSTOM-1"
    assert info.title == "Custom Title"
    assert info.investigating_agency == "Custom Agency"
    assert info.examiner_name == "Custom Examiner"
