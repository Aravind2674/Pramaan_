"""
Tests for pramaan.report.case_report.

Like test_report_certificate.py, uses pypdf (dev-only) to extract text
back out of generated PDFs and verify real content is present, not just
that a nonzero-size file exists.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

from pramaan.case.store import Case
from pramaan.report.case_report import (
    CaseReportError,
    GapAnalysisWindow,
    generate_case_report_pdf,
)
from pramaan.timeline.model import SegmentKind


def _new_case(tmp_path, name="case.db") -> Case:
    return Case.create(
        tmp_path / name,
        case_id="SIH26150-CASE-1",
        title="Sample Investigation",
        investigating_agency="Cyber Cell",
        examiner_name="Dr. A. Examiner",
    )


def _extract_text(path) -> str:
    """Join every page's text into one whitespace-normalized string.

    A table cell's own text wraps onto multiple lines whenever content is
    wider than its column -- an intra-cell line break, not a semantic
    boundary -- so raw newlines from pypdf extraction are collapsed to
    single spaces rather than preserved literally; a multi-word assertion
    should not depend on exactly where a column happened to wrap.
    """
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(path).pages)


# ---------------------------------------------------------------------------
# GapAnalysisWindow validation
# ---------------------------------------------------------------------------

def test_gap_analysis_window_rejects_end_not_after_start():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(CaseReportError):
        GapAnalysisWindow(start=start, end=start)
    with pytest.raises(CaseReportError):
        GapAnalysisWindow(start=start, end=datetime(2025, 12, 31, tzinfo=UTC))


def test_gap_analysis_window_accepts_valid_range():
    GapAnalysisWindow(start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 2, tzinfo=UTC))


# ---------------------------------------------------------------------------
# Generation basics
# ---------------------------------------------------------------------------

def test_generate_raises_if_destination_already_exists(tmp_path):
    case = _new_case(tmp_path)
    dest = tmp_path / "report.pdf"
    dest.write_bytes(b"already here")
    with pytest.raises(CaseReportError):
        generate_case_report_pdf(case, dest)


def test_generate_creates_a_pdf_for_an_empty_case(tmp_path):
    """An empty case (no evidence, no clips, no findings) must still
    produce a real, valid document that says so honestly -- not crash,
    and not silently omit the sections."""
    case = _new_case(tmp_path)
    dest = tmp_path / "report.pdf"
    result = generate_case_report_pdf(case, dest)
    assert result == dest
    assert dest.exists()
    text = _extract_text(dest)
    assert "No evidence items have been recorded" in text
    assert "No clips have been recorded" in text
    assert "No findings have been recorded" in text


def test_empty_case_report_states_gap_analysis_was_skipped(tmp_path):
    case = _new_case(tmp_path)
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "Skipped" in text


def test_pdf_contains_case_summary_fields(tmp_path):
    case = _new_case(tmp_path)
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "SIH26150-CASE-1" in text
    assert "Sample Investigation" in text
    assert "Cyber Cell" in text
    assert "Dr. A. Examiner" in text


# ---------------------------------------------------------------------------
# Evidence items
# ---------------------------------------------------------------------------

def test_pdf_lists_evidence_items_with_hash_and_write_block_status(tmp_path):
    case = _new_case(tmp_path)
    case.add_evidence_item(
        description="Dahua XVR hard disk image",
        source_path="/evidence/disk1.img",
        sha256="a" * 64,
        size_bytes=1_000_000,
        device_type="DVR",
        make_model="Dahua XVR5108HS",
        write_block_attestation={"path": "/dev/sdb", "write_open_refused": True, "detail": "blocked"},
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "Dahua XVR hard disk image" in text
    assert "a" * 64 in text
    assert "DVR" in text
    assert "Write-open refused" in text


def test_pdf_shows_write_open_permitted_when_attestation_was_not_refused(tmp_path):
    case = _new_case(tmp_path)
    case.add_evidence_item(
        description="A working copy on an ordinary writable file",
        source_path="/evidence/copy.img",
        sha256="f" * 64,
        size_bytes=10,
        write_block_attestation={"path": "/evidence/copy.img", "write_open_refused": False, "detail": "permitted"},
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "Write-open permitted" in text


def test_pdf_shows_not_checked_for_missing_write_block_attestation(tmp_path):
    case = _new_case(tmp_path)
    case.add_evidence_item(
        description="Evidence with no write-block check",
        source_path="/evidence/disk2.img",
        sha256="b" * 64,
        size_bytes=500,
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "Not checked" in text


# ---------------------------------------------------------------------------
# Clips, coverage, and exhibit list
# ---------------------------------------------------------------------------

def _add_evidence(case: Case) -> int:
    item = case.add_evidence_item(
        description="Evidence item", source_path="/x.img", sha256="c" * 64, size_bytes=10,
    )
    return item.id


def test_pdf_shows_coverage_counts_per_channel_and_kind(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(evidence_id, channel=0, kind=SegmentKind.RECORDED.value,
                  start_time="2026-01-01T00:00:00", end_time="2026-01-01T01:00:00")
    case.add_clip(evidence_id, channel=0, kind=SegmentKind.RECOVERED.value,
                  start_time="2026-01-01T01:00:00", end_time="2026-01-01T02:00:00")
    case.add_clip(evidence_id, channel=1, kind=SegmentKind.RECORDED.value,
                  start_time="2026-01-01T00:00:00", end_time="2026-01-01T01:00:00")
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "Recorded (intact index)" in text
    assert "Recovered (carved)" in text


def test_pdf_exhibit_list_contains_clip_hash_and_times(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(
        evidence_id, channel=2, kind=SegmentKind.RECOVERED.value,
        start_time="2026-01-01T03:00:00", end_time="2026-01-01T03:30:00",
        sha256="deadbeef" * 8, frame_count=900,
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "deadbeef" * 8 in text
    assert "900" in text


def test_pdf_shows_a_clips_note_when_present(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(
        evidence_id, channel=0, kind=SegmentKind.CORRUPT.value,
        note="Header partially overwritten; frame count is a lower bound.",
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "Header partially overwritten" in text


def test_pdf_shows_unknown_for_clips_with_no_time_range(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(evidence_id, channel=0, kind=SegmentKind.CORRUPT.value)
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "unknown" in text


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def test_pdf_lists_findings_with_author_and_category(tmp_path):
    case = _new_case(tmp_path)
    case.add_finding(
        author="Dr. A. Examiner", category="tamper_indicator",
        description="Sequence discontinuity on channel 0 consistent with deliberate deletion.",
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "tamper_indicator" in text
    assert "Sequence discontinuity on channel 0" in text
    assert "Dr. A. Examiner" in text


def test_pdf_references_the_associated_clip_in_a_finding(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    clip = case.add_clip(evidence_id, channel=0, kind=SegmentKind.RECOVERED.value)
    case.add_finding(
        author="Dr. A. Examiner", category="note", description="See attached clip.", clip_id=clip.id,
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert f"clip {clip.id}" in text


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def test_gap_analysis_reports_no_anomalies_when_fully_covered(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(
        evidence_id, channel=0, kind=SegmentKind.RECORDED.value,
        start_time="2026-01-01T00:00:00+00:00", end_time="2026-01-01T02:00:00+00:00",
        first_sequence=1, last_sequence=100,
    )
    window = GapAnalysisWindow(
        start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC), end=datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest, gap_analysis_window=window)
    text = _extract_text(dest)
    assert "No anomalies were found" in text


def test_gap_analysis_reports_recovered_from_unallocated_anomaly(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(
        evidence_id, channel=0, kind=SegmentKind.RECOVERED.value,
        start_time="2026-01-01T00:00:00+00:00", end_time="2026-01-01T01:00:00+00:00",
    )
    window = GapAnalysisWindow(
        start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC), end=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest, gap_analysis_window=window)
    text = _extract_text(dest)
    assert "Recovered from unallocated space" in text


def test_gap_analysis_reports_sequence_discontinuity_anomaly(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(
        evidence_id, channel=0, kind=SegmentKind.RECORDED.value,
        start_time="2026-01-01T00:00:00+00:00", end_time="2026-01-01T01:00:00+00:00",
        first_sequence=1, last_sequence=10,
    )
    case.add_clip(
        evidence_id, channel=0, kind=SegmentKind.RECORDED.value,
        start_time="2026-01-01T02:00:00+00:00", end_time="2026-01-01T03:00:00+00:00",
        first_sequence=50, last_sequence=60,
    )
    window = GapAnalysisWindow(
        start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC), end=datetime(2026, 1, 1, 3, 0, tzinfo=UTC),
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest, gap_analysis_window=window)
    text = _extract_text(dest)
    assert "Sequence discontinuity" in text


def test_gap_analysis_with_no_timed_clips_states_analysis_is_unavailable(tmp_path):
    case = _new_case(tmp_path)
    window = GapAnalysisWindow(start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 2, tzinfo=UTC))
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest, gap_analysis_window=window)
    text = _extract_text(dest)
    assert "No timed clips are available" in text


# ---------------------------------------------------------------------------
# Integrity section
# ---------------------------------------------------------------------------

def test_pdf_shows_valid_chain_verification(tmp_path):
    case = _new_case(tmp_path)
    case.add_evidence_item(
        description="x", source_path="/x.img", sha256="d" * 64, size_bytes=1,
    )
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "VALID" in text
    assert case.ledger.head_hash in text


def test_pdf_shows_broken_chain_verification(tmp_path):
    case = _new_case(tmp_path)
    case.add_evidence_item(
        description="x", source_path="/x.img", sha256="e" * 64, size_bytes=1,
    )
    case.close()
    # Corrupt the ledger file directly to force a broken chain.
    ledger_path = tmp_path.joinpath("case.db.ledger.jsonl")
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    import json
    tampered = json.loads(lines[0])
    tampered["detail"] = {"tampered": True}
    lines[0] = json.dumps(tampered)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    case = Case(tmp_path / "case.db")
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "BROKEN" in text


# ---------------------------------------------------------------------------
# Custom generated_at
# ---------------------------------------------------------------------------

def test_pdf_uses_the_supplied_generated_at_timestamp(tmp_path):
    case = _new_case(tmp_path)
    dest = tmp_path / "report.pdf"
    fixed = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    generate_case_report_pdf(case, dest, generated_at=fixed)
    text = _extract_text(dest)
    assert fixed.isoformat() in text


def test_pdf_text_has_no_unicode_replacement_characters(tmp_path):
    case = _new_case(tmp_path)
    evidence_id = _add_evidence(case)
    case.add_clip(evidence_id, channel=0, kind=SegmentKind.RECORDED.value,
                  start_time="2026-01-01T00:00:00", end_time="2026-01-01T01:00:00")
    case.add_finding(author="Examiner", category="note", description="A finding.")
    dest = tmp_path / "report.pdf"
    generate_case_report_pdf(case, dest)
    text = _extract_text(dest)
    assert "�" not in text
