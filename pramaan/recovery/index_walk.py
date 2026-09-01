"""
Recovery via an intact index: walk every record a known vendor profile can
find, and group them into clips.

This only needs a profile whose signature is ``recurring`` (a per-record
container header, like Dahua's DHAV chunks) and that tags a ``channel`` and
a ``sequence`` field by role — it works for any such profile without
knowing the vendor, which is the point of tagging fields by role rather than
by name in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from pramaan.core.image import DiskImage
from pramaan.fs.profile import DecodeError, FilesystemInterpreter, ProfileField, VendorProfile


class IndexWalkError(Exception):
    """Raised when a profile lacks a role-tagged field this walk needs."""


@dataclass(frozen=True)
class ClipRecord:
    """A contiguous run of records on one channel, found via an intact index."""

    channel: int
    start_offset: int
    end_offset: int
    frame_count: int
    first_sequence: int
    last_sequence: int
    format_id: str


def _field_with_role(profile: VendorProfile, role: str) -> ProfileField:
    for f in profile.fields:
        if f.role == role:
            return f
    raise IndexWalkError(
        f"profile {profile.format_id!r} has no field with role={role!r}; "
        "index_walk requires a channel and a sequence field to be tagged"
    )


def _field_with_role_optional(profile: VendorProfile, role: str) -> ProfileField | None:
    for f in profile.fields:
        if f.role == role:
            return f
    return None


def walk_container_records(profile: VendorProfile, image: DiskImage) -> list[ClipRecord]:
    """Find every record the profile's signature matches, and group
    consecutive same-channel, sequence-contiguous records into clips.

    Channels are tracked independently, each with its own "currently open"
    clip — a multi-camera recorder ordinarily interleaves channels'
    records on disk (round-robin across cameras), so a channel-0 record is
    not usually immediately followed by the next channel-0 record. Tracking
    a single "current" clip regardless of channel would treat that
    ordinary interleaving as constant discontinuity and never group
    anything into more than one record.

    A signature match too close to the end of the image to hold a full
    record is skipped rather than aborting the walk — a truncated final
    record at the tail of a disk image is an expected, ordinary occurrence,
    not a reason to discard everything found before it.
    """
    channel_field = _field_with_role(profile, "channel")
    sequence_field = _field_with_role(profile, "sequence")
    length_field = _field_with_role_optional(profile, "length")

    interpreter = FilesystemInterpreter(profile, image)
    rows: list[tuple[int, int, int, int]] = []  # (offset, channel, sequence, record_length)
    for offset in interpreter.find_signatures():
        try:
            record = interpreter.read_record(offset)
        except DecodeError:
            continue
        length = record[length_field.name] if length_field is not None else profile.record_size
        rows.append((offset, record[channel_field.name], record[sequence_field.name], length))

    rows.sort(key=lambda r: r[0])

    open_clips: dict[int, ClipRecord] = {}
    clips: list[ClipRecord] = []
    for offset, channel, sequence, length in rows:
        end_offset = offset + length
        existing = open_clips.get(channel)
        if existing is not None and sequence == existing.last_sequence + 1:
            open_clips[channel] = replace(
                existing,
                end_offset=end_offset,
                last_sequence=sequence,
                frame_count=existing.frame_count + 1,
            )
        else:
            if existing is not None:
                clips.append(existing)
            open_clips[channel] = ClipRecord(
                channel=channel,
                start_offset=offset,
                end_offset=end_offset,
                frame_count=1,
                first_sequence=sequence,
                last_sequence=sequence,
                format_id=profile.format_id,
            )
    clips.extend(open_clips.values())

    return sorted(clips, key=lambda c: c.start_offset)
