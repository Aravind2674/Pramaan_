"""Tests for pramaan.recovery.h264 — pure byte-buffer logic, no ffmpeg needed."""

from __future__ import annotations

from pramaan.recovery.h264 import (
    NAL_TYPE_IDR_SLICE,
    NAL_TYPE_NON_IDR_SLICE,
    NAL_TYPE_PPS,
    NAL_TYPE_SPS,
    count_slices,
    find_offsets,
    iter_nal_units,
    normalize_slice_stream,
)


def _nal(nal_type: int, payload: bytes, start_code: bytes = b"\x00\x00\x00\x01") -> bytes:
    return start_code + bytes([nal_type]) + payload


def test_iter_nal_units_with_4byte_start_codes():
    data = _nal(NAL_TYPE_SPS, b"\xaa\xbb") + _nal(NAL_TYPE_IDR_SLICE, b"\xcc\xdd\xee")
    units = list(iter_nal_units(data))
    assert [u.nal_type for u in units] == [NAL_TYPE_SPS, NAL_TYPE_IDR_SLICE]
    assert [u.start_code_length for u in units] == [4, 4]
    assert units[0].start_code_offset == 0
    assert units[0].header_offset == 4


def test_iter_nal_units_with_3byte_start_codes():
    data = _nal(NAL_TYPE_SPS, b"\xaa", start_code=b"\x00\x00\x01") + _nal(
        NAL_TYPE_PPS, b"\xbb", start_code=b"\x00\x00\x01"
    )
    units = list(iter_nal_units(data))
    assert [u.nal_type for u in units] == [NAL_TYPE_SPS, NAL_TYPE_PPS]
    assert [u.start_code_length for u in units] == [3, 3]


def test_iter_nal_units_with_mixed_start_code_lengths():
    data = (
        _nal(NAL_TYPE_SPS, b"\xaa", start_code=b"\x00\x00\x01")
        + _nal(NAL_TYPE_IDR_SLICE, b"\xbb", start_code=b"\x00\x00\x00\x01")
    )
    units = list(iter_nal_units(data))
    assert [u.start_code_length for u in units] == [3, 4]
    assert [u.nal_type for u in units] == [NAL_TYPE_SPS, NAL_TYPE_IDR_SLICE]


def test_iter_nal_units_on_empty_buffer():
    assert list(iter_nal_units(b"")) == []


def test_iter_nal_units_ignores_truncated_start_code_at_end():
    # A start code with no header byte following it must not be yielded or
    # crash the scan -- it's what a stream cut off mid-NAL looks like.
    data = _nal(NAL_TYPE_SPS, b"\xaa") + b"\x00\x00\x00\x01"
    units = list(iter_nal_units(data))
    assert len(units) == 1
    assert units[0].nal_type == NAL_TYPE_SPS


def test_find_offsets_filters_by_type():
    data = _nal(NAL_TYPE_SPS, b"\x01") + _nal(NAL_TYPE_PPS, b"\x02") + _nal(NAL_TYPE_SPS, b"\x03")
    offsets = find_offsets(data, NAL_TYPE_SPS)
    assert len(offsets) == 2
    assert offsets[0] == 0


def test_count_slices_only_counts_slice_types():
    data = (
        _nal(NAL_TYPE_SPS, b"\x01")
        + _nal(NAL_TYPE_PPS, b"\x02")
        + _nal(NAL_TYPE_IDR_SLICE, b"\x03")
        + _nal(NAL_TYPE_NON_IDR_SLICE, b"\x04")
        + _nal(NAL_TYPE_NON_IDR_SLICE, b"\x05")
    )
    assert count_slices(data) == 3


def test_normalize_slice_stream_keeps_only_slice_payloads():
    data = (
        _nal(NAL_TYPE_SPS, b"\x11\x22")
        + _nal(NAL_TYPE_PPS, b"\x33")
        + _nal(NAL_TYPE_IDR_SLICE, b"\xaa\xbb\xcc")
        + _nal(NAL_TYPE_NON_IDR_SLICE, b"\xdd\xee")
    )
    normalized = normalize_slice_stream(data)
    assert normalized == b"\xaa\xbb\xcc\xdd\xee"


def test_normalize_slice_stream_strips_trailing_zero_padding_per_nal():
    data = _nal(NAL_TYPE_IDR_SLICE, b"\xaa\xbb\x00\x00\x00") + _nal(NAL_TYPE_NON_IDR_SLICE, b"\xcc")
    assert normalize_slice_stream(data) == b"\xaa\xbb\xcc"


def test_normalize_slice_stream_is_insensitive_to_start_code_length():
    """The whole point of comparing through this function: two streams that
    differ only in start-code length (3 vs 4 bytes) must normalize identically."""
    a = _nal(NAL_TYPE_IDR_SLICE, b"\xaa\xbb", start_code=b"\x00\x00\x01")
    b = _nal(NAL_TYPE_IDR_SLICE, b"\xaa\xbb", start_code=b"\x00\x00\x00\x01")
    assert normalize_slice_stream(a) == normalize_slice_stream(b)


def test_normalize_slice_stream_on_data_with_no_slices():
    data = _nal(NAL_TYPE_SPS, b"\x01") + _nal(NAL_TYPE_PPS, b"\x02")
    assert normalize_slice_stream(data) == b""
