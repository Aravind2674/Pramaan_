"""Tests for pramaan.recovery.extents."""

from __future__ import annotations

import pytest

from pramaan.recovery.extents import Extent, compute_gaps, merge_extents


def test_extent_length():
    assert Extent(10, 30).length == 20
    assert Extent(5, 5).length == 0


def test_extent_rejects_end_before_start():
    with pytest.raises(ValueError):
        Extent(10, 5)


def test_extent_overlaps():
    assert Extent(0, 10).overlaps(Extent(5, 15))
    assert Extent(5, 15).overlaps(Extent(0, 10))
    assert not Extent(0, 10).overlaps(Extent(10, 20))  # touching, not overlapping
    assert not Extent(0, 10).overlaps(Extent(20, 30))


def test_merge_extents_empty():
    assert merge_extents([]) == []


def test_merge_extents_single():
    assert merge_extents([Extent(5, 10)]) == [Extent(5, 10)]


def test_merge_extents_non_overlapping_stay_separate_and_sorted():
    result = merge_extents([Extent(20, 30), Extent(0, 10)])
    assert result == [Extent(0, 10), Extent(20, 30)]


def test_merge_extents_overlapping_are_combined():
    result = merge_extents([Extent(0, 10), Extent(5, 20)])
    assert result == [Extent(0, 20)]


def test_merge_extents_adjacent_are_combined():
    """Touching extents (a.end == b.start) must merge -- otherwise a
    zero-length phantom gap would appear between two index entries that
    describe genuinely back-to-back blocks."""
    result = merge_extents([Extent(0, 10), Extent(10, 20)])
    assert result == [Extent(0, 20)]


def test_merge_extents_chain_of_three():
    result = merge_extents([Extent(0, 5), Extent(4, 12), Extent(12, 20)])
    assert result == [Extent(0, 20)]


def test_merge_extents_fully_contained_extent_is_absorbed():
    result = merge_extents([Extent(0, 100), Extent(10, 20)])
    assert result == [Extent(0, 100)]


def test_compute_gaps_no_allocation_is_one_full_gap():
    assert compute_gaps(1000, []) == [Extent(0, 1000)]


def test_compute_gaps_fully_allocated_has_no_gaps():
    assert compute_gaps(1000, [Extent(0, 1000)]) == []


def test_compute_gaps_allocation_in_the_middle():
    gaps = compute_gaps(1000, [Extent(400, 600)])
    assert gaps == [Extent(0, 400), Extent(600, 1000)]


def test_compute_gaps_between_two_allocated_extents():
    gaps = compute_gaps(1000, [Extent(0, 100), Extent(900, 1000)])
    assert gaps == [Extent(100, 900)]


def test_compute_gaps_handles_overlapping_allocated_extents():
    gaps = compute_gaps(1000, [Extent(0, 500), Extent(300, 700)])
    assert gaps == [Extent(700, 1000)]


def test_compute_gaps_clips_extent_beyond_image_size():
    """A malformed or malicious index claiming bytes past the end of the
    image must be clipped, not crash the gap computation."""
    gaps = compute_gaps(100, [Extent(50, 500)])
    assert gaps == [Extent(0, 50)]


def test_compute_gaps_drops_extent_entirely_beyond_image():
    gaps = compute_gaps(100, [Extent(200, 300)])
    assert gaps == [Extent(0, 100)]


def test_compute_gaps_rejects_negative_image_size():
    with pytest.raises(ValueError):
        compute_gaps(-1, [])
