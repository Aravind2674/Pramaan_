"""
Integration test for the carving pipeline: build a disk image containing
real H.264 segments in a region with no filesystem index pointing at them
(exactly what "unallocated space" looks like after a deletion), carve them
back out, and prove the exported clips are bit-exact against the source --
the production-code version of what was validated as a standalone proof of
concept before this project's architecture was written.
"""

from __future__ import annotations

import pytest

from pramaan.core.image import DiskImage
from pramaan.recovery.carver import (
    RemuxError,
    carve_h264_clips,
    extract_payload,
    remux_to_mp4,
    verify_bitexact,
)
from pramaan.recovery.extents import Extent
from pramaan.recovery.h264 import NAL_TYPE_SPS, count_slices, find_offsets


def _split_into_segments(stream: bytes) -> list[bytes]:
    """Every consecutive SPS-to-SPS interval in the stream, each a genuine,
    non-overlapping real segment (a DVR normally emits a fresh SPS/PPS pair
    per GOP, so this is what actually separates one recorded interval from
    the next). Callers take however many of these they need."""
    sps_offsets = find_offsets(stream, NAL_TYPE_SPS)
    return [stream[sps_offsets[i] : sps_offsets[i + 1]] for i in range(len(sps_offsets) - 1)]


def _build_image_with_gap(tmp_path, segments: list[bytes], block_size: int) -> tuple[str, Extent]:
    """A superblock of junk, followed by fixed-size zero-padded blocks each
    holding one segment -- the region these blocks occupy is deliberately
    NOT recorded as an allocated extent anywhere, standing in for a
    filesystem region whose index entry has been cleared."""
    path = tmp_path / "image.raw"
    with path.open("wb") as fh:
        fh.write(b"\xff" * block_size)  # unrelated "allocated" junk before the gap
        gap_start = fh.tell()
        for seg in segments:
            assert len(seg) < block_size, "test segment must fit in one block"
            fh.write(seg + b"\x00" * (block_size - len(seg)))
        gap_end = fh.tell()
        fh.write(b"\xff" * block_size)  # unrelated "allocated" junk after the gap
    return str(path), Extent(gap_start, gap_end)


def test_carve_recovers_every_segment_with_correct_frame_counts(tmp_path, real_h264_stream):
    segments = _split_into_segments(real_h264_stream)[:4]
    block_size = 1 << 20  # comfortably larger than one GOP-sized real segment
    img_path, gap = _build_image_with_gap(tmp_path, segments, block_size)

    with DiskImage(img_path) as img:
        clips = carve_h264_clips(img, [gap])

    assert len(clips) == len(segments)
    for clip, original in zip(clips, segments, strict=True):
        expected_frames = count_slices(original.rstrip(b"\x00"))
        assert clip.frame_count == expected_frames
        assert clip.frame_count > 0


def test_carve_returns_nothing_outside_the_searched_extent(tmp_path, real_h264_stream):
    segments = _split_into_segments(real_h264_stream)[:2]
    block_size = 1 << 20  # comfortably larger than one GOP-sized real segment
    img_path, _gap = _build_image_with_gap(tmp_path, segments, block_size)

    with DiskImage(img_path) as img:
        # Search a region that does NOT include the gap at all.
        clips = carve_h264_clips(img, [Extent(0, block_size)])

    assert clips == []


def test_carve_on_region_with_no_video_structure_finds_nothing(tmp_path):
    path = tmp_path / "blank.raw"
    path.write_bytes(b"\x00" * 4096)
    with DiskImage(path) as img:
        assert carve_h264_clips(img) == []


def test_extract_payload_matches_declared_extent(tmp_path, real_h264_stream):
    segments = _split_into_segments(real_h264_stream)[:1]
    block_size = 1 << 20  # comfortably larger than one GOP-sized real segment
    img_path, gap = _build_image_with_gap(tmp_path, segments, block_size)

    with DiskImage(img_path) as img:
        clips = carve_h264_clips(img, [gap])
        assert len(clips) == 1
        payload = extract_payload(img, clips[0])

    assert len(payload) == clips[0].end_offset - clips[0].start_offset
    assert not payload.endswith(b"\x00")  # trailing padding must already be trimmed


def test_recovered_clips_remux_bit_exact_against_source(tmp_path, real_h264_stream):
    """The claim that matters: the exported MP4 carries the original
    recorder bitstream byte-for-byte, proven by round-tripping it back out
    and comparing, not merely asserted."""
    segments = _split_into_segments(real_h264_stream)[:3]
    block_size = 1 << 20  # comfortably larger than one GOP-sized real segment
    img_path, gap = _build_image_with_gap(tmp_path, segments, block_size)

    with DiskImage(img_path) as img:
        clips = carve_h264_clips(img, [gap])
        assert len(clips) == len(segments)

        for i, clip in enumerate(clips):
            payload = extract_payload(img, clip)
            mp4_path = tmp_path / f"recovered_{i}.mp4"
            remux_to_mp4(payload, mp4_path)
            assert mp4_path.exists() and mp4_path.stat().st_size > 0
            assert verify_bitexact(payload, mp4_path) is True


def test_verify_bitexact_raises_remux_error_on_a_non_video_file(tmp_path):
    not_a_video = tmp_path / "not_a_video.mp4"
    not_a_video.write_bytes(b"this is plain text, not a video container")
    with pytest.raises(RemuxError):
        verify_bitexact(b"irrelevant", not_a_video)


def test_remux_to_mp4_raises_remux_error_when_destination_is_unwritable(tmp_path, real_h264_stream):
    segment = _split_into_segments(real_h264_stream)[0]
    # The parent directory doesn't exist -- ffmpeg cannot create it, so the
    # remux itself (not just extraction) must surface as a RemuxError.
    bad_dest = tmp_path / "no_such_directory" / "out.mp4"
    with pytest.raises(RemuxError):
        remux_to_mp4(segment, bad_dest)


def test_carve_ignores_zero_length_search_extents(tmp_path, real_h264_stream):
    """A caller-supplied zero-length extent is valid per Extent itself
    (start == end) and must be skipped cleanly, not crash the scan of the
    other, real extents alongside it."""
    segments = _split_into_segments(real_h264_stream)[:2]
    block_size = 1 << 20
    img_path, gap = _build_image_with_gap(tmp_path, segments, block_size)

    with DiskImage(img_path) as img:
        clips = carve_h264_clips(img, [Extent(50, 50), gap, Extent(0, 0)])

    assert len(clips) == len(segments)
