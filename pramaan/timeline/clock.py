"""
Clock-drift estimation: fitting a recorder's own clock against
independently-verified true-time anchors.

Theil-Sen regression (the median of every pairwise slope between anchors)
rather than ordinary least squares, specifically because a bad anchor — a
misread OSD timestamp, a stale NTP record — is exactly the kind of input
this has to tolerate rather than be wrecked by. A median-based estimator
keeps working with up to roughly half the anchors wrong; a single bad
point can drag a least-squares fit arbitrarily far in the wrong direction.
No new dependency for this: the pairwise-median computation is a direct,
checkable translation of the definition, not an algorithm that benefits
from a library's optimized (and less inspectable) implementation at the
anchor counts this tool deals with.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np


class ClockError(Exception):
    """Raised when a drift estimate cannot be computed from the given anchors."""


@dataclass(frozen=True)
class ClockAnchor:
    """One point where the recorder's own clock reading and an
    independently-verified true time are both known for the same instant.

    ``source`` records where ``true_time`` came from (e.g. ``"osd_ocr"``,
    ``"ntp_config"``, ``"manual"``) — purely descriptive here, but a report
    built on a :class:`DriftEstimate` should be able to say what grounded
    it, not just present a number.
    """

    recorder_time: datetime
    true_time: datetime
    source: str


@dataclass(frozen=True)
class DriftEstimate:
    reference_recorder_time: datetime
    offset_seconds: float
    drift_slope: float
    drift_rate_ppm: float
    confidence_interval_seconds: tuple[float, float]
    anchor_count: int
    residuals_seconds: tuple[float, ...]

    def correct(self, recorder_reading: datetime) -> datetime:
        """Estimate the true time corresponding to a recorder-clock
        reading, applying both the fitted offset and drift rate — not
        just the offset, which alone is only exact at
        ``reference_recorder_time`` itself.
        """
        elapsed = (recorder_reading - self.reference_recorder_time).total_seconds()
        corrected_elapsed = self.drift_slope * elapsed + self.offset_seconds
        return self.reference_recorder_time + timedelta(seconds=corrected_elapsed)


def estimate_drift(anchors: list[ClockAnchor]) -> DriftEstimate:
    """Fit a drift model from ``anchors`` via Theil-Sen regression.

    At least 2 anchors are required to fit a line at all; at least 3 are
    needed for the median-of-slopes to actually reject an outlier rather
    than just average two points. ``confidence_interval_seconds`` is the
    5th-to-95th percentile of the fit's residuals — an honest description
    of how well the anchors agree with the fitted line, not a formal
    statistical confidence interval requiring assumptions this dataset is
    usually too small to justify.
    """
    if len(anchors) < 2:
        raise ClockError("at least 2 anchors are required to estimate clock drift")

    aware_states = {a.recorder_time.tzinfo is not None for a in anchors} | {
        a.true_time.tzinfo is not None for a in anchors
    }
    if len(aware_states) > 1:
        raise ClockError(
            "anchors mix timezone-aware and timezone-naive datetimes — "
            "use one consistently, preferably UTC-aware"
        )

    ordered = sorted(anchors, key=lambda a: a.recorder_time)
    t0 = ordered[0].recorder_time
    x = np.array([(a.recorder_time - t0).total_seconds() for a in ordered])
    y = np.array([(a.true_time - t0).total_seconds() for a in ordered])

    n = len(x)
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i in range(n)
        for j in range(i + 1, n)
        if x[j] != x[i]
    ]
    if not slopes:
        raise ClockError(
            "every anchor shares the same recorder_time — cannot fit a slope"
        )

    slope = float(np.median(slopes))
    intercept = float(np.median(y - slope * x))
    residuals = y - (slope * x + intercept)
    ci = (float(np.percentile(residuals, 5)), float(np.percentile(residuals, 95)))

    return DriftEstimate(
        reference_recorder_time=t0,
        offset_seconds=intercept,
        drift_slope=slope,
        drift_rate_ppm=(slope - 1.0) * 1_000_000,
        confidence_interval_seconds=ci,
        anchor_count=n,
        residuals_seconds=tuple(residuals.tolist()),
    )
