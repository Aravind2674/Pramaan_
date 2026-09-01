"""
Vendor fingerprinting: given an image and a directory of known profiles,
report which ones plausibly match.

This deliberately returns *ranked candidates*, never a single confident
answer picked on the tool's behalf. A DVR filesystem is exactly the kind of
input where a false positive (misidentifying the vendor) is worse than an
honest "no match" — misparsing a Hikvision disk as Dahua produces confident,
wrong timestamps, which is a worse outcome for an investigation than the
tool admitting it doesn't recognise the format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pramaan.core.image import DiskImage
from pramaan.fs.profile import FilesystemInterpreter, VendorProfile, load_profile

DEFAULT_PROFILE_DIR = Path(__file__).parent / "profiles"


@dataclass(frozen=True)
class FingerprintMatch:
    profile: VendorProfile
    match_count: int
    first_offset: int

    @property
    def confidence_label(self) -> str:
        """A human-facing confidence label, distinct from the profile's own
        ``confidence`` field (which describes how well-sourced the *profile*
        is, not how strong *this particular match* is)."""
        if self.match_count >= 3:
            return "strong"
        if self.match_count >= 1:
            return "weak"
        return "none"


def load_profiles(directory: Path = DEFAULT_PROFILE_DIR) -> list[VendorProfile]:
    """Load every ``*.yaml`` profile in ``directory``.

    A profile that fails to load is skipped with its error surfaced via a
    raised exception at load time — this function does not swallow a bad
    profile silently, since a vendor going missing from the registry without
    a visible error is exactly the kind of failure an examiner would never
    notice until it was too late.
    """
    return [load_profile(p) for p in sorted(directory.glob("*.yaml"))]


def fingerprint(
    image: DiskImage, profiles: list[VendorProfile] | None = None
) -> list[FingerprintMatch]:
    """Test ``image`` against every profile in ``profiles`` (or the bundled
    set, if not given) and return matches ranked strongest-first.

    A profile with zero signature matches anywhere in the image is omitted
    entirely, rather than included with a zero score — the caller should
    never have to filter "no match" entries out of the result themselves.
    """
    if profiles is None:
        profiles = load_profiles()

    results: list[FingerprintMatch] = []
    for profile in profiles:
        interpreter = FilesystemInterpreter(profile, image)
        offsets = list(interpreter.find_signatures())
        if offsets:
            results.append(
                FingerprintMatch(
                    profile=profile, match_count=len(offsets), first_offset=offsets[0]
                )
            )

    results.sort(key=lambda m: m.match_count, reverse=True)
    return results
