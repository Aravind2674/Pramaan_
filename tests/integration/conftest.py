"""Shared fixtures for integration tests that need a real H.264 elementary
stream. These tests invoke the actual ffmpeg binary (via imageio-ffmpeg) --
they are integration tests, not unit tests, precisely because of that."""

from __future__ import annotations

import subprocess

import imageio_ffmpeg
import pytest


@pytest.fixture(scope="session")
def real_h264_stream(tmp_path_factory) -> bytes:
    """A short, real H.264 Annex-B elementary stream: 12 fps, 2s GOP,
    encoded once per test session and reused, since encoding is the slow
    part and its content doesn't need to vary between tests."""
    out_dir = tmp_path_factory.mktemp("h264src")
    out_path = out_dir / "sample.264"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi",
            "-i", "testsrc2=size=320x240:rate=12:duration=8",
            "-c:v", "libx264", "-g", "12", "-keyint_min", "12",
            "-sc_threshold", "0", "-preset", "ultrafast",
            "-f", "h264", str(out_path),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return out_path.read_bytes()
