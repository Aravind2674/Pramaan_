"""Tests for pramaan.recovery.index_walk, exercised against the real,
shipped Dahua DHAV profile rather than a synthetic stand-in -- this is the
first recovery-layer test that proves out an actual vendor profile, not
just the mechanism in the abstract."""

from __future__ import annotations

import struct

import pytest
import yaml

from pramaan.core.image import DiskImage
from pramaan.fs.profile import load_profile
from pramaan.fs.registry import DEFAULT_PROFILE_DIR
from pramaan.recovery.index_walk import IndexWalkError, walk_container_records

DAHUA_PROFILE = load_profile(DEFAULT_PROFILE_DIR / "dahua_dhav.yaml")


def _dahua_chunk(channel: int, frame_number: int, payload_len: int = 50) -> bytes:
    frame_length = 20 + payload_len
    header = (
        b"DHAV"
        + struct.pack("<B", 0xFD)
        + struct.pack("<B", 0)
        + struct.pack("<B", channel)
        + struct.pack("<B", 0)
        + struct.pack("<I", frame_number)
        + struct.pack("<I", frame_length)
        + struct.pack("<I", 0)
    )
    return header + b"\x00" * payload_len


def test_contiguous_sequence_on_one_channel_forms_one_clip(tmp_path):
    blob = b"".join(_dahua_chunk(channel=0, frame_number=i) for i in range(5))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(blob)
    with DiskImage(img_path) as img:
        clips = walk_container_records(DAHUA_PROFILE, img)

    assert len(clips) == 1
    clip = clips[0]
    assert clip.channel == 0
    assert clip.first_sequence == 0
    assert clip.last_sequence == 4
    assert clip.frame_count == 5
    assert clip.start_offset == 0
    assert clip.end_offset == len(blob)
    assert clip.format_id == "dahua_dhav_chunk"


def test_a_gap_in_sequence_splits_into_two_clips(tmp_path):
    chunks = [_dahua_chunk(0, i) for i in (0, 1, 2)] + [_dahua_chunk(0, i) for i in (5, 6)]
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(b"".join(chunks))
    with DiskImage(img_path) as img:
        clips = walk_container_records(DAHUA_PROFILE, img)

    assert len(clips) == 2
    assert (clips[0].first_sequence, clips[0].last_sequence) == (0, 2)
    assert (clips[1].first_sequence, clips[1].last_sequence) == (5, 6)


def test_interleaved_channels_are_tracked_independently(tmp_path):
    # Byte-interleaved on disk, but each channel's sequence is contiguous on
    # its own -- a realistic layout for a multi-camera recorder writing
    # channels round-robin into the same region.
    chunks = []
    for i in range(4):
        chunks.append(_dahua_chunk(channel=0, frame_number=i))
        chunks.append(_dahua_chunk(channel=1, frame_number=i))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(b"".join(chunks))

    with DiskImage(img_path) as img:
        clips = walk_container_records(DAHUA_PROFILE, img)

    by_channel = {c.channel: c for c in clips}
    # Each channel's own run is contiguous (0,1,2,3), but because they
    # alternate on disk, a channel-0 chunk is never immediately followed by
    # the next channel-0 chunk -- the walk groups by (channel, sequence)
    # continuity regardless of what sits between them on disk, so this
    # should still be one clip per channel.
    assert set(by_channel) == {0, 1}
    assert by_channel[0].frame_count == 4
    assert by_channel[1].frame_count == 4


def test_truncated_trailing_chunk_is_skipped_not_fatal(tmp_path):
    good = _dahua_chunk(0, 0)
    truncated = b"DHAV" + struct.pack("<B", 0xFD) + b"\x00\x00\x00"  # far short of a full header
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(good + truncated)

    with DiskImage(img_path) as img:
        clips = walk_container_records(DAHUA_PROFILE, img)

    assert len(clips) == 1
    assert clips[0].frame_count == 1


def test_empty_image_yields_no_clips(tmp_path):
    img_path = tmp_path / "empty.raw"
    img_path.write_bytes(b"")
    with DiskImage(img_path) as img:
        assert walk_container_records(DAHUA_PROFILE, img) == []


def test_missing_length_role_falls_back_to_profiles_record_size(tmp_path):
    """A profile with no length-role field must still work -- each record's
    extent falls back to the profile's declared record_size rather than
    requiring every profile to name a length field."""
    doc = yaml.safe_load((DEFAULT_PROFILE_DIR / "dahua_dhav.yaml").read_text())
    doc["fields"] = [f for f in doc["fields"] if f.get("role") != "length"]
    profile_path = tmp_path / "no_length.yaml"
    profile_path.write_text(yaml.safe_dump(doc))
    profile = load_profile(profile_path)

    blob = b"".join(_dahua_chunk(channel=0, frame_number=i) for i in range(3))
    img_path = tmp_path / "img.raw"
    img_path.write_bytes(blob)
    with DiskImage(img_path) as img:
        clips = walk_container_records(profile, img)

    assert len(clips) == 1
    # record_size is the offset+size of the last declared field
    # (date_packed, at 16+4=20 bytes) -- much shorter than a real chunk's
    # true on-disk length (20-byte header + payload). With no length-role
    # field, the fallback is used for the LAST record's own extent, which
    # is what end_offset reports -- not the true on-disk stride between
    # records, which find_signatures locates independently regardless.
    last_chunk_offset = 2 * (20 + 50)  # two prior 70-byte chunks precede it
    assert clips[0].start_offset == 0
    assert clips[0].end_offset == last_chunk_offset + profile.record_size


def test_profile_missing_channel_role_raises_index_walk_error(tmp_path):
    doc = yaml.safe_load((DEFAULT_PROFILE_DIR / "dahua_dhav.yaml").read_text())
    doc["fields"] = [f for f in doc["fields"] if f.get("role") != "channel"]
    profile_path = tmp_path / "no_channel.yaml"
    profile_path.write_text(yaml.safe_dump(doc))
    profile = load_profile(profile_path)

    img_path = tmp_path / "img.raw"
    img_path.write_bytes(_dahua_chunk(0, 0))
    with DiskImage(img_path) as img, pytest.raises(IndexWalkError):
        walk_container_records(profile, img)
