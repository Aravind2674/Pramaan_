"""Tests for pramaan.core.hashing."""

from __future__ import annotations

import hashlib
import os

import pytest

from pramaan.core.hashing import StreamingHash, hash_image
from pramaan.core.image import DiskImage


def test_streaming_hash_matches_hashlib_single_shot():
    data = os.urandom(1_000_003)  # deliberately not a round chunk boundary
    sh = StreamingHash(("sha256", "blake2b"))
    # Feed it in irregular chunk sizes to prove correctness doesn't depend on
    # the caller's chunking.
    for i in range(0, len(data), 777):
        sh.update(data[i : i + 777])
    digests = sh.hexdigests()
    assert digests["sha256"] == hashlib.sha256(data).hexdigest()
    assert digests["blake2b"] == hashlib.blake2b(data).hexdigest()
    assert sh.bytes_seen == len(data)


def test_streaming_hash_rejects_unknown_algorithm():
    with pytest.raises(ValueError):
        StreamingHash(("sha256", "not_a_real_algorithm"))


def test_streaming_hash_rejects_empty_algorithm_list():
    with pytest.raises(ValueError):
        StreamingHash(())


def test_hash_image_matches_direct_hashlib(tmp_path):
    data = os.urandom(5_000_017)
    p = tmp_path / "img.dd"
    p.write_bytes(data)
    with DiskImage(p) as img:
        digests = hash_image(img, ("sha256", "md5"), chunk_size=64_000)
    assert digests["sha256"] == hashlib.sha256(data).hexdigest()
    assert digests["md5"] == hashlib.md5(data).hexdigest()


def test_hash_image_progress_callback_reaches_total(tmp_path):
    data = os.urandom(300_000)
    p = tmp_path / "img.dd"
    p.write_bytes(data)
    progress_calls: list[tuple[int, int]] = []
    with DiskImage(p) as img:
        hash_image(
            img,
            chunk_size=100_000,
            on_progress=lambda done, total: progress_calls.append((done, total)),
        )
    assert progress_calls[-1] == (300_000, 300_000)
    assert all(total == 300_000 for _, total in progress_calls)
    # Monotonically increasing — a progress bar must never go backwards.
    assert [done for done, _ in progress_calls] == sorted(d for d, _ in progress_calls)


def test_hash_image_on_empty_image(tmp_path):
    p = tmp_path / "empty.dd"
    p.write_bytes(b"")
    with DiskImage(p) as img:
        digests = hash_image(img)
    assert digests["sha256"] == hashlib.sha256(b"").hexdigest()
