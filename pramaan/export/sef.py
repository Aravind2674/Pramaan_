"""
Building and validating Surveillance Evidence Format (SEF) bundles.

A SEF bundle is a ZIP with a documented shape:

- ``manifest.json`` — case identity and, for every included artifact, its
  filename, size, and SHA-256, validated against ``sef_manifest.schema.json``.
- ``artifacts/`` — the files the manifest describes.
- ``ledger.jsonl`` (optional) — an excerpt of the case's audit ledger.
- ``manifest.json.sig`` + ``examiner_public_key.pem`` (optional) — an
  Ed25519 signature over the exact bytes of ``manifest.json``, and the
  public key to check it against.

The signature is deliberately never a field *inside* ``manifest.json``: a
signature covering "this JSON document, including its own signature field"
is circular, and every practical way to make that work (sign a redacted
copy, sign a canonicalised form that omits the field) still means the
bytes actually shipped in the bundle are not quite the bytes verified —
exactly the kind of gap a careless implementation could hide behind. Two
separate files avoids the problem outright: ``manifest.json`` never needs
to know it might be signed, and verification is "hash these exact bytes,
check that signature."
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from pramaan.integrity.ledger import LedgerEntry, verify_entries
from pramaan.integrity.signing import sign, verify

SEF_FORMAT_VERSION = "1.0"
MANIFEST_FILENAME = "manifest.json"
SIGNATURE_FILENAME = "manifest.json.sig"
PUBLIC_KEY_FILENAME = "examiner_public_key.pem"
LEDGER_FILENAME = "ledger.jsonl"

_SCHEMA_CACHE: dict[str, Any] | None = None


class SefError(Exception):
    """Raised for a SEF bundle construction error — a build-time problem
    this layer itself detected, not a filesystem or ZIP error, which is
    left to surface as-is."""


def _load_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        text = resources.files("pramaan.export").joinpath("sef_manifest.schema.json").read_text()
        _SCHEMA_CACHE = json.loads(text)
    return _SCHEMA_CACHE


@dataclass(frozen=True)
class ArtifactSpec:
    """One file to include in a SEF bundle, described by where it
    currently lives on disk — the bundle builder reads and hashes it from
    there; it is not copied or moved as a side effect of describing it."""

    artifact_id: str
    source_path: Path
    description: str = ""

    @property
    def bundle_filename(self) -> str:
        return f"artifacts/{self.artifact_id}_{self.source_path.name}"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def _ledger_jsonl(entries: Iterable[LedgerEntry]) -> str:
    lines = [json.dumps(asdict(e), sort_keys=True) for e in entries]
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_ledger_jsonl(data: bytes) -> list[LedgerEntry]:
    entries = []
    for line in data.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(LedgerEntry(**json.loads(line)))
    return entries


def build_sef_bundle(
    dest_path: str | Path,
    *,
    case_id: str,
    title: str,
    investigating_agency: str,
    examiner_name: str,
    artifacts: Iterable[ArtifactSpec] = (),
    ledger_entries: Iterable[LedgerEntry] = (),
    ledger_head_hash: str,
    signing_key: Ed25519PrivateKey | None = None,
    generated_at: str | None = None,
) -> Path:
    """Build a SEF bundle at ``dest_path``. Raises :class:`SefError` if
    ``dest_path`` already exists, or if any artifact's ``source_path``
    cannot be read — this fails before writing a single byte of the
    bundle, not partway through it.
    """
    dest_path = Path(dest_path)
    if dest_path.exists():
        raise SefError(f"{dest_path} already exists")

    artifacts = list(artifacts)
    for spec in artifacts:
        if not spec.source_path.is_file():
            raise SefError(f"artifact {spec.artifact_id!r}: {spec.source_path} is not a file")

    manifest_artifacts = []
    artifact_bytes: dict[str, bytes] = {}
    for spec in artifacts:
        data = spec.source_path.read_bytes()
        artifact_bytes[spec.bundle_filename] = data
        manifest_artifacts.append({
            "artifact_id": spec.artifact_id,
            "filename": spec.bundle_filename,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "description": spec.description,
        })

    ledger_entries = list(ledger_entries)
    ledger_text = _ledger_jsonl(ledger_entries)

    manifest: dict[str, Any] = {
        "sef_version": SEF_FORMAT_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "case": {
            "case_id": case_id,
            "title": title,
            "investigating_agency": investigating_agency,
            "examiner_name": examiner_name,
        },
        "artifacts": manifest_artifacts,
        "ledger_head_hash": ledger_head_hash,
    }
    if ledger_entries:
        manifest["ledger_filename"] = LEDGER_FILENAME

    try:
        jsonschema.validate(manifest, _load_schema())
    except jsonschema.ValidationError as exc:
        raise SefError(f"built manifest does not conform to the SEF schema: {exc.message}") from exc

    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_FILENAME, manifest_bytes)
        for filename, data in artifact_bytes.items():
            zf.writestr(filename, data)
        if ledger_entries:
            zf.writestr(LEDGER_FILENAME, ledger_text)
        if signing_key is not None:
            signature = sign(signing_key, manifest_bytes)
            zf.writestr(SIGNATURE_FILENAME, signature.hex())
            public_pem = signing_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            zf.writestr(PUBLIC_KEY_FILENAME, public_pem)

    return dest_path


def read_manifest(bundle_path: str | Path) -> dict[str, Any]:
    """The parsed ``manifest.json`` from a SEF bundle, without validating
    or checking anything else — for :func:`validate_sef_bundle`'s full
    check, or simple metadata inspection when that is all that's needed.
    """
    with zipfile.ZipFile(bundle_path, "r") as zf:
        try:
            raw = zf.read(MANIFEST_FILENAME)
        except KeyError as exc:
            raise SefError(f"{bundle_path} has no {MANIFEST_FILENAME}") from exc
    return dict(json.loads(raw))


def validate_sef_bundle(
    bundle_path: str | Path, *, trusted_public_key: Ed25519PublicKey | None = None
) -> ValidationResult:
    """Independently check a SEF bundle: the manifest conforms to the
    published schema, every declared artifact is present with the exact
    hash and size the manifest claims, any included ledger excerpt is a
    valid, self-consistent hash chain matching the manifest's declared
    head, and — if the bundle is signed — the signature verifies against
    the bundled public key.

    ``trusted_public_key``, if given, additionally requires the bundle to
    be signed *by that specific key* — confirming a signature verifies
    against whatever public key happens to be bundled alongside it proves
    the manifest hasn't been altered since signing; it says nothing about
    who that key belongs to. Binding a key to a named, trusted examiner is
    a real-world trust decision outside what this function can determine
    from the bundle alone.

    Every problem found is collected and returned rather than raised —
    a caller auditing a bundle wants the full list of what's wrong, not
    just the first thing that broke.
    """
    errors: list[str] = []
    bundle_path = Path(bundle_path)

    try:
        zf = zipfile.ZipFile(bundle_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as exc:
        return ValidationResult(False, (f"cannot open {bundle_path} as a ZIP: {exc}",))

    with zf:
        names = set(zf.namelist())
        if MANIFEST_FILENAME not in names:
            return ValidationResult(False, (f"missing {MANIFEST_FILENAME}",))

        manifest_bytes = zf.read(MANIFEST_FILENAME)
        try:
            manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as exc:
            return ValidationResult(False, (f"{MANIFEST_FILENAME} is not valid JSON: {exc}",))

        try:
            jsonschema.validate(manifest, _load_schema())
        except jsonschema.ValidationError as exc:
            return ValidationResult(
                False,
                (f"{MANIFEST_FILENAME} does not conform to the SEF schema: {exc.message}",),
            )

        for artifact in manifest["artifacts"]:
            filename = artifact["filename"]
            if filename not in names:
                errors.append(
                    f"artifact {artifact['artifact_id']!r} declares filename "
                    f"{filename!r}, not present in the bundle"
                )
                continue
            data = zf.read(filename)
            actual_hash = hashlib.sha256(data).hexdigest()
            if actual_hash != artifact["sha256"]:
                errors.append(
                    f"artifact {artifact['artifact_id']!r} hash mismatch: manifest "
                    f"declares {artifact['sha256']}, actual content hashes to {actual_hash}"
                )
            if len(data) != artifact["size_bytes"]:
                errors.append(
                    f"artifact {artifact['artifact_id']!r} size mismatch: manifest "
                    f"declares {artifact['size_bytes']}, actual size is {len(data)}"
                )

        ledger_filename = manifest.get("ledger_filename")
        if ledger_filename is not None:
            if ledger_filename not in names:
                errors.append(
                    f"manifest references ledger_filename {ledger_filename!r}, "
                    "not present in the bundle"
                )
            else:
                entries = _parse_ledger_jsonl(zf.read(ledger_filename))
                chain_result = verify_entries(entries)
                if not chain_result.valid:
                    errors.append(
                        f"included ledger excerpt fails its own chain verification "
                        f"at entry {chain_result.break_at_index}: {chain_result.reason}"
                    )
                else:
                    actual_head = entries[-1].entry_hash if entries else None
                    if actual_head != manifest["ledger_head_hash"]:
                        errors.append(
                            "manifest ledger_head_hash does not match the included "
                            f"ledger excerpt's actual head hash ({actual_head})"
                        )

        if SIGNATURE_FILENAME in names:
            if PUBLIC_KEY_FILENAME not in names:
                errors.append(f"{SIGNATURE_FILENAME} present but {PUBLIC_KEY_FILENAME} is missing")
            else:
                errors.extend(
                    _verify_bundle_signature(zf, manifest_bytes, trusted_public_key)
                )
        elif trusted_public_key is not None:
            errors.append("caller requires a trusted signature, but this bundle is not signed")

    return ValidationResult(len(errors) == 0, tuple(errors))


def _verify_bundle_signature(
    zf: zipfile.ZipFile, manifest_bytes: bytes, trusted_public_key: Ed25519PublicKey | None
) -> list[str]:
    errors: list[str] = []
    try:
        signature = bytes.fromhex(zf.read(SIGNATURE_FILENAME).decode("ascii").strip())
        bundled_key = serialization.load_pem_public_key(zf.read(PUBLIC_KEY_FILENAME))
    except (ValueError, TypeError) as exc:
        return [f"could not parse signature or public key: {exc}"]

    if not isinstance(bundled_key, Ed25519PublicKey):
        return [f"{PUBLIC_KEY_FILENAME} does not contain an Ed25519 public key"]

    if not verify(bundled_key, manifest_bytes, signature):
        errors.append(
            "manifest signature does not verify against the bundled public key "
            "-- the manifest may have been altered since it was signed"
        )
    elif trusted_public_key is not None:
        bundled_raw = bundled_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        trusted_raw = trusted_public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if bundled_raw != trusted_raw:
            errors.append("bundle is signed, but not by the expected trusted public key")
    return errors
