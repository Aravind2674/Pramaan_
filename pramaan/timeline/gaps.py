"""
Classifying what a Timeline's gaps and recovered segments actually mean.

Grounded in the three-way deletion taxonomy from Yoon & Hwang's Honeywell
surveillance-filesystem paper (see ``docs/sources.md``): a missing time
range is not one undifferentiated kind of finding. A gap at the oldest
edge of a recording, with nothing before it, looks nothing like a gap
sitting between two otherwise-contiguous recordings whose sequence
numbers jump — and a stretch of footage that exists only because it was
carved out of unallocated space is a different finding again from either.
Every classification here states the specific evidence behind it in
``rationale`` — an examiner or a court needs to see *why*, not just *what*.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pramaan.timeline.model import Segment, SegmentKind, Timeline


class AnomalyCategory(str, Enum):
    RECOVERED_FROM_UNALLOCATED = "recovered_from_unallocated"
    """Footage exists here only via carving — no index entry backs it."""

    EXPECTED_OVERWRITE = "expected_overwrite"
    """A gap at the oldest edge of the observed window, with nothing
    before it — consistent with ordinary ring-buffer recycling."""

    SEQUENCE_DISCONTINUITY = "sequence_discontinuity"
    """A gap between two RECORDED segments whose sequence numbers do not
    connect as expected — the recorder's own counter, not just the index,
    shows something happened here."""

    UNEXPLAINED_GAP = "unexplained_gap"
    """No recovered payload and no sequence evidence explains this gap
    either way. Reported honestly as unexplained rather than guessed at."""


@dataclass(frozen=True)
class Anomaly:
    channel: int
    start: datetime
    end: datetime
    category: AnomalyCategory
    rationale: tuple[str, ...]


def _segment_ending_at_or_before(segments: list[Segment], t: datetime) -> Segment | None:
    candidates = [s for s in segments if s.end <= t]
    return max(candidates, key=lambda s: s.end) if candidates else None


def _segment_starting_at_or_after(segments: list[Segment], t: datetime) -> Segment | None:
    candidates = [s for s in segments if s.start >= t]
    return min(candidates, key=lambda s: s.start) if candidates else None


def find_anomalies(
    timeline: Timeline, channel: int, window_start: datetime, window_end: datetime
) -> list[Anomaly]:
    """Every :class:`Anomaly` on ``channel`` within the observed window:
    each RECOVERED segment, and every gap not covered by any segment,
    classified with its supporting evidence.
    """
    anomalies: list[Anomaly] = []

    for seg in timeline.segments_for(channel):
        if seg.kind is SegmentKind.RECOVERED:
            anomalies.append(
                Anomaly(
                    channel=channel,
                    start=seg.start,
                    end=seg.end,
                    category=AnomalyCategory.RECOVERED_FROM_UNALLOCATED,
                    rationale=(
                        (
                            "this time range has no supporting index entry — the "
                            "video payload was recovered by carving unallocated "
                            "space, consistent with a deleted or cleared index "
                            "entry whose payload was left in place"
                        ),
                    ),
                )
            )

    recorded = sorted(
        (s for s in timeline.segments_for(channel) if s.kind is SegmentKind.RECORDED),
        key=lambda s: s.start,
    )

    for gap in timeline.gaps_for(channel, window_start, window_end):
        before = _segment_ending_at_or_before(recorded, gap.start)
        after = _segment_starting_at_or_after(recorded, gap.end)

        if before is None:
            anomalies.append(
                Anomaly(
                    channel=channel,
                    start=gap.start,
                    end=gap.end,
                    category=AnomalyCategory.EXPECTED_OVERWRITE,
                    rationale=(
                        (
                            "this gap sits at the oldest edge of the observed "
                            "window, with no recorded segment before it — "
                            "consistent with a ring buffer that has simply not "
                            "retained anything older, not a deletion"
                        ),
                    ),
                )
            )
            continue

        if (
            after is not None
            and before.last_sequence is not None
            and after.first_sequence is not None
        ):
            expected_next = before.last_sequence + 1
            if after.first_sequence != expected_next:
                anomalies.append(
                    Anomaly(
                        channel=channel,
                        start=gap.start,
                        end=gap.end,
                        category=AnomalyCategory.SEQUENCE_DISCONTINUITY,
                        rationale=(
                            (
                                f"the segment before this gap ends at sequence "
                                f"{before.last_sequence}; the segment after it "
                                f"begins at sequence {after.first_sequence}, not "
                                f"the expected {expected_next} — the recorder's "
                                "own sequence counter shows a discontinuity "
                                "here, not just an absence of index entries"
                            ),
                        ),
                    )
                )
                continue

        anomalies.append(
            Anomaly(
                channel=channel,
                start=gap.start,
                end=gap.end,
                category=AnomalyCategory.UNEXPLAINED_GAP,
                rationale=(
                    (
                        "no recovered payload fills this range, and no sequence "
                        "evidence explains it either way — reported as "
                        "unexplained rather than guessed at"
                    ),
                ),
            )
        )

    return sorted(anomalies, key=lambda a: a.start)
