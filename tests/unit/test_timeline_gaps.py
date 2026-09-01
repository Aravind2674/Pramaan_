"""Tests for pramaan.timeline.gaps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pramaan.timeline.gaps import AnomalyCategory, find_anomalies
from pramaan.timeline.model import Segment, SegmentKind, Timeline

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _t(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _recorded(start: int, end: int, first_seq: int | None = None, last_seq: int | None = None) -> Segment:
    return Segment(
        channel=0, start=_t(start), end=_t(end), kind=SegmentKind.RECORDED,
        first_sequence=first_seq, last_sequence=last_seq,
    )


def _recovered(start: int, end: int) -> Segment:
    return Segment(channel=0, start=_t(start), end=_t(end), kind=SegmentKind.RECOVERED)


def test_recovered_segment_is_flagged_as_recovered_from_unallocated():
    tl = Timeline([_recovered(10, 20)])
    anomalies = find_anomalies(tl, 0, _t(0), _t(30))
    recovered = [a for a in anomalies if a.category is AnomalyCategory.RECOVERED_FROM_UNALLOCATED]
    assert len(recovered) == 1
    assert recovered[0].start == _t(10)
    assert recovered[0].end == _t(20)
    assert "carving" in recovered[0].rationale[0]


def test_leading_gap_with_nothing_before_is_expected_overwrite():
    tl = Timeline([_recorded(30, 60)])
    anomalies = find_anomalies(tl, 0, _t(0), _t(60))
    assert len(anomalies) == 1
    assert anomalies[0].category is AnomalyCategory.EXPECTED_OVERWRITE
    assert anomalies[0].start == _t(0)
    assert anomalies[0].end == _t(30)


def test_gap_with_sequence_discontinuity_is_flagged():
    before = _recorded(0, 20, first_seq=0, last_seq=10)
    after = _recorded(30, 50, first_seq=50, last_seq=60)  # expected 11, got 50
    tl = Timeline([before, after])
    anomalies = find_anomalies(tl, 0, _t(0), _t(50))

    gap_anomalies = [a for a in anomalies if a.category is not AnomalyCategory.RECOVERED_FROM_UNALLOCATED]
    assert len(gap_anomalies) == 1
    assert gap_anomalies[0].category is AnomalyCategory.SEQUENCE_DISCONTINUITY
    assert "11" in gap_anomalies[0].rationale[0]
    assert "50" in gap_anomalies[0].rationale[0]


def test_gap_with_contiguous_sequence_is_unexplained_not_discontinuity():
    """Sequence numbers connecting perfectly doesn't explain a TIME gap on
    its own -- the block/frame counter looking normal is a different fact
    from why there's a hole in the timeline, so this must not be silently
    treated as resolved."""
    before = _recorded(0, 20, first_seq=0, last_seq=10)
    after = _recorded(30, 50, first_seq=11, last_seq=20)  # perfectly contiguous
    tl = Timeline([before, after])
    anomalies = find_anomalies(tl, 0, _t(0), _t(50))

    assert len(anomalies) == 1
    assert anomalies[0].category is AnomalyCategory.UNEXPLAINED_GAP


def test_gap_with_no_sequence_info_is_unexplained():
    before = _recorded(0, 20)  # no sequence numbers at all
    after = _recorded(30, 50)
    tl = Timeline([before, after])
    anomalies = find_anomalies(tl, 0, _t(0), _t(50))

    assert len(anomalies) == 1
    assert anomalies[0].category is AnomalyCategory.UNEXPLAINED_GAP


def test_fully_covered_timeline_has_no_anomalies():
    tl = Timeline([_recorded(0, 60, first_seq=0, last_seq=100)])
    assert find_anomalies(tl, 0, _t(0), _t(60)) == []


def test_anomalies_are_sorted_by_start_time():
    tl = Timeline([
        _recorded(40, 60, first_seq=0, last_seq=1),
        _recovered(10, 20),
    ])
    anomalies = find_anomalies(tl, 0, _t(0), _t(60))
    assert [a.start for a in anomalies] == sorted(a.start for a in anomalies)


def test_find_anomalies_ignores_other_channels():
    other_channel_gap_segment = Segment(
        channel=1, start=_t(0), end=_t(30), kind=SegmentKind.RECORDED
    )
    tl = Timeline([other_channel_gap_segment])
    # Channel 0 has nothing at all -> one EXPECTED_OVERWRITE gap covering
    # the whole window, not influenced by channel 1's coverage.
    anomalies = find_anomalies(tl, 0, _t(0), _t(30))
    assert len(anomalies) == 1
    assert anomalies[0].channel == 0
