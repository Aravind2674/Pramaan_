"""
Read-only, provenance-tracked access to an acquired disk image.

Design rule this module exists to enforce: nothing downstream of ``DiskImage``
can write to the source. There is no ``write`` method, no ``mode="r+b"``
option, and no way to construct one around a writable handle — the guarantee
is structural, not a matter of callers behaving.

``DiskImage`` wraps an :class:`ImageSource`, an abstraction over *where the
bytes come from*. Only :class:`RawImageSource` (a flat dd/raw image, or a raw
physical device path) is implemented today. The seam is deliberate: adding
E01 or AFF4 support later means writing one more small class, not touching
this file or anything built on top of it.
"""

from __future__ import annotations

import mmap
import os
from abc import ABC
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol, Self

from pramaan.core.exceptions import ImageBoundsError, ImageOpenError

#: Called as ``on_read(offset, length)`` every time a read reaches the
#: underlying source. ``DiskImage`` has no opinion on what a caller does with
#: this — the integrity ledger uses it to record provenance, tests use it to
#: assert access patterns, and the default is to not attach one at all.
ReadHook = Callable[[int, int], None]

#: A conservative default: large enough that sequential hashing of a
#: multi-terabyte image isn't dominated by per-call overhead, small enough
#: that a bounded number of chunks are ever resident.
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB


class ImageSource(Protocol):
    """What :class:`DiskImage` needs from a concrete backing store."""

    @property
    def size(self) -> int: ...

    def read_raw(self, offset: int, length: int) -> bytes:
        """Read exactly ``length`` bytes starting at ``offset``.

        Implementations may assume the caller has already bounds-checked the
        request against :attr:`size` — that is ``DiskImage``'s job, done once,
        so every backing store doesn't have to repeat it.
        """
        ...

    def close(self) -> None: ...


class _FileBackedSource(ABC):
    """Shared machinery for sources backed by a single opened file handle."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        try:
            # Deliberately not a `with open(...)` block: the handle's
            # lifetime is tied to this object, closed explicitly in
            # close()/__exit__, not to a single scoped statement.
            self._fh = open(self._path, "rb")  # noqa: SIM115
        except OSError as exc:
            raise ImageOpenError(f"cannot open {self._path} for reading: {exc}") from exc

        self._size = os.fstat(self._fh.fileno()).st_size

        self._mmap: mmap.mmap | None = None
        if self._size > 0:
            try:
                self._mmap = mmap.mmap(
                    self._fh.fileno(), 0, access=mmap.ACCESS_READ
                )
            except (OSError, ValueError):
                # Some sources (named pipes, certain device special files)
                # cannot be mmap'd. Fall back to seek+read; still read-only,
                # still correct, just without the zero-copy fast path.
                self._mmap = None

    @property
    def size(self) -> int:
        return self._size

    def read_raw(self, offset: int, length: int) -> bytes:
        if self._mmap is not None:
            return bytes(self._mmap[offset : offset + length])
        self._fh.seek(offset)
        data = self._fh.read(length)
        if len(data) != length:
            raise ImageBoundsError(offset, length, self._size)
        return data

    def close(self) -> None:
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None
        self._fh.close()


class RawImageSource(_FileBackedSource):
    """A flat raw/dd image file, or a raw physical device path.

    This is deliberately the only concrete source shipped today. Every DVR
    filesystem profile in this project is written against a byte-addressed
    view of the media — E01/AFF4 support is a matter of decompressing into
    the same view, not a different contract.
    """


class DiskImage:
    """A read-only, bounds-checked, provenance-observable view of a source.

    ``DiskImage`` never exposes a way to write. If you find yourself wanting
    one, the change belongs in a different tool, not here.
    """

    def __init__(
        self,
        source: str | Path | ImageSource,
        *,
        on_read: ReadHook | None = None,
    ) -> None:
        self._source: ImageSource = (
            source if not isinstance(source, (str, Path)) else RawImageSource(source)
        )
        self._on_read = on_read
        self._closed = False

    @property
    def size(self) -> int:
        return self._source.size

    def read(self, offset: int, length: int) -> bytes:
        """Read ``length`` bytes at ``offset``. Raises :class:`ImageBoundsError`
        if the request falls outside the image, instead of silently
        truncating — a truncated read that goes unnoticed is exactly the
        kind of bug that produces a wrong offset in a filesystem parser.
        """
        if self._closed:
            raise ValueError("read from a closed DiskImage")
        if offset < 0 or length < 0 or offset + length > self._source.size:
            raise ImageBoundsError(offset, length, self._source.size)

        data = self._source.read_raw(offset, length)

        if self._on_read is not None:
            self._on_read(offset, length)

        return data

    def iter_chunks(
        self, chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> Iterator[tuple[int, bytes]]:
        """Yield ``(offset, chunk)`` sequentially across the whole image.

        Used by the hashing pass and by any full-image scan (signature
        search, carving). Reading through this — rather than each caller
        doing its own offset arithmetic — is what keeps the ``on_read`` hook
        meaningful as a complete provenance trail.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        offset = 0
        size = self._source.size
        while offset < size:
            length = min(chunk_size, size - offset)
            yield offset, self.read(offset, length)
            offset += length

    def close(self) -> None:
        if not self._closed:
            self._source.close()
            self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def __len__(self) -> int:
        return self._source.size
