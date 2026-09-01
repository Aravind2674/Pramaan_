"""Tests for pramaan.fs.registry — vendor fingerprinting."""

from __future__ import annotations

import struct

from pramaan.core.image import DiskImage
from pramaan.fs.profile import Signature, VendorProfile
from pramaan.fs.registry import DEFAULT_PROFILE_DIR, FingerprintMatch, fingerprint, load_profiles


def _dahua_chunk(channel: int, frame_number: int, payload_len: int = 100) -> bytes:
    frame_length = 20 + payload_len
    header = (
        b"DHAV"
        + struct.pack("<B", 0xFD)
        + struct.pack("<B", 0)
        + struct.pack("<B", channel)
        + struct.pack("<B", 0)
        + struct.pack("<I", frame_number)
        + struct.pack("<I", frame_length)
        + struct.pack("<I", 0)  # date_packed, unused by this test
    )
    return header + b"\x00" * payload_len


def test_load_bundled_profiles_does_not_raise():
    profiles = load_profiles(DEFAULT_PROFILE_DIR)
    assert len(profiles) >= 2


def test_fingerprint_identifies_dahua_image(tmp_path):
    blob = b"".join(_dahua_chunk(channel=1, frame_number=i) for i in range(6))
    img_path = tmp_path / "dahua.raw"
    img_path.write_bytes(blob)

    profiles = load_profiles(DEFAULT_PROFILE_DIR)
    with DiskImage(img_path) as img:
        matches = fingerprint(img, profiles)

    assert matches, "expected at least one profile to match a genuine DHAV image"
    top = matches[0]
    assert top.profile.format_id == "dahua_dhav_chunk"
    assert top.match_count == 6
    assert top.confidence_label == "strong"


def test_fingerprint_does_not_falsely_match_unrelated_data(tmp_path):
    img_path = tmp_path / "random.raw"
    img_path.write_bytes(b"\x00\x01\x02\x03" * 10_000)

    profiles = load_profiles(DEFAULT_PROFILE_DIR)
    with DiskImage(img_path) as img:
        matches = fingerprint(img, profiles)

    assert matches == []


def test_fingerprint_ranks_strongest_match_first(tmp_path):
    # Six real Dahua chunks plus, elsewhere in the same image, a single
    # decoy 4-byte sequence that happens to share Dahua's magic bytes but
    # fails the type-byte check right after it — it must not count as a
    # match at all, and must not outrank the six genuine chunks.
    dahua_blob = b"".join(_dahua_chunk(channel=0, frame_number=i) for i in range(6))
    decoy = b"DHAV" + b"\x99"  # 0x99 is not a valid Dahua chunk type
    img_path = tmp_path / "mixed.raw"
    img_path.write_bytes(dahua_blob + decoy)

    profiles = load_profiles(DEFAULT_PROFILE_DIR)
    with DiskImage(img_path) as img:
        matches = fingerprint(img, profiles)

    assert matches[0].profile.format_id == "dahua_dhav_chunk"
    assert matches[0].match_count == 6  # decoy correctly excluded


def test_fingerprint_uses_bundled_profiles_by_default(tmp_path):
    """Calling fingerprint() with no explicit profile list must fall back to
    the bundled profile directory, not silently return an empty result."""
    blob = b"".join(_dahua_chunk(channel=0, frame_number=i) for i in range(3))
    img_path = tmp_path / "dahua.raw"
    img_path.write_bytes(blob)

    with DiskImage(img_path) as img:
        matches = fingerprint(img)  # no `profiles` argument

    assert any(m.profile.format_id == "dahua_dhav_chunk" for m in matches)


def _dummy_profile() -> VendorProfile:
    return VendorProfile(
        vendor="dummy", format_id="dummy", display_name="dummy", version="1",
        confidence="verified", endian="little",
        signature=Signature(offset=0, pattern=b"X"), fields=(),
    )


def test_confidence_label_thresholds():
    profile = _dummy_profile()
    assert FingerprintMatch(profile, match_count=0, first_offset=0).confidence_label == "none"
    assert FingerprintMatch(profile, match_count=1, first_offset=0).confidence_label == "weak"
    assert FingerprintMatch(profile, match_count=2, first_offset=0).confidence_label == "weak"
    assert FingerprintMatch(profile, match_count=3, first_offset=0).confidence_label == "strong"
    assert FingerprintMatch(profile, match_count=100, first_offset=0).confidence_label == "strong"
