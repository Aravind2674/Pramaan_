"""
Single-pass, multi-algorithm hashing of an acquired image.

Hashing a multi-terabyte image is not cheap, so it is computed exactly once,
during the same sequential pass that acquisition already has to make, rather
than as a second read-through. ``StreamingHash`` updates every requested
algorithm from the same chunk, so the cost of hashing N algorithms is one
read plus N digest updates, not N reads.

Algorithm choice matters for a reason specific to this project: the
Bharatiya Sakshya Adhiniyam 2023 certificate schedule (Part A / Part B) asks
the examiner to tick a box among SHA1, SHA256, MD5, or "Other" — so the tool
needs to be *able* to produce SHA-1 and MD5 on request even though neither is
a sound choice for anything security-sensitive. Default to SHA-256 (and
BLAKE2b as a fast, modern second witness); never default to SHA-1 or MD5.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from typing import Protocol

from pramaan.core.image import DEFAULT_CHUNK_SIZE, DiskImage


class _Digest(Protocol):
    """The subset of hashlib's hash-object interface this module needs.

    Defined structurally rather than reused from ``hashlib._Hash`` because
    typeshed does not model ``blake2b``/``blake2s`` as subtypes of that
    common type, even though they satisfy the same interface at runtime —
    matching what we actually call is more robust than matching a class
    hierarchy that doesn't reflect it.
    """

    def update(self, data: bytes, /) -> None: ...
    def hexdigest(self) -> str: ...


#: Algorithms the BSA 2023 Schedule form recognises by name, plus the two we
#: default to. Anything else in this dict is rejected up front rather than
#: failing deep inside hashlib with a less useful error.
_HashConstructor = Callable[[], _Digest]
_SUPPORTED: dict[str, _HashConstructor] = {
    "sha256": hashlib.sha256,
    "blake2b": hashlib.blake2b,
    "sha1": hashlib.sha1,
    "md5": hashlib.md5,
}

DEFAULT_ALGORITHMS: tuple[str, ...] = ("sha256", "blake2b")

ProgressCallback = Callable[[int, int], None]


class StreamingHash:
    """Accumulates one or more digests over a sequence of byte chunks."""

    def __init__(self, algorithms: Iterable[str] = DEFAULT_ALGORITHMS) -> None:
        algorithms = tuple(algorithms)
        if not algorithms:
            raise ValueError("at least one hash algorithm is required")
        unknown = set(algorithms) - _SUPPORTED.keys()
        if unknown:
            raise ValueError(
                f"unsupported hash algorithm(s): {sorted(unknown)}; "
                f"supported: {sorted(_SUPPORTED)}"
            )
        self._hashers = {name: _SUPPORTED[name]() for name in algorithms}
        self._bytes_seen = 0

    def update(self, chunk: bytes) -> None:
        for hasher in self._hashers.values():
            hasher.update(chunk)
        self._bytes_seen += len(chunk)

    @property
    def bytes_seen(self) -> int:
        return self._bytes_seen

    def hexdigests(self) -> dict[str, str]:
        """Digests computed so far, keyed by algorithm name (e.g. ``"sha256"``)."""
        return {name: hasher.hexdigest() for name, hasher in self._hashers.items()}


def hash_image(
    image: DiskImage,
    algorithms: Iterable[str] = DEFAULT_ALGORITHMS,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    on_progress: ProgressCallback | None = None,
) -> dict[str, str]:
    """Hash an entire :class:`DiskImage` in one sequential pass.

    ``on_progress(bytes_hashed, total_bytes)`` is invoked after every chunk —
    intended for a determinate progress bar during acquisition of a large
    image, per the "never show an indeterminate spinner when a byte count is
    available" rule for this tool's UI.
    """
    hasher = StreamingHash(algorithms)
    total = image.size
    for _offset, chunk in image.iter_chunks(chunk_size):
        hasher.update(chunk)
        if on_progress is not None:
            on_progress(hasher.bytes_seen, total)
    return hasher.hexdigests()
