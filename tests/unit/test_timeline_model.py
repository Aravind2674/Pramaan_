"""Tests for pramaan.timeline.model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pramaan.timeline.model import Gap, Segment, SegmentKind, Timeline

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _t(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _seg(channel: int, start: int, end: int, kind: SegmentKind = SegmentKind.RECORDED) -> Segment:
    return Segment(channel=channel, start=_t(start), end=_t(end), kind=kind)


def test_segment_rejects_end_before_start():
    with pytest.raises(ValueError):
        Segment(channel=0, start=_t(10), end=_t(5), kind=SegmentKind.RECORDED)


def test_segment_duration():
    seg = _seg(0, 0, 30)
    assert seg.duration == timedelta(minutes=30)


def test_gap_duration():
    gap = Gap(channel=0, start=_t(0), end=_t(15))
    assert gap.duration == timedelta(minutes=15)


def test_segment_overlaps_same_channel():
    a = _seg(0, 0, 10)
    b = _seg(0, 5, 15)
    assert a.overlaps(b)
    assert b.overlaps(a)


def test_segment_does_not_overlap_touching_segments():
    a = _seg(0, 0, 10)
    b = _seg(0, 10, 20)
    assert not a.overlaps(b)


def test_segment_does_not_overlap_different_channels():
    a = _seg(0, 0, 10)
    b = _seg(1, 0, 10)
    assert not a.overlaps(b)


def test_timeline_channels_and_segments_for():
    tl = Timeline([_seg(0, 0, 10), _seg(1, 0, 10), _seg(0, 20, 30)])
    assert tl.channels == (0, 1)
    assert len(tl.segments_for(0)) == 2
    assert len(tl.segments_for(1)) == 1
    assert tl.segments_for(2) == ()


def test_timeline_segments_are_sorted_by_channel_then_start():
    tl = Timeline([_seg(1, 10, 20), _seg(0, 20, 30), _seg(0, 0, 10)])
    assert [(s.channel, s.start) for s in tl.segments] == [
        (0, _t(0)), (0, _t(20)), (1, _t(10)),
    ]


def test_gaps_for_no_segments_is_one_full_gap():
    tl = Timeline([])
    gaps = tl.gaps_for(0, _t(0), _t(60))
    assert len(gaps) == 1
    assert gaps[0].start == _t(0)
    assert gaps[0].end == _t(60)


def test_gaps_for_fully_covered_window_has_no_gaps():
    tl = Timeline([_seg(0, 0, 60)])
    assert tl.gaps_for(0, _t(0), _t(60)) == []


def test_gaps_for_coverage_in_the_middle():
    tl = Timeline([_seg(0, 20, 40)])
    gaps = tl.gaps_for(0, _t(0), _t(60))
    assert [(g.start, g.end) for g in gaps] == [(_t(0), _t(20)), (_t(40), _t(60))]


def test_gaps_for_merges_overlapping_segments_before_computing_gaps():
    tl = Timeline([_seg(0, 0, 20), _seg(0, 10, 30)])
    assert tl.gaps_for(0, _t(0), _t(60)) == [Gap(0, _t(30), _t(60))]


def test_gaps_for_merges_adjacent_touching_segments_no_phantom_gap():
    tl = Timeline([_seg(0, 0, 20), _seg(0, 20, 40)])
    gaps = tl.gaps_for(0, _t(0), _t(60))
    assert [(g.start, g.end) for g in gaps] == [(_t(40), _t(60))]


def test_gaps_for_clips_segments_partially_outside_window():
    tl = Timeline([_seg(0, -10, 10)])  # starts before the window
    gaps = tl.gaps_for(0, _t(0), _t(30))
    assert [(g.start, g.end) for g in gaps] == [(_t(10), _t(30))]


def test_gaps_for_ignores_segments_entirely_outside_the_window():
    # One segment well before the window, one well after -- both should
    # be dropped entirely rather than clipped to a zero-or-negative span.
    tl = Timeline([_seg(0, -100, -50), _seg(0, 100, 150)])
    gaps = tl.gaps_for(0, _t(0), _t(30))
    assert [(g.start, g.end) for g in gaps] == [(_t(0), _t(30))]


def test_gaps_for_ignores_other_channels():
    tl = Timeline([_seg(1, 0, 60)])  # fully covers channel 1, not channel 0
    gaps = tl.gaps_for(0, _t(0), _t(60))
    assert len(gaps) == 1


def test_gaps_for_rejects_inverted_window():
    tl = Timeline([])
    with pytest.raises(ValueError):
        tl.gaps_for(0, _t(60), _t(0))


def test_overlapping_pairs_detects_overlap_on_same_channel():
    a, b, c = _seg(0, 0, 10), _seg(0, 5, 15), _seg(0, 20, 30)
    tl = Timeline([a, b, c])
    pairs = tl.overlapping_pairs(0)
    assert len(pairs) == 1
    assert set(pairs[0]) == {a, b}


def test_overlapping_pairs_empty_when_no_overlap():
    tl = Timeline([_seg(0, 0, 10), _seg(0, 10, 20)])
    assert tl.overlapping_pairs(0) == []


def test_overlapping_pairs_ignores_other_channels():
    tl = Timeline([_seg(0, 0, 10), _seg(1, 0, 10)])
    assert tl.overlapping_pairs(0) == []
