"""Tests for pramaan.timeline.clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pramaan.timeline.clock import ClockAnchor, ClockError, estimate_drift

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _synthetic_anchors(
    n: int, slope: float, offset_seconds: float, step_seconds: float = 3600.0
) -> list[ClockAnchor]:
    """Ground-truth anchors for a recorder clock that runs at `slope` times
    real speed, with a fixed `offset_seconds`, sampled every `step_seconds`
    of recorder time."""
    anchors = []
    for i in range(n):
        recorder_time = T0 + timedelta(seconds=i * step_seconds)
        elapsed = i * step_seconds
        true_time = T0 + timedelta(seconds=slope * elapsed + offset_seconds)
        anchors.append(ClockAnchor(recorder_time, true_time, source="synthetic"))
    return anchors


def test_estimate_drift_requires_at_least_two_anchors():
    with pytest.raises(ClockError):
        estimate_drift([])
    with pytest.raises(ClockError):
        estimate_drift([ClockAnchor(T0, T0, "x")])


def test_pure_fixed_offset_no_drift():
    anchors = _synthetic_anchors(n=5, slope=1.0, offset_seconds=-10.0)
    estimate = estimate_drift(anchors)
    assert estimate.drift_slope == pytest.approx(1.0, abs=1e-9)
    assert estimate.offset_seconds == pytest.approx(-10.0, abs=1e-6)
    assert estimate.drift_rate_ppm == pytest.approx(0.0, abs=1e-3)


def test_known_drift_rate_is_recovered():
    # Recorder clock runs 100 ppm fast: slope = 1 + 100e-6
    true_slope = 1.0 + 100e-6
    anchors = _synthetic_anchors(n=6, slope=true_slope, offset_seconds=5.0, step_seconds=3600)
    estimate = estimate_drift(anchors)
    assert estimate.drift_slope == pytest.approx(true_slope, abs=1e-9)
    assert estimate.drift_rate_ppm == pytest.approx(100.0, abs=1e-3)
    assert estimate.offset_seconds == pytest.approx(5.0, abs=1e-6)


def test_theil_sen_tolerates_one_outlier_anchor():
    """The property that justifies choosing Theil-Sen over ordinary least
    squares: a single badly-wrong anchor among several good ones should
    barely move the estimate, not dominate it."""
    good_anchors = _synthetic_anchors(n=7, slope=1.0, offset_seconds=0.0, step_seconds=3600)
    # Corrupt one anchor's true_time by a large, implausible amount (a
    # misread OSD timestamp, say).
    bad = good_anchors[3]
    corrupted = ClockAnchor(bad.recorder_time, bad.true_time + timedelta(hours=5), bad.source)
    anchors_with_outlier = good_anchors[:3] + [corrupted] + good_anchors[4:]

    estimate = estimate_drift(anchors_with_outlier)
    # With no outlier, slope would be exactly 1.0 and offset exactly 0.0.
    # Theil-Sen should stay close to that despite the one bad point.
    assert estimate.drift_slope == pytest.approx(1.0, abs=0.01)
    assert abs(estimate.offset_seconds) < 60.0  # nowhere near the ~5 hour corruption


def test_ordinary_least_squares_would_have_been_dragged_by_the_same_outlier():
    """Not testing pramaan's own code here -- confirming the premise the
    Theil-Sen choice rests on, so this test would fail loudly if that
    premise ever stopped being true (e.g. a rewrite that quietly swapped
    the estimator)."""
    import numpy as np

    good_anchors = _synthetic_anchors(n=7, slope=1.0, offset_seconds=0.0, step_seconds=3600)
    bad = good_anchors[3]
    corrupted = ClockAnchor(bad.recorder_time, bad.true_time + timedelta(hours=5), bad.source)
    anchors = good_anchors[:3] + [corrupted] + good_anchors[4:]

    x = np.array([(a.recorder_time - T0).total_seconds() for a in anchors])
    y = np.array([(a.true_time - T0).total_seconds() for a in anchors])
    _ols_slope, ols_intercept = np.polyfit(x, y, 1)

    # The single 5-hour (18000s) corruption should move an OLS fit's
    # intercept far more than the 60-second tolerance Theil-Sen meets above.
    assert abs(ols_intercept) > 500.0


def test_correct_applies_offset_and_drift():
    true_slope = 1.0 + 200e-6
    anchors = _synthetic_anchors(n=5, slope=true_slope, offset_seconds=10.0, step_seconds=3600)
    estimate = estimate_drift(anchors)

    # A reading far beyond the anchors should still correct consistently
    # with the fitted model, not just interpolate between sampled points.
    reading = anchors[0].recorder_time + timedelta(seconds=36000)
    corrected = estimate.correct(reading)
    expected_elapsed = true_slope * 36000 + 10.0
    expected = anchors[0].recorder_time + timedelta(seconds=expected_elapsed)
    assert abs((corrected - expected).total_seconds()) < 1e-3


def test_correct_at_reference_time_is_just_the_offset():
    anchors = _synthetic_anchors(n=4, slope=1.0, offset_seconds=42.0, step_seconds=1800)
    estimate = estimate_drift(anchors)
    corrected = estimate.correct(estimate.reference_recorder_time)
    assert (corrected - estimate.reference_recorder_time).total_seconds() == pytest.approx(42.0, abs=1e-6)


def test_all_anchors_sharing_recorder_time_raises():
    anchors = [
        ClockAnchor(T0, T0, "a"),
        ClockAnchor(T0, T0 + timedelta(seconds=5), "b"),
        ClockAnchor(T0, T0 + timedelta(seconds=10), "c"),
    ]
    with pytest.raises(ClockError):
        estimate_drift(anchors)


def test_mixed_naive_and_aware_datetimes_raises():
    # Naive datetimes are deliberate here -- this test exists specifically
    # to prove estimate_drift rejects mixing them with aware ones.
    naive_anchor = ClockAnchor(
        datetime(2026, 1, 1),  # noqa: DTZ001
        datetime(2026, 1, 1),  # noqa: DTZ001
        "naive",
    )
    aware_anchor = ClockAnchor(T0, T0, "aware")
    with pytest.raises(ClockError):
        estimate_drift([naive_anchor, aware_anchor])


def test_residuals_count_matches_anchor_count():
    anchors = _synthetic_anchors(n=6, slope=1.0001, offset_seconds=1.0)
    estimate = estimate_drift(anchors)
    assert len(estimate.residuals_seconds) == 6
    assert estimate.anchor_count == 6


def test_confidence_interval_is_ordered():
    anchors = _synthetic_anchors(n=8, slope=1.00005, offset_seconds=-3.0)
    estimate = estimate_drift(anchors)
    low, high = estimate.confidence_interval_seconds
    assert low <= high


def test_two_anchors_gives_an_exact_fit_with_zero_width_interval():
    anchors = _synthetic_anchors(n=2, slope=1.0002, offset_seconds=7.0, step_seconds=7200)
    estimate = estimate_drift(anchors)
    low, high = estimate.confidence_interval_seconds
    assert low == pytest.approx(0.0, abs=1e-9)
    assert high == pytest.approx(0.0, abs=1e-9)


def test_anchors_do_not_need_to_be_pre_sorted():
    anchors = _synthetic_anchors(n=5, slope=1.0, offset_seconds=3.0)
    shuffled = [anchors[2], anchors[0], anchors[4], anchors[1], anchors[3]]
    ordered_estimate = estimate_drift(anchors)
    shuffled_estimate = estimate_drift(shuffled)
    assert shuffled_estimate.drift_slope == pytest.approx(ordered_estimate.drift_slope)
    assert shuffled_estimate.offset_seconds == pytest.approx(ordered_estimate.offset_seconds)
