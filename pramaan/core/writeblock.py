r"""
Write-block attestation.

Being precise about what this module actually proves matters more than what
it sounds like it proves. A *hardware* write-blocker sits between the media
and the host and refuses write commands at the electrical/protocol level —
nothing running on the host can verify that from software with certainty,
because a sufficiently determined write attempt is exactly what the blocker
exists to intercept, and the host cannot distinguish "blocked" from "blocked
and lying about it" without independent hardware.

What this module *can* do, honestly: attempt to open the source for writing
and record whether the OS itself refused. For a raw physical device
(``\\.\PhysicalDriveN`` on Windows, ``/dev/sdX`` on Linux) protected by a
hardware blocker or an OS-level read-only flag, that attempt will fail with
``PermissionError`` or ``OSError`` — a real, useful signal. For an ordinary
file (an already-acquired image sitting on a working copy), the same open
will normally *succeed*, because the file itself is just a file; protection
there is a matter of filesystem permissions and procedure, not physics.

So: this produces an **attestation**, not a guarantee, and it says so on
every result. The result is recorded in the integrity ledger either way —
"we checked and here is what we found" is the honest claim, not "verified
write-blocked."
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WriteBlockAttestation:
    """The recorded outcome of one write-block check against one source."""

    path: str
    write_open_refused: bool
    detail: str

    def as_ledger_entry(self) -> dict[str, str | bool]:
        """Shape this attestation for the integrity ledger (see
        :mod:`pramaan.integrity`), which records it verbatim rather than
        re-deriving or paraphrasing it.
        """
        return {
            "path": self.path,
            "write_open_refused": self.write_open_refused,
            "detail": self.detail,
        }


def verify_source_read_only(path: str | Path) -> WriteBlockAttestation:
    """Attempt to open ``path`` for writing, without writing a single byte,
    and record whether the OS refused.

    The attempt opens in ``"r+b"`` (read+write, must already exist, no
    truncation) specifically so that if the open *does* succeed, closing it
    immediately leaves the source byte-for-byte untouched.
    """
    path = Path(path)
    try:
        fh = os.open(path, os.O_RDWR)
    except PermissionError as exc:
        return WriteBlockAttestation(
            path=str(path),
            write_open_refused=True,
            detail=f"OS refused a read-write open ({exc.strerror}); "
            "consistent with a hardware or OS-level write-blocker, "
            "but not a substitute for one.",
        )
    except OSError as exc:
        # Some other reason the write-open failed (e.g. the device is busy).
        # Still refused, but say what actually happened rather than
        # collapsing every failure into "blocked".
        return WriteBlockAttestation(
            path=str(path),
            write_open_refused=True,
            detail=f"read-write open failed: {exc}",
        )
    else:
        os.close(fh)
        return WriteBlockAttestation(
            path=str(path),
            write_open_refused=False,
            detail="OS permitted a read-write open. This source is an "
            "ordinary writable file or an unblocked device — protection "
            "must come from procedure (a working copy, filesystem "
            "permissions) rather than from this check. Pramaan itself "
            "never performs a write through DiskImage regardless of this "
            "result.",
        )
