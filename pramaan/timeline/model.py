"""
Multi-channel timeline model: segments and gaps, addressed by channel and
wall-clock time rather than by disk offset.

This module knows nothing about profiles, clips, or disk images — it
takes typed ``(channel, start, end, kind)`` segments from whatever
produced them (an index walk, a carver run, a manual annotation) and
answers questions about coverage: what exists on a channel, and what time
ranges on that channel have no segment covering them at all.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class SegmentKind(str, Enum):
    """What kind of evidence a segment represents — an epistemic
    distinction, not just a status label. RECORDED and RECOVERED both mean
    "there is footage here"; they differ in how much the index vouches for
    it, which is exactly the distinction the recovery layer's two paths
    (:mod:`pramaan.recovery.index_walk` vs :mod:`pramaan.recovery.carver`)
    produce."""

    RECORDED = "recorded"
    """Confirmed via an intact filesystem/container index."""

    RECOVERED = "recovered"
    """Carved from space no index claims — payload verified present, no
    index metadata backs it."""

    CORRUPT = "corrupt"
    """Partially decodable; present but damaged."""

    UNKNOWN = "unknown"
    """Not yet parsed or characterized — distinct from confirmed absence."""


@dataclass(frozen=True)
class Segment:
    channel: int
    start: datetime
    end: datetime
    kind: SegmentKind
    first_sequence: int | None = None
    last_sequence: int | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"segment end {self.end} precedes start {self.start}")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: Segment) -> bool:
        return (
            self.channel == other.channel
            and self.start < other.end
            and other.start < self.end
        )


@dataclass(frozen=True)
class Gap:
    channel: int
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


class Timeline:
    """A read-only view over a fixed set of segments, organized per channel."""

    def __init__(self, segments: Iterable[Segment]) -> None:
        self._segments: tuple[Segment, ...] = tuple(
            sorted(segments, key=lambda s: (s.channel, s.start))
        )

    @property
    def segments(self) -> tuple[Segment, ...]:
        return self._segments

    @property
    def channels(self) -> tuple[int, ...]:
        return tuple(sorted({s.channel for s in self._segments}))

    def segments_for(self, channel: int) -> tuple[Segment, ...]:
        return tuple(s for s in self._segments if s.channel == channel)

    def overlapping_pairs(self, channel: int) -> list[tuple[Segment, Segment]]:
        """Every pair of segments on ``channel`` that overlap in time.

        Deliberately not resolved (merged, one preferred over the other)
        here — two different accounts of the same time range is itself a
        finding worth an examiner's attention, not something this model
        should paper over by picking a winner.
        """
        ordered = self.segments_for(channel)
        pairs = []
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                if ordered[i].overlaps(ordered[j]):
                    pairs.append((ordered[i], ordered[j]))
        return pairs

    def gaps_for(
        self, channel: int, window_start: datetime, window_end: datetime
    ) -> list[Gap]:
        """Time ranges within ``[window_start, window_end)`` not covered
        by any segment on ``channel``.

        Overlapping or adjacent segments are merged before gaps are
        computed, so a gap is only ever reported where genuinely nothing
        reaches — the same complement-of-coverage approach as
        :func:`pramaan.recovery.extents.compute_gaps`, over wall-clock
        time instead of byte offsets.
        """
        if window_end < window_start:
            raise ValueError("window_end precedes window_start")

        merged: list[tuple[datetime, datetime]] = []
        for seg in self.segments_for(channel):
            start = max(seg.start, window_start)
            end = min(seg.end, window_end)
            if end <= start:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        gaps: list[Gap] = []
        cursor = window_start
        for start, end in merged:
            if start > cursor:
                gaps.append(Gap(channel, cursor, start))
            cursor = max(cursor, end)
        if cursor < window_end:
            gaps.append(Gap(channel, cursor, window_end))
        return gaps
