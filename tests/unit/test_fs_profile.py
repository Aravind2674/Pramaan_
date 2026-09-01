"""
Tests for pramaan.fs.profile — the vendor-profile interpreter.

`test_shipped_profiles_are_well_formed` and `test_dahua_bitfield_date_decode`
are the two tests that matter most: they check the actual profiles this
project ships, not just the interpreter machinery in the abstract.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
import yaml

from pramaan.core.image import DiskImage
from pramaan.fs.profile import (
    DecodeError,
    FilesystemInterpreter,
    ProfileError,
    load_profile,
)
from pramaan.fs.registry import DEFAULT_PROFILE_DIR, load_profiles

SYNTHETIC_PROFILE = {
    "vendor": "testvendor",
    "format_id": "testvendor_record",
    "display_name": "Synthetic test record",
    "version": "1.0",
    "confidence": "verified",
    "endian": "little",
    "signature": {"offset": 0, "ascii": "TVR1", "recurring": True},
    "fields": [
        {"name": "magic", "offset": 0, "size": 4, "dtype": "ascii", "status": "confirmed"},
        {"name": "channel", "offset": 4, "size": 1, "dtype": "u8", "status": "confirmed", "role": "channel"},
        {"name": "seq", "offset": 5, "size": 4, "dtype": "u32", "status": "confirmed", "role": "sequence"},
        {
            "name": "packed",
            "offset": 9,
            "size": 4,
            "dtype": "bitfields",
            "status": "confirmed",
            "bitfields": [
                {"name": "low", "shift": 0, "bits": 8},
                {"name": "mid", "shift": 8, "bits": 8},
                {"name": "high_plus_100", "shift": 16, "bits": 16, "add": 100},
            ],
        },
    ],
}


def _write_profile(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "profile.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


def _pack_record(channel: int, seq: int, packed: int) -> bytes:
    return b"TVR1" + struct.pack("<B", channel) + struct.pack("<I", seq) + struct.pack("<I", packed)


def test_load_and_decode_a_synthetic_record(tmp_path):
    profile_path = _write_profile(tmp_path, SYNTHETIC_PROFILE)
    profile = load_profile(profile_path)
    assert profile.vendor == "testvendor"
    assert profile.confidence == "verified"

    record_bytes = _pack_record(channel=3, seq=999, packed=(100 << 16) | (7 << 8) | 42)
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(record_bytes)

    with DiskImage(img_path) as img:
        interp = FilesystemInterpreter(profile, img)
        record = interp.read_record(0)

    assert record["magic"] == "TVR1"
    assert record["channel"] == 3
    assert record["seq"] == 999
    assert record["packed"] == {"low": 42, "mid": 7, "high_plus_100": 200}


def test_recurring_signature_finds_every_occurrence(tmp_path):
    profile = load_profile(_write_profile(tmp_path, SYNTHETIC_PROFILE))
    records = [
        _pack_record(channel=i, seq=i * 10, packed=0) for i in range(5)
    ]
    # Interleave with non-matching filler so the scanner has to actually
    # search, not just assume records are back-to-back.
    blob = b"".join(r + b"\xff\xff\xff" for r in records)
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(blob)

    with DiskImage(img_path) as img:
        interp = FilesystemInterpreter(profile, img)
        offsets = list(interp.find_signatures())

        assert len(offsets) == 5
        for i, offset in enumerate(offsets):
            record = interp.read_record(offset)
            assert record["channel"] == i
            assert record["seq"] == i * 10


def test_non_recurring_signature_checks_only_declared_offset(tmp_path):
    doc = dict(SYNTHETIC_PROFILE)
    doc["signature"] = {"offset": 20, "ascii": "TVR1", "recurring": False}
    profile = load_profile(_write_profile(tmp_path, doc))

    # A matching pattern exists at offset 0 too, but recurring=False must
    # ignore it and check ONLY offset 20.
    blob = _pack_record(1, 1, 0).ljust(20, b"\x00") + _pack_record(2, 2, 0)
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(blob)

    with DiskImage(img_path) as img:
        interp = FilesystemInterpreter(profile, img)
        offsets = list(interp.find_signatures())

    assert offsets == [20]


def test_decode_error_when_record_exceeds_image_bounds(tmp_path):
    profile = load_profile(_write_profile(tmp_path, SYNTHETIC_PROFILE))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(b"TVR1\x01")  # magic + channel, but seq/packed missing

    with DiskImage(img_path) as img:
        interp = FilesystemInterpreter(profile, img)
        with pytest.raises(DecodeError):
            interp.read_record(0)


def test_invalid_profile_fails_schema_validation(tmp_path):
    bad = dict(SYNTHETIC_PROFILE)
    del bad["endian"]  # required by the schema
    with pytest.raises(ProfileError):
        load_profile(_write_profile(tmp_path, bad))


def test_bitfields_field_requires_bitfields_list(tmp_path):
    bad = {
        **SYNTHETIC_PROFILE,
        "fields": [
            {"name": "packed", "offset": 0, "size": 4, "dtype": "bitfields", "status": "confirmed"}
        ],
    }
    with pytest.raises(ProfileError):
        load_profile(_write_profile(tmp_path, bad))


def test_field_by_name_lookup(tmp_path):
    profile = load_profile(_write_profile(tmp_path, SYNTHETIC_PROFILE))
    assert profile.field_by_name("channel").role == "channel"
    with pytest.raises(KeyError):
        profile.field_by_name("does_not_exist")


def test_record_size_is_end_of_last_field(tmp_path):
    profile = load_profile(_write_profile(tmp_path, SYNTHETIC_PROFILE))
    # "packed" is offset 9, size 4 -> the furthest-reaching field.
    assert profile.record_size == 13


def test_record_size_of_profile_with_no_fields_is_zero():
    # record_size must not raise on the degenerate empty case even though
    # the schema requires at least one field in practice — the property
    # itself should still be well-defined.
    from pramaan.fs.profile import Signature, VendorProfile

    empty = VendorProfile(
        vendor="v", format_id="v", display_name="v", version="1",
        confidence="verified", endian="little",
        signature=Signature(offset=0, pattern=b"X"), fields=(),
    )
    assert empty.record_size == 0


def test_signature_resolved_from_bytes_hex(tmp_path):
    doc = dict(SYNTHETIC_PROFILE)
    doc["signature"] = {"offset": 0, "bytes_hex": "54565231", "recurring": True}  # "TVR1"
    profile = load_profile(_write_profile(tmp_path, doc))

    img_path = tmp_path / "img.raw"
    img_path.write_bytes(_pack_record(1, 1, 0))
    with DiskImage(img_path) as img:
        interp = FilesystemInterpreter(profile, img)
        assert list(interp.find_signatures()) == [0]


def test_bytes_dtype_returns_raw_bytes(tmp_path):
    doc = {
        **SYNTHETIC_PROFILE,
        "fields": [
            {"name": "magic", "offset": 0, "size": 4, "dtype": "ascii", "status": "confirmed"},
            {"name": "raw_tail", "offset": 4, "size": 3, "dtype": "bytes", "status": "confirmed"},
        ],
    }
    profile = load_profile(_write_profile(tmp_path, doc))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(b"TVR1" + b"\x01\x02\x03")
    with DiskImage(img_path) as img:
        record = FilesystemInterpreter(profile, img).read_record(0)
    assert record["raw_tail"] == b"\x01\x02\x03"


def test_signature_with_offset_beyond_image_never_matches(tmp_path):
    doc = dict(SYNTHETIC_PROFILE)
    doc["signature"] = {"offset": 1000, "ascii": "TVR1", "recurring": False}
    profile = load_profile(_write_profile(tmp_path, doc))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(b"TVR1")  # far shorter than offset 1000
    with DiskImage(img_path) as img:
        assert list(FilesystemInterpreter(profile, img).find_signatures()) == []


def test_type_byte_check_fails_closed_when_it_would_read_past_end(tmp_path):
    """If the byte immediately after the signature (checked against
    valid_type_bytes) would fall outside the image, that must count as
    'no match' — not raise, and not silently accept it."""
    doc = dict(SYNTHETIC_PROFILE)
    doc["signature"] = {
        "offset": 0, "ascii": "TVR1", "recurring": False,
        "valid_type_bytes": [0xAB],
    }
    profile = load_profile(_write_profile(tmp_path, doc))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(b"TVR1")  # signature present, but no type byte follows
    with DiskImage(img_path) as img:
        assert list(FilesystemInterpreter(profile, img).find_signatures()) == []


# ---------------------------------------------------------------------------
# The profiles this project actually ships
# ---------------------------------------------------------------------------

def test_shipped_profiles_are_well_formed():
    profiles = load_profiles(DEFAULT_PROFILE_DIR)
    ids = {p.format_id for p in profiles}
    assert "dahua_dhav_chunk" in ids
    assert "hikvision_master_sector" in ids


def test_dahua_bitfield_date_decode():
    """Reproduce the exact worked example from FFmpeg's get_timeinfo():
    verify our declarative bitfield decode matches hand-computed values for
    a specific, arbitrary date/time rather than trusting the formula by
    inspection alone."""
    profile = load_profile(DEFAULT_PROFILE_DIR / "dahua_dhav.yaml")

    # Encode 2024-03-14 21:48:49 using the documented packing, independently
    # of any Pramaan code, to prove the interpreter decodes it correctly.
    year, month, day, hour, minute, second = 2024, 3, 14, 21, 48, 49
    packed = (
        (second & 0x3F)
        | ((minute & 0x3F) << 6)
        | ((hour & 0x1F) << 12)
        | ((day & 0x1F) << 17)
        | ((month & 0x0F) << 22)
        | (((year - 2000) & 0x3F) << 26)
    )

    header = (
        b"DHAV"
        + struct.pack("<B", 0xFD)  # type: video
        + struct.pack("<B", 0)     # subtype
        + struct.pack("<B", 2)     # channel
        + struct.pack("<B", 0)     # frame_subnumber
        + struct.pack("<I", 12345)  # frame_number
        + struct.pack("<I", 4096)   # frame_length
        + struct.pack("<I", packed)  # date_packed
    )
    img_path_bytes = header
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(img_path_bytes)
        tf_path = tf.name

    try:
        with DiskImage(tf_path) as img:
            interp = FilesystemInterpreter(profile, img)
            record = interp.read_record(0)
    finally:
        Path(tf_path).unlink()

    assert record["magic"] == "DHAV"
    assert record["channel"] == 2
    assert record["frame_number"] == 12345
    assert record["date_packed"] == {
        "second": 49,
        "minute": 48,
        "hour": 21,
        "day": 14,
        "month": 3,
        "year": 2024,
    }
