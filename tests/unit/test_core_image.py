"""Tests for pramaan.core.image.DiskImage."""

from __future__ import annotations

import mmap as mmap_module

import pytest

from pramaan.core.exceptions import ImageBoundsError, ImageOpenError
from pramaan.core.image import DiskImage, RawImageSource


def _write(tmp_path, name: str, content: bytes):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_size_matches_file(tmp_path):
    p = _write(tmp_path, "a.img", b"0123456789")
    with DiskImage(p) as img:
        assert img.size == 10
        assert len(img) == 10


def test_read_exact_slice(tmp_path):
    p = _write(tmp_path, "a.img", b"0123456789")
    with DiskImage(p) as img:
        assert img.read(3, 4) == b"3456"
        assert img.read(0, 1) == b"0"
        assert img.read(9, 1) == b"9"


def test_read_zero_length_is_empty_bytes(tmp_path):
    p = _write(tmp_path, "a.img", b"0123456789")
    with DiskImage(p) as img:
        assert img.read(5, 0) == b""


def test_read_past_end_raises_bounds_error(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    with DiskImage(p) as img:
        with pytest.raises(ImageBoundsError) as exc_info:
            img.read(3, 10)
        assert exc_info.value.offset == 3
        assert exc_info.value.length == 10
        assert exc_info.value.image_size == 5


def test_negative_offset_raises_bounds_error(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    with DiskImage(p) as img, pytest.raises(ImageBoundsError):
        img.read(-1, 2)


def test_read_after_close_raises(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    img = DiskImage(p)
    img.close()
    with pytest.raises(ValueError):
        img.read(0, 1)


def test_double_close_is_safe(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    img = DiskImage(p)
    img.close()
    img.close()  # must not raise


def test_iter_chunks_reconstructs_content(tmp_path):
    content = bytes(range(256)) * 10  # 2560 bytes, deliberately not a clean
    p = _write(tmp_path, "a.img", content)  # multiple of the chunk size below
    with DiskImage(p) as img:
        rebuilt = bytearray()
        seen_offsets = []
        for offset, chunk in img.iter_chunks(chunk_size=100):
            seen_offsets.append(offset)
            rebuilt += chunk
        assert bytes(rebuilt) == content
        assert seen_offsets == sorted(seen_offsets)
        assert seen_offsets[0] == 0


def test_iter_chunks_on_empty_image_yields_nothing(tmp_path):
    p = _write(tmp_path, "empty.img", b"")
    with DiskImage(p) as img:
        assert img.size == 0
        assert list(img.iter_chunks()) == []


def test_on_read_hook_receives_every_read(tmp_path):
    p = _write(tmp_path, "a.img", b"0123456789")
    calls: list[tuple[int, int]] = []
    with DiskImage(p, on_read=lambda offset, length: calls.append((offset, length))) as img:
        img.read(0, 3)
        img.read(5, 2)
    assert calls == [(0, 3), (5, 2)]


def test_on_read_hook_not_called_for_out_of_bounds_read(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    calls: list[tuple[int, int]] = []
    with DiskImage(p, on_read=lambda o, ln: calls.append((o, ln))) as img, \
         pytest.raises(ImageBoundsError):
        img.read(0, 100)
    # A rejected read must never be logged as if it happened — a provenance
    # trail that records reads that didn't occur is worse than an empty one.
    assert calls == []


def test_context_manager_closes_on_exception(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    img = DiskImage(p)
    try:
        with img:
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with pytest.raises(ValueError):
        img.read(0, 1)


def test_iter_chunks_rejects_non_positive_chunk_size(tmp_path):
    p = _write(tmp_path, "a.img", b"01234")
    with DiskImage(p) as img:
        with pytest.raises(ValueError):
            list(img.iter_chunks(chunk_size=0))
        with pytest.raises(ValueError):
            list(img.iter_chunks(chunk_size=-1))


def test_opening_a_nonexistent_source_raises_image_open_error(tmp_path):
    missing = tmp_path / "does-not-exist.img"
    with pytest.raises(ImageOpenError):
        DiskImage(missing)


def test_falls_back_to_seek_read_when_mmap_unavailable(tmp_path, monkeypatch):
    """Some sources (named pipes, certain special device files) cannot be
    mmap'd. RawImageSource must still work correctly through a seek+read
    fallback — simulated here by forcing mmap.mmap to fail, since actually
    obtaining a non-mmap-able file object cross-platform in a unit test
    isn't practical."""
    content = bytes(range(256)) * 4

    def _raising_mmap(*args, **kwargs):
        raise OSError("simulated: this source cannot be memory-mapped")

    monkeypatch.setattr(mmap_module, "mmap", _raising_mmap)

    p = _write(tmp_path, "unmappable.img", content)
    with DiskImage(p) as img:
        assert img.size == len(content)
        assert img.read(10, 20) == content[10:30]
        # The fallback path's own bounds check (a short read from the
        # underlying file) must surface as the same ImageBoundsError a
        # caller already handles for the mmap path — not a different
        # exception type depending on which path happened to be taken.
        with pytest.raises(ImageBoundsError):
            RawImageSource(p).read_raw(len(content) - 5, 100)
