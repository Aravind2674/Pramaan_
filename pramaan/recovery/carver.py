"""
Recovery from unallocated space: no index, no profile pointing at it —
just a byte range the filesystem doesn't claim, scanned directly for H.264
structure.

The lossless-remux and bit-exactness check here are the production version
of what was proven as a standalone proof of concept before this project's
architecture was written: carve, remux with ``-c copy`` (never re-encode),
then extract the bitstream back out of the export and confirm the coded
picture data is unchanged. That proof is what lets Pramaan claim an
exported clip carries the original recorder's bitstream byte-for-byte,
rather than asserting it.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

from pramaan.core.image import DiskImage
from pramaan.recovery.extents import Extent
from pramaan.recovery.h264 import NAL_TYPE_SPS, count_slices, find_offsets, normalize_slice_stream


class RemuxError(Exception):
    """Raised when ffmpeg fails to remux a carved payload or extract one back out."""


@dataclass(frozen=True)
class CarvedClip:
    """A contiguous run of H.264 elementary-stream data found by scanning a
    region no index or profile claims — i.e. footage with no surviving
    metadata pointing at it at all."""

    start_offset: int
    end_offset: int
    frame_count: int
    sha256: str


def carve_h264_clips(
    image: DiskImage, search_extents: list[Extent] | None = None
) -> list[CarvedClip]:
    """Scan ``search_extents`` (or the whole image, if not given) for H.264
    elementary-stream structure and reconstruct clip-sized byte ranges.

    A new clip starts at every SPS (NAL type 7) found, ending at the byte
    before the next one (or the end of the searched region) — a DVR
    ordinarily emits a fresh SPS/PPS pair at each keyframe/GOP boundary, so
    this is what separates one recorded segment from the next in a region
    with no other structure to go by. A region with no SPS at all yields no
    clips from it; carving is not attempted on data with no anchor to carve
    from.
    """
    if search_extents is None:
        search_extents = [Extent(0, image.size)]

    clips: list[CarvedClip] = []
    for region in search_extents:
        if region.length == 0:
            continue
        data = image.read(region.start, region.length)
        anchors = find_offsets(data, NAL_TYPE_SPS)
        if not anchors:
            continue

        # anchors is strictly increasing (find_offsets scans left to right
        # with no duplicates), so every slice below is non-empty and starts
        # with a genuine start code — a NAL type of 7 (SPS) forces the
        # header byte itself to be non-zero, so rstrip can never empty it.
        boundaries = [*anchors, len(data)]
        for i, local_start in enumerate(anchors):
            # A block is typically fixed-size and zero-padded past the real
            # payload — trim that padding rather than treat it as content.
            # H.264 already permits trailing zero bytes after the RBSP stop
            # bit, so this is not a hazard to real coded data.
            payload = data[local_start : boundaries[i + 1]].rstrip(b"\x00")
            abs_start = region.start + local_start
            clips.append(
                CarvedClip(
                    start_offset=abs_start,
                    end_offset=abs_start + len(payload),
                    frame_count=count_slices(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            )
    return clips


def extract_payload(image: DiskImage, clip: CarvedClip) -> bytes:
    """Read a carved clip's raw bytes back out of the image on demand.

    Deliberately not stored on :class:`CarvedClip` itself — a scan that
    finds many clips over a large image should not have to hold every
    payload in memory at once just because it found them.
    """
    return image.read(clip.start_offset, clip.end_offset - clip.start_offset)


def _run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # check=False: a non-zero exit is expected input here, not a programming
    # error -- the caller inspects returncode itself and raises RemuxError
    # with ffmpeg's own stderr, which is more useful than CalledProcessError.
    return subprocess.run([ffmpeg, *args], capture_output=True, text=True, check=False)


def remux_to_mp4(payload: bytes, dest_path: str | Path, *, frame_rate: float = 12.0) -> None:
    """Losslessly remux a raw Annex-B elementary stream into an MP4 container.

    ``-c:v copy`` means exactly one thing here: not one byte of the coded
    picture data is touched. ``frame_rate`` is a container-timing hint only
    — Annex-B carries no wall-clock timing of its own — and never affects
    the bitstream itself, which is exactly what :func:`verify_bitexact`
    checks independently rather than assumes.
    """
    fd, raw_path = tempfile.mkstemp(suffix=".264")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        result = _run_ffmpeg(
            [
                "-y", "-fflags", "+genpts", "-r", str(frame_rate),
                "-f", "h264", "-i", raw_path,
                "-c:v", "copy", "-movflags", "+faststart", str(dest_path),
            ]
        )
        if result.returncode != 0:
            raise RemuxError(f"ffmpeg remux failed:\n{result.stderr[-2000:]}")
    finally:
        os.unlink(raw_path)


def verify_bitexact(payload: bytes, mp4_path: str | Path) -> bool:
    """Extract the bitstream back out of an exported MP4 and confirm the
    coded slice data is unchanged from ``payload``.

    Compared through :func:`pramaan.recovery.h264.normalize_slice_stream`,
    not byte-for-byte — container muxing legitimately changes start-code
    length, parameter-set placement, and padding; it must never change the
    coded picture data, and that is the one thing this checks.
    """
    fd, extracted_path = tempfile.mkstemp(suffix=".264")
    os.close(fd)
    try:
        result = _run_ffmpeg(
            [
                "-y", "-i", str(mp4_path),
                "-c:v", "copy", "-bsf:v", "h264_mp4toannexb",
                "-f", "h264", extracted_path,
            ]
        )
        if result.returncode != 0:
            raise RemuxError(f"ffmpeg extraction failed:\n{result.stderr[-2000:]}")
        extracted = Path(extracted_path).read_bytes()
    finally:
        os.unlink(extracted_path)

    return normalize_slice_stream(payload) == normalize_slice_stream(extracted)
