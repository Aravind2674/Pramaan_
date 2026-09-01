"""
Acquisition layer.

Everything in this package touches the seized source. The one rule that
overrides every other design consideration here: evidence is never modified.
`DiskImage` cannot be opened for writing — that is enforced by the type, not
by convention — and every read can be observed by an external audit hook
without this package needing to know anything about the integrity ledger
that consumes it.
"""

from pramaan.core.exceptions import ImageBoundsError, PramaanCoreError
from pramaan.core.hashing import StreamingHash, hash_image
from pramaan.core.image import DiskImage
from pramaan.core.writeblock import WriteBlockAttestation, verify_source_read_only

__all__ = [
    "DiskImage",
    "ImageBoundsError",
    "PramaanCoreError",
    "StreamingHash",
    "WriteBlockAttestation",
    "hash_image",
    "verify_source_read_only",
]
