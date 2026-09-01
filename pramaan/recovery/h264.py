"""
Annex-B H.264 NAL unit scanning.

This is the one piece of codec-level knowledge the recovery layer needs,
and it is deliberately minimal: enough to find NAL unit boundaries and read
a type byte, nothing that requires decoding a picture. Carving does not
need to understand video to recover it — it needs to recognise where one
coded unit ends and the next begins.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

# NAL unit types relevant to carving (ITU-T H.264, Table 7-1). Only the
# ones this module's callers actually branch on are named — this is not a
# complete enumeration of the standard.
NAL_TYPE_NON_IDR_SLICE = 1
NAL_TYPE_IDR_SLICE = 5
NAL_TYPE_SEI = 6
NAL_TYPE_SPS = 7
NAL_TYPE_PPS = 8
NAL_TYPE_AUD = 9

#: The two NAL types that carry actual coded picture data, as opposed to
#: parameter sets or metadata — what "frame count" means throughout this
#: package.
SLICE_NAL_TYPES = frozenset({NAL_TYPE_NON_IDR_SLICE, NAL_TYPE_IDR_SLICE})


@dataclass(frozen=True)
class NalUnit:
    """One NAL unit's location within a buffer, not its decoded content."""

    start_code_offset: int
    """Offset of the first byte of the start code (``00 00 01`` or ``00 00 00 01``)."""

    start_code_length: int
    """3 or 4, depending on which start-code form was found."""

    header_offset: int
    """Offset of the one-byte NAL header immediately after the start code."""

    nal_type: int
    """The low 5 bits of the NAL header byte."""


def iter_nal_units(data: bytes) -> Iterator[NalUnit]:
    """Scan ``data`` for every NAL unit start, in order.

    Recognises both 3-byte and 4-byte Annex-B start codes — a DVR-produced
    stream is not guaranteed to use one form consistently, and getting this
    wrong silently shifts every downstream offset by one byte.
    """
    pos = 0
    n = len(data)
    while True:
        idx = data.find(b"\x00\x00\x01", pos)
        if idx == -1:
            return
        if idx > 0 and data[idx - 1] == 0:
            start_code_offset, start_code_length = idx - 1, 4
        else:
            start_code_offset, start_code_length = idx, 3
        header_offset = idx + 3
        if header_offset >= n:
            return
        yield NalUnit(
            start_code_offset=start_code_offset,
            start_code_length=start_code_length,
            header_offset=header_offset,
            nal_type=data[header_offset] & 0x1F,
        )
        pos = idx + 3


def find_offsets(data: bytes, nal_type: int) -> list[int]:
    """Convenience: the ``start_code_offset`` of every NAL unit of a given type."""
    return [n.start_code_offset for n in iter_nal_units(data) if n.nal_type == nal_type]


def count_slices(data: bytes) -> int:
    """How many coded-picture NAL units (IDR or non-IDR slices) ``data`` contains."""
    return sum(1 for n in iter_nal_units(data) if n.nal_type in SLICE_NAL_TYPES)


def normalize_slice_stream(data: bytes) -> bytes:
    """Concatenate only the coded-slice payloads from an Annex-B buffer,
    stripping start codes, parameter sets, SEI, and any trailing zero
    padding within each NAL.

    This is the comparison this package uses to prove a lossless remux:
    container muxing legitimately changes start-code length, parameter-set
    placement, and padding, but it must never change the coded picture data
    itself. Comparing two streams through this function rather than
    byte-for-byte is what makes that a meaningful check instead of a
    trivially-failing one.
    """
    nals = list(iter_nal_units(data))
    out = bytearray()
    for i, nal in enumerate(nals):
        if nal.nal_type not in SLICE_NAL_TYPES:
            continue
        end = nals[i + 1].start_code_offset if i + 1 < len(nals) else len(data)
        # header_offset + 1: the NAL header byte itself (forbidden_zero_bit,
        # nal_ref_idc, nal_unit_type) is syntax, not slice payload.
        payload = data[nal.header_offset + 1 : end].rstrip(b"\x00")
        out += payload
    return bytes(out)
