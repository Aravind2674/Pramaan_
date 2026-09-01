"""
The vendor-profile interpreter.

A profile (see ``profile.schema.json``) declares a recorder's byte layout as
data; this module is the only code that has to understand *how* to read that
data. Everything here must degrade safely on hostile input — the whole point
of a forensic tool is that its input is a seized disk image, which is
attacker-controlled by definition. A malformed or deliberately booby-trapped
image must produce a clear decode error, never an unhandled exception that
crashes a case in progress and never a silent wrong answer.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import jsonschema
import yaml

from pramaan.core.image import DiskImage

_SCHEMA_CACHE: dict[str, Any] | None = None

_STRUCT_CODE = {
    "u8": "B", "u16": "H", "u32": "I", "u64": "Q",
    "i8": "b", "i16": "h", "i32": "i", "i64": "q",
}


class ProfileError(Exception):
    """Raised for a malformed profile document — a data-authoring bug, not a
    property of the image being examined."""


class DecodeError(Exception):
    """Raised when a record cannot be decoded from the image at a given
    offset — e.g. the read would run past the end of the image. This is
    expected and recoverable: a caller scanning many candidate offsets
    should catch this per-candidate and move on, not abort the scan."""


def _load_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        text = resources.files("pramaan.fs").joinpath("profile.schema.json").read_text()
        import json

        _SCHEMA_CACHE = json.loads(text)
    return _SCHEMA_CACHE


@dataclass(frozen=True)
class Bitfield:
    name: str
    shift: int
    bits: int
    add: int = 0

    def extract(self, raw: int) -> int:
        mask = (1 << self.bits) - 1
        return ((raw >> self.shift) & mask) + self.add


@dataclass(frozen=True)
class ProfileField:
    name: str
    offset: int
    size: int
    dtype: str
    endian: str  # already resolved against the profile default
    status: str
    role: str | None = None
    bitfields: tuple[Bitfield, ...] = ()
    note: str | None = None

    def decode(self, raw: bytes) -> Any:
        """Decode this field's raw bytes into a Python value.

        ``raw`` must be exactly ``self.size`` bytes — the caller
        (:class:`FilesystemInterpreter`) is responsible for slicing it out;
        this method only ever interprets bytes it has already been handed,
        so it never itself reaches outside the image.
        """
        if self.dtype == "ascii":
            return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
        if self.dtype == "bytes":
            return raw
        if self.dtype == "bitfields":
            order: Literal["little", "big"] = "little" if self.endian == "little" else "big"
            value = int.from_bytes(raw, order)
            return {bf.name: bf.extract(value) for bf in self.bitfields}

        code = _STRUCT_CODE[self.dtype]
        prefix = "<" if self.endian == "little" else ">"
        (value,) = struct.unpack(prefix + code, raw)
        return value


@dataclass(frozen=True)
class Signature:
    offset: int
    pattern: bytes
    recurring: bool = False
    valid_type_bytes: tuple[int, ...] = ()

    def matches_at(self, image: DiskImage, at: int) -> bool:
        if at < 0 or at + len(self.pattern) > image.size:
            return False
        if image.read(at, len(self.pattern)) != self.pattern:
            return False
        if self.valid_type_bytes:
            type_byte_offset = at + len(self.pattern)
            if type_byte_offset >= image.size:
                return False
            (type_byte,) = image.read(type_byte_offset, 1)
            if type_byte not in self.valid_type_bytes:
                return False
        return True


@dataclass(frozen=True)
class VendorProfile:
    vendor: str
    format_id: str
    display_name: str
    version: str
    confidence: str
    endian: str
    signature: Signature
    fields: tuple[ProfileField, ...]
    description: str | None = None
    source: str | None = None
    license_note: str | None = None
    notes: tuple[str, ...] = ()

    def field_by_name(self, name: str) -> ProfileField:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(f"profile {self.format_id!r} has no field named {name!r}")

    @property
    def record_size(self) -> int:
        """The number of bytes this profile's declared fields span, from the
        start of the record to the end of the last field. Not necessarily
        the true on-disk record size (padding/unknown trailing bytes are
        common) — this is a lower bound, and callers that need the real
        stride (e.g. a fixed block size) must get it from elsewhere.
        """
        return max((f.offset + f.size for f in self.fields), default=0)


def _resolve_signature_pattern(sig: dict[str, Any]) -> bytes:
    if "ascii" in sig:
        return sig["ascii"].encode("ascii")
    return bytes.fromhex(sig["bytes_hex"])


def load_profile(path: str | Path) -> VendorProfile:
    """Load and validate a vendor profile YAML file.

    Validation against ``profile.schema.json`` happens before any of the
    values are trusted — a profile with a typo'd offset should fail loudly
    at load time, not produce a silently wrong parse three layers downstream.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    try:
        jsonschema.validate(doc, _load_schema())
    except jsonschema.ValidationError as exc:
        raise ProfileError(f"{path}: schema validation failed: {exc.message}") from exc

    default_endian = doc["endian"]

    sig_doc = doc["signature"]
    signature = Signature(
        offset=sig_doc["offset"],
        pattern=_resolve_signature_pattern(sig_doc),
        recurring=sig_doc.get("recurring", False),
        valid_type_bytes=tuple(sig_doc.get("valid_type_bytes", ())),
    )

    fields = []
    for f in doc["fields"]:
        bitfields = tuple(
            Bitfield(name=bf["name"], shift=bf["shift"], bits=bf["bits"], add=bf.get("add", 0))
            for bf in f.get("bitfields", ())
        )
        fields.append(
            ProfileField(
                name=f["name"],
                offset=f["offset"],
                size=f["size"],
                dtype=f["dtype"],
                endian=f.get("endian", default_endian),
                status=f["status"],
                role=f.get("role"),
                bitfields=bitfields,
                note=f.get("note"),
            )
        )

    return VendorProfile(
        vendor=doc["vendor"],
        format_id=doc["format_id"],
        display_name=doc["display_name"],
        version=doc["version"],
        confidence=doc["confidence"],
        endian=default_endian,
        signature=signature,
        fields=tuple(fields),
        description=doc.get("description"),
        source=doc.get("source"),
        license_note=doc.get("license_note"),
        notes=tuple(doc.get("notes", ())),
    )


class FilesystemInterpreter:
    """Reads and decodes records from an image according to a compiled profile."""

    def __init__(self, profile: VendorProfile, image: DiskImage) -> None:
        self.profile = profile
        self.image = image

    def read_record(self, base_offset: int) -> dict[str, Any]:
        """Decode one record starting at ``base_offset``.

        Returns a mapping of field name to decoded value (a ``bitfields``
        field decodes to a nested ``dict``). Raises :class:`DecodeError` if
        any declared field would read past the end of the image — this is
        the normal, expected outcome when a caller probes a candidate offset
        that turns out not to be a real record.
        """
        record: dict[str, Any] = {}
        for f in self.profile.fields:
            start = base_offset + f.offset
            end = start + f.size
            if start < 0 or end > self.image.size:
                raise DecodeError(
                    f"field {f.name!r} at offset {start} (size {f.size}) "
                    f"exceeds image bounds (image size {self.image.size})"
                )
            raw = self.image.read(start, f.size)
            record[f.name] = f.decode(raw)
        return record

    def find_signatures(self) -> Iterator[int]:
        """Yield every offset in the image where the profile's signature
        matches.

        For a non-recurring signature (e.g. a filesystem master sector that
        exists exactly once), this checks only the declared offset and
        yields at most once. For a recurring signature (e.g. a per-chunk
        container header), the whole image is scanned starting from the
        declared minimum offset.
        """
        sig = self.profile.signature
        if not sig.recurring:
            if sig.matches_at(self.image, sig.offset):
                yield sig.offset
            return

        pattern = sig.pattern
        overlap = len(pattern) - 1
        pos = sig.offset
        # A signature can straddle a chunk boundary, so each search window
        # re-reads the last `overlap` bytes of the previous one. For the
        # short signatures (4-19 bytes) every profile in this project uses,
        # that overlap is negligible next to the chunk size.
        search_chunk = 4 * 1024 * 1024
        while pos < self.image.size:
            window_len = min(search_chunk + overlap, self.image.size - pos)
            window = self.image.read(pos, window_len)
            start = 0
            while True:
                idx = window.find(pattern, start)
                if idx == -1:
                    break
                candidate = pos + idx
                if sig.matches_at(self.image, candidate):
                    yield candidate
                start = idx + 1
            pos += search_chunk
