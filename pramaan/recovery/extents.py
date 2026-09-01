"""
Extent bookkeeping: turning "here is everything the index claims" into
"here is everything it doesn't" — the input the carver needs.

Deliberately its own tiny module rather than folded into the carver: the
gap-complement computation is pure interval arithmetic with no forensic
domain logic in it at all, and keeping it that way makes it trivial to unit
test exhaustively.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Extent:
    """A byte range ``[start, end)`` — half-open, like a Python slice."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"extent end {self.end} precedes start {self.start}")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: Extent) -> bool:
        return self.start < other.end and other.start < self.end


def merge_extents(extents: list[Extent]) -> list[Extent]:
    """Merge overlapping or adjacent extents into the minimal covering set.

    Adjacent extents (``a.end == b.start``) are merged too, not just
    overlapping ones — two index entries that describe back-to-back blocks
    with no gap between them should not produce a spurious zero-length gap
    when this feeds :func:`compute_gaps`.
    """
    if not extents:
        return []
    ordered = sorted(extents, key=lambda e: e.start)
    merged = [ordered[0]]
    for e in ordered[1:]:
        last = merged[-1]
        if e.start <= last.end:
            if e.end > last.end:
                merged[-1] = Extent(last.start, e.end)
        else:
            merged.append(e)
    return merged


def compute_gaps(image_size: int, allocated: list[Extent]) -> list[Extent]:
    """The complement of ``allocated`` within ``[0, image_size)``.

    This is what "unallocated space" means to the carver: not a filesystem
    concept borrowed from the profile, but literally whatever the known
    index entries do not account for. An extent from a corrupted or
    malformed profile that claims bytes beyond ``image_size`` is clipped
    to the image rather than raising — a bad claim from an untrusted index
    should not crash a scan that is otherwise trying to route around it.
    """
    if image_size < 0:
        raise ValueError("image_size must be non-negative")

    clipped = []
    for e in allocated:
        start = max(0, min(e.start, image_size))
        end = max(0, min(e.end, image_size))
        if end > start:
            clipped.append(Extent(start, end))

    merged = merge_extents(clipped)

    gaps: list[Extent] = []
    cursor = 0
    for e in merged:
        if e.start > cursor:
            gaps.append(Extent(cursor, e.start))
        cursor = max(cursor, e.end)
    if cursor < image_size:
        gaps.append(Extent(cursor, image_size))
    return gaps
