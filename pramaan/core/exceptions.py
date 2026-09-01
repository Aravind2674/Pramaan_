"""Exceptions raised by the acquisition layer."""

from __future__ import annotations


class PramaanCoreError(Exception):
    """Base class for all acquisition-layer errors."""


class ImageBoundsError(PramaanCoreError):
    """Raised when a read is requested outside the bounds of the image.

    This is deliberately its own exception type rather than letting a
    ``ValueError`` or ``IndexError`` propagate: a caller in the filesystem or
    recovery layers needs to distinguish "the profile's offset math is wrong"
    (a bug to fix) from other I/O failures (a bad source to report).
    """

    def __init__(self, offset: int, length: int, image_size: int) -> None:
        self.offset = offset
        self.length = length
        self.image_size = image_size
        super().__init__(
            f"read of {length} byte(s) at offset {offset} exceeds image "
            f"bounds (image size {image_size} bytes)"
        )


class ImageOpenError(PramaanCoreError):
    """Raised when a source cannot be opened for read-only acquisition."""
