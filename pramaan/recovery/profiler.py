"""
The unknown-vendor structural profiler.

Given an image with no matching :mod:`pramaan.fs` profile, this infers
enough of the recorder's layout to recover video from it anyway: block
cadence, header length, a magic signature, and the offset/width/endianness
of a timestamp, sequence, channel, and length field — using nothing but the
statistical structure of the bytes and the fact that H.264 elementary
streams have a recognisable shape. No vendor knowledge is assumed.

This is deliberately conservative rather than clever: every inference is a
concrete, checkable test (monotonicity, correlation against measured
extent, occupancy entropy), not a machine-learning model whose reasoning
can't be stated in a report. A field this module gets wrong should be wrong
in an explainable way.

Current scope: reads the full image into memory for vectorised analysis,
which is appropriate for triage-scale images and the synthetic/benchmark
corpus this project tests against. Streaming this for multi-terabyte disks
is future work, not attempted here.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import numpy as np
import yaml

from pramaan.core.image import DiskImage
from pramaan.recovery.h264 import NAL_TYPE_SPS, find_offsets

Endian = Literal["little", "big"]

#: Plausible Unix-epoch-seconds range for a timestamp guess: from roughly
#: 2001 to roughly 2039. Wide enough to not miss a real recorder timestamp,
#: narrow enough to reject arbitrary binary noise.
_EPOCH_LOW = 1_000_000_000
_EPOCH_HIGH = 2_200_000_000

#: A candidate field must be constant across at least this fraction of
#: sampled blocks to be accepted as the header length / magic boundary.
_MIN_HEADER_CONSISTENCY = 0.5
_MIN_MAGIC_DOMINANCE = 0.6

#: A channel candidate's value distribution must be at least this uniform
#: (entropy relative to a perfectly uniform distribution over the observed
#: cardinality) to be accepted — this is what separates a real channel ID
#: from the lumpy high bits of some unrelated field.
_MIN_CHANNEL_UNIFORMITY = 0.90
_MAX_CHANNEL_CARDINALITY = 64
_MIN_LENGTH_CORRELATION = 0.98

_ENDIAN_OPTIONS: tuple[tuple[Endian, str], ...] = (("little", "<"), ("big", ">"))


@dataclass(frozen=True)
class FieldGuess:
    offset: int
    width: int
    endian: Endian
    kind: Literal["timestamp_unix", "sequence", "length", "channel"]
    confidence: float
    note: str


@dataclass(frozen=True)
class DraftLayout:
    """What could be inferred, and what could not.

    A layout with too few anchors or inconsistent header boundaries simply
    has ``block_size`` / ``header_length`` as ``None`` — this is a report of
    what was found, not a best-effort guess dressed up as a confident
    answer.
    """

    anchors_found: int
    block_size: int | None
    header_length: int | None
    header_consistency: float
    blocks_analyzed: int
    magic: bytes
    signature_cleared_blocks: tuple[int, ...]
    fields: tuple[FieldGuess, ...]


def _infer_block_geometry(anchors: list[int]) -> tuple[int, int, float] | None:
    """From the spacing between anchors, infer the block size and the
    header length preceding each anchor within its block.

    The recorder writes one video segment per block, so the *dominant*
    spacing between consecutive anchors is the block size itself — not an
    approximation of it, because every full block contributes exactly one
    such gap. A block size that lands within 1% of a power of two is
    snapped to it, since fixed-size storage overwhelmingly is one.
    """
    # anchors is strictly increasing (guaranteed by infer_layout's sole
    # caller, find_offsets), so every diff is positive by construction --
    # nothing here needs to defend against a non-increasing input.
    diffs = np.diff(np.asarray(anchors, dtype=np.int64))
    cadence = int(Counter(diffs.tolist()).most_common(1)[0][0])
    power_of_two = 1 << round(np.log2(cadence)) if cadence > 0 else cadence
    if power_of_two > 0 and abs(power_of_two - cadence) / cadence < 0.01:
        cadence = power_of_two

    residues = Counter(a % cadence for a in anchors)
    header_length, hits = residues.most_common(1)[0]
    consistency = hits / len(anchors)
    if header_length == 0 or consistency < _MIN_HEADER_CONSISTENCY:
        return None
    return cadence, int(header_length), consistency


def _infer_magic(headers: np.ndarray) -> tuple[bytes, list[int]]:
    """The modal byte value at each of the first 32 header offsets, taken
    as the signature for as long as it stays dominant and non-zero.

    Blocks whose observed bytes disagree with this signature are not noise
    to filter out — they are recorded and returned, because a cleared
    signature is exactly what an unlinked (deleted) index entry looks like.
    """
    n = headers.shape[0]
    scan_width = min(headers.shape[1], 32)
    modal_bytes: list[int] = []
    dominance: list[float] = []
    for col in range(scan_width):
        value, count = Counter(headers[:, col].tolist()).most_common(1)[0]
        modal_bytes.append(value)
        dominance.append(count / n)

    magic_length = 0
    for i in range(scan_width):
        if modal_bytes[i] != 0 and dominance[i] >= _MIN_MAGIC_DOMINANCE:
            magic_length = i + 1
        else:
            break

    magic = bytes(modal_bytes[:magic_length])
    if not magic_length:
        return magic, []

    signature = np.frombuffer(magic, dtype=np.uint8)
    matches = (headers[:, :magic_length] == signature).all(axis=1)
    cleared = [int(i) for i in np.flatnonzero(~matches)]
    return magic, cleared


def _measure_payload_extents(image: DiskImage, bases: list[int], header_length: int, cadence: int) -> np.ndarray:
    """For each block, how many bytes past the header are non-zero before
    the first all-zero tail — a length field, if one exists, should
    correlate almost perfectly against this."""
    extents: np.ndarray = np.empty(len(bases), dtype=np.int64)
    for i, base in enumerate(bases):
        body = np.frombuffer(image.read(base + header_length, cadence - header_length), dtype=np.uint8)
        nonzero = np.flatnonzero(body)
        extents[i] = int(nonzero[-1] + 1) if nonzero.size else 0
    return extents


def _infer_fields(headers: np.ndarray, extents: np.ndarray, header_length: int) -> list[FieldGuess]:
    n = headers.shape[0]
    candidates: list[FieldGuess] = []

    for offset in range(header_length):
        for width, fmt in ((4, "I"), (8, "Q"), (2, "H")):
            if offset + width > header_length:
                continue
            for endian, symbol in _ENDIAN_OPTIONS:
                # offset + width <= header_length was just checked above, and
                # every row of `headers` is exactly header_length bytes, so
                # this unpack is always in-bounds -- no struct.error to guard.
                raw_values = [
                    struct.unpack_from(symbol + fmt, headers[i].tobytes(), offset)[0]
                    for i in range(n)
                ]
                if max(raw_values) > np.iinfo(np.int64).max:
                    # A value this large cannot be a timestamp, sequence, or
                    # length under any of the checks below — drop it rather
                    # than widen the comparison dtype to accommodate it.
                    continue
                values = np.array(raw_values, dtype=np.int64)
                unique_count = len(np.unique(values))
                if unique_count < 2:
                    continue
                strictly_increasing = bool(np.all(np.diff(values) > 0))

                if (
                    width in (4, 8)
                    and strictly_increasing
                    and _EPOCH_LOW <= values[0] <= _EPOCH_HIGH
                    and _EPOCH_LOW <= values[-1] <= _EPOCH_HIGH
                ):
                    span = int(values[-1] - values[0])
                    candidates.append(FieldGuess(
                        offset, width, endian, "timestamp_unix", 0.95,
                        f"monotonic, span {span}s, first={values[0]}",
                    ))
                elif strictly_increasing and values[0] < 16 and values[-1] < (1 << 24):
                    candidates.append(FieldGuess(
                        offset, width, endian, "sequence", 0.85,
                        f"0..{values[-1]}",
                    ))
                elif (
                    not strictly_increasing
                    and unique_count >= 4
                    and 0 < values.min()
                    and len(np.unique(extents)) > 1
                ):
                    correlation = float(np.corrcoef(values, extents)[0, 1])
                    if correlation > _MIN_LENGTH_CORRELATION:
                        candidates.append(FieldGuess(
                            offset, width, endian, "length", 0.90,
                            f"{values.min()}..{values.max()}, "
                            f"r={correlation:.3f} vs measured payload extent",
                        ))
                elif (
                    2 <= unique_count <= _MAX_CHANNEL_CARDINALITY
                    and values.max() < _MAX_CHANNEL_CARDINALITY
                    and not strictly_increasing
                ):
                    counts = np.unique(values, return_counts=True)[1]
                    p = counts / counts.sum()
                    uniformity = float(-(p * np.log2(p)).sum() / np.log2(unique_count))
                    if uniformity >= _MIN_CHANNEL_UNIFORMITY:
                        candidates.append(FieldGuess(
                            offset, width, endian, "channel",
                            0.60 + 0.30 * uniformity,
                            f"{unique_count} distinct, max {values.max()}, "
                            f"uniformity {uniformity:.2f}",
                        ))

    # Resolve overlaps: an aliased read (a 2-byte window inside a real
    # 4-byte field, or the same value under both endiannesses) is the real
    # hazard here. Prefer higher confidence, then natural alignment, then
    # the wider field — a narrower match inside a real field is its alias,
    # not an independent field.
    candidates.sort(key=lambda g: (-g.confidence, g.offset % g.width != 0, -g.width))
    accepted: list[FieldGuess] = []
    for guess in candidates:
        if any(
            not (guess.offset + guess.width <= taken.offset or taken.offset + taken.width <= guess.offset)
            for taken in accepted
        ):
            continue
        accepted.append(guess)
    return sorted(accepted, key=lambda g: g.offset)


def infer_layout(image: DiskImage, *, anchor_nal_type: int = NAL_TYPE_SPS) -> DraftLayout:
    """Infer as much of an unknown recorder's block layout as the bytes support.

    ``anchor_nal_type`` defaults to SPS (7) — a DVR typically emits a fresh
    SPS at the start of each recorded segment, which is what makes it a
    reliable anchor for finding block boundaries in the first place.
    """
    data = image.read(0, image.size)
    anchors = find_offsets(data, anchor_nal_type)
    if len(anchors) < 4:
        return DraftLayout(
            anchors_found=len(anchors), block_size=None, header_length=None,
            header_consistency=0.0, blocks_analyzed=0, magic=b"",
            signature_cleared_blocks=(), fields=(),
        )

    geometry = _infer_block_geometry(anchors)
    if geometry is None:
        return DraftLayout(
            anchors_found=len(anchors), block_size=None, header_length=None,
            header_consistency=0.0, blocks_analyzed=0, magic=b"",
            signature_cleared_blocks=(), fields=(),
        )
    cadence, header_length, consistency = geometry

    bases = sorted({a - header_length for a in anchors if a >= header_length})
    headers = np.frombuffer(
        b"".join(data[b : b + header_length] for b in bases), dtype=np.uint8
    ).reshape(len(bases), header_length)

    magic, cleared_local_indices = _infer_magic(headers)
    cleared_blocks = tuple(bases[i] // cadence for i in cleared_local_indices)

    extents = _measure_payload_extents(image, bases, header_length, cadence)
    fields = _infer_fields(headers, extents, header_length)

    return DraftLayout(
        anchors_found=len(anchors),
        block_size=cadence,
        header_length=header_length,
        header_consistency=consistency,
        blocks_analyzed=len(bases),
        magic=magic,
        signature_cleared_blocks=cleared_blocks,
        fields=tuple(fields),
    )


_ROLE_BY_KIND = {
    "timestamp_unix": "timestamp",
    "sequence": "sequence",
    "length": "length",
    "channel": "channel",
}
_DTYPE_BY_WIDTH = {2: "u16", 4: "u32", 8: "u64"}


def draft_layout_to_profile_yaml(
    layout: DraftLayout, *, vendor: str = "unknown", format_id: str = "unknown_provisional"
) -> str:
    """Render an inferred layout as a profile document in this project's
    own schema — a candidate for a human to review, verify against a real
    disk of the same vendor, and promote field-by-field to ``confirmed``.

    Every field is emitted with ``status: unconfirmed`` unconditionally:
    this is an inference, however well-supported, not a verified fact, and
    the schema's own honesty convention (see ``profile.schema.json``)
    applies to profiles this project generates about itself just as much
    as to ones a human writes by hand.
    """
    if layout.block_size is None or layout.header_length is None:
        raise ValueError("cannot render a profile from a layout with no inferred block geometry")

    fields = [
        {
            "name": "magic",
            "offset": 0,
            "size": len(layout.magic),
            "dtype": "bytes",
            "status": "unconfirmed",
            "note": "Inferred from modal-byte dominance across sampled blocks.",
        }
    ] if layout.magic else []

    for guess in layout.fields:
        fields.append({
            "name": f"{_ROLE_BY_KIND[guess.kind]}_field",
            "offset": guess.offset,
            "size": guess.width,
            "dtype": _DTYPE_BY_WIDTH[guess.width],
            "endian": guess.endian,
            "role": _ROLE_BY_KIND[guess.kind],
            "status": "unconfirmed",
            "note": f"confidence={guess.confidence:.2f}; {guess.note}",
        })

    doc = {
        "vendor": vendor,
        "format_id": format_id,
        "display_name": f"Unknown-vendor draft profile ({format_id})",
        "version": "0.1",
        "confidence": "provisional",
        "description": (
            "Generated by pramaan.recovery.profiler from structural inference "
            "alone, with no prior knowledge of this recorder's format. Every "
            "field is unconfirmed pending review against a real disk of the "
            "same vendor/model."
        ),
        "endian": "little",
        "signature": (
            {"offset": 0, "bytes_hex": layout.magic.hex(), "recurring": True}
            if layout.magic
            else {"offset": 0, "bytes_hex": "00", "recurring": True}
        ),
        "fields": fields,
        "notes": [
            f"Inferred block size: {layout.block_size} bytes.",
            (
                f"Inferred header length: {layout.header_length} bytes "
                f"(consistency {layout.header_consistency:.0%} across "
                f"{layout.blocks_analyzed} sampled blocks)."
            ),
            (
                f"{len(layout.signature_cleared_blocks)} block(s) had a cleared/non-matching "
                f"signature: block indices {list(layout.signature_cleared_blocks)}. These are "
                "candidates for recovery via pramaan.recovery.carver, since a cleared "
                "signature is consistent with a deleted index entry whose video payload "
                "was left in place."
            ),
        ],
    }
    return yaml.safe_dump(doc, sort_keys=False)
