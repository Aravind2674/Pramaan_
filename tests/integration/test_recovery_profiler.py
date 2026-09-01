"""
Integration test for the unknown-vendor structural profiler.

This reproduces, as production-code regression coverage, the exact
experiment that validated the profiler concept before this project's
architecture was written: build a synthetic recorder image using a layout
the profiler is never told about, clear the signature on some blocks to
simulate deleted index entries, and confirm structural inference alone
recovers block geometry, the header, and every semantic field -- plus
identifies exactly which blocks were "deleted".
"""

from __future__ import annotations

import struct

import pytest
import yaml

from pramaan.core.image import DiskImage
from pramaan.fs.profile import load_profile
from pramaan.recovery.h264 import NAL_TYPE_SPS, find_offsets
from pramaan.recovery.profiler import draft_layout_to_profile_yaml, infer_layout

# Ground truth for a layout the profiler is never told about. None of these
# constants are referenced by pramaan.recovery.profiler itself.
GT_BLOCK = 1 << 20  # 1 MiB
GT_MAGIC = b"ZQFS"
GT_HEADER = 48
GT_OFFSET_CHANNEL = 6   # u16 LE
GT_OFFSET_TIMESTAMP = 8  # u32 LE, unix epoch
GT_OFFSET_SEQUENCE = 12  # u32 LE
GT_OFFSET_LENGTH = 16   # u32 LE
GT_EPOCH_START = 1_756_000_000
GT_CHANNELS = 4
GT_DELETED_BLOCKS = {5, 6, 7, 19, 20, 33}


def _split_into_segments(stream: bytes) -> list[bytes]:
    """Every consecutive SPS-to-SPS interval, cycled via modulo by the
    caller to fill more blocks than there are distinct real segments."""
    sps_offsets = find_offsets(stream, NAL_TYPE_SPS)
    return [stream[sps_offsets[i] : sps_offsets[i + 1]] for i in range(len(sps_offsets) - 1)]


def _build_unknown_vendor_image(path, real_h264_stream: bytes, n_blocks: int = 48) -> None:
    segments = _split_into_segments(real_h264_stream)
    with path.open("wb") as fh:
        fh.write(b"\x00" * GT_BLOCK)  # a superblock the profiler never sees interpreted
        for i in range(n_blocks):
            segment = segments[i % len(segments)][: GT_BLOCK - GT_HEADER]
            header = bytearray(GT_HEADER)
            header[0:4] = b"\x00\x00\x00\x00" if i in GT_DELETED_BLOCKS else GT_MAGIC
            struct.pack_into("<H", header, GT_OFFSET_CHANNEL, i % GT_CHANNELS)
            struct.pack_into("<I", header, GT_OFFSET_TIMESTAMP, GT_EPOCH_START + i * 137)
            struct.pack_into("<I", header, GT_OFFSET_SEQUENCE, i)
            struct.pack_into("<I", header, GT_OFFSET_LENGTH, len(segment))
            body = bytes(header) + segment + b"\x00" * (GT_BLOCK - GT_HEADER - len(segment))
            fh.write(body)


def test_profiler_recovers_full_layout_from_raw_bytes_alone(tmp_path, real_h264_stream):
    img_path = tmp_path / "unknown_vendor.img"
    _build_unknown_vendor_image(img_path, real_h264_stream)

    with DiskImage(img_path) as img:
        layout = infer_layout(img)

    assert layout.block_size == GT_BLOCK
    assert layout.header_length == GT_HEADER
    assert layout.header_consistency >= 0.5
    assert layout.magic == GT_MAGIC
    # +1: the profiler counts blocks from absolute offset 0, so the leading
    # superblock this image starts with is block 0 -- it has no way to know
    # that block is special, and correctly doesn't try to guess. GT_DELETED
    # _BLOCKS is defined as an index within the data-block loop below, which
    # starts one block later.
    expected_cleared = {i + 1 for i in GT_DELETED_BLOCKS}
    assert set(layout.signature_cleared_blocks) == expected_cleared

    fields_by_kind = {f.kind: f for f in layout.fields}
    assert set(fields_by_kind) == {"timestamp_unix", "sequence", "length", "channel"}

    ts = fields_by_kind["timestamp_unix"]
    assert (ts.offset, ts.width, ts.endian) == (GT_OFFSET_TIMESTAMP, 4, "little")

    seq = fields_by_kind["sequence"]
    assert (seq.offset, seq.width, seq.endian) == (GT_OFFSET_SEQUENCE, 4, "little")

    length = fields_by_kind["length"]
    assert (length.offset, length.endian) == (GT_OFFSET_LENGTH, "little")

    channel = fields_by_kind["channel"]
    assert (channel.offset, channel.width, channel.endian) == (GT_OFFSET_CHANNEL, 2, "little")


def test_profiler_on_image_with_too_few_anchors_returns_empty_layout(tmp_path):
    img_path = tmp_path / "blank.img"
    img_path.write_bytes(b"\x00" * (1 << 16))
    with DiskImage(img_path) as img:
        layout = infer_layout(img)

    assert layout.block_size is None
    assert layout.header_length is None
    assert layout.fields == ()
    assert layout.anchors_found == 0


def test_draft_layout_serializes_to_a_schema_valid_provisional_profile(tmp_path, real_h264_stream):
    img_path = tmp_path / "unknown_vendor.img"
    _build_unknown_vendor_image(img_path, real_h264_stream)
    with DiskImage(img_path) as img:
        layout = infer_layout(img)

    yaml_text = draft_layout_to_profile_yaml(layout, vendor="acme", format_id="acme_draft_v1")
    doc = yaml.safe_load(yaml_text)

    assert doc["confidence"] == "provisional"
    assert doc["vendor"] == "acme"
    assert doc["format_id"] == "acme_draft_v1"
    assert all(f["status"] == "unconfirmed" for f in doc["fields"])

    # The whole point of this function: its output must be a loadable,
    # schema-valid profile, not just YAML that merely looks like one.
    profile_path = tmp_path / "acme_draft_v1.yaml"
    profile_path.write_text(yaml_text)
    loaded = load_profile(profile_path)
    assert loaded.confidence == "provisional"
    assert {f.role for f in loaded.fields if f.role} == {"channel", "timestamp", "sequence", "length"}


def test_profiler_on_headerless_layout_reports_no_geometry(tmp_path, real_h264_stream):
    """Each segment starts at position 0 of its fixed-size block -- there is
    no header for the profiler to find, and the honest result is 'nothing
    confirmed', not a false claim of a zero-length header."""
    segments = _split_into_segments(real_h264_stream)
    block_size = 1 << 18
    img_path = tmp_path / "headerless.img"
    with img_path.open("wb") as fh:
        for i in range(8):
            segment = segments[i % len(segments)][:block_size]
            fh.write(segment + b"\x00" * (block_size - len(segment)))

    with DiskImage(img_path) as img:
        layout = infer_layout(img)

    assert layout.block_size is None
    assert layout.header_length is None
    assert layout.fields == ()


def test_profiler_with_no_dominant_header_offset_reports_no_geometry(tmp_path, real_h264_stream):
    """Each block places its segment at one of three different offsets, none
    of which is used by a majority of blocks -- there is no single header
    length the profiler can commit to, and it must say so rather than guess
    whichever offset happened to be checked first."""
    segments = _split_into_segments(real_h264_stream)
    block_size = 1 << 18
    header_offsets = (10, 100, 300)
    img_path = tmp_path / "noisy_header.img"
    with img_path.open("wb") as fh:
        for i in range(9):
            offset = header_offsets[i % len(header_offsets)]
            segment = segments[i % len(segments)][: block_size - offset]
            body = (
                b"\x00" * offset
                + segment
                + b"\x00" * (block_size - offset - len(segment))
            )
            fh.write(body)

    with DiskImage(img_path) as img:
        layout = infer_layout(img)

    assert layout.block_size is None
    assert layout.header_length is None


def test_profiler_with_no_dominant_first_byte_finds_no_magic(tmp_path, real_h264_stream):
    """Block geometry (size, header length) is inferred purely from anchor
    *positions* and is independent of header *content* -- so a layout with
    no consistent signature byte should still yield correct geometry, just
    with an empty magic rather than a false one."""
    segments = _split_into_segments(real_h264_stream)
    block_size = 1 << 18
    header = GT_HEADER
    first_byte_options = (0x11, 0x22, 0x33)
    img_path = tmp_path / "no_magic.img"
    with img_path.open("wb") as fh:
        for i in range(9):
            segment = segments[i % len(segments)][: block_size - header]
            hdr = bytearray(header)
            hdr[0] = first_byte_options[i % len(first_byte_options)]
            body = bytes(hdr) + segment + b"\x00" * (block_size - header - len(segment))
            fh.write(body)

    with DiskImage(img_path) as img:
        layout = infer_layout(img)

    assert layout.block_size == block_size
    assert layout.header_length == header
    assert layout.magic == b""
    assert layout.signature_cleared_blocks == ()


def test_draft_layout_to_yaml_rejects_an_incomplete_layout():
    from pramaan.recovery.profiler import DraftLayout

    incomplete = DraftLayout(
        anchors_found=0, block_size=None, header_length=None,
        header_consistency=0.0, blocks_analyzed=0, magic=b"",
        signature_cleared_blocks=(), fields=(),
    )
    with pytest.raises(ValueError):
        draft_layout_to_profile_yaml(incomplete)
