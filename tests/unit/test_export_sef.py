"""Tests for pramaan.export.sef."""

from __future__ import annotations

import hashlib
import json
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization

from pramaan.export.sef import (
    LEDGER_FILENAME,
    MANIFEST_FILENAME,
    PUBLIC_KEY_FILENAME,
    SIGNATURE_FILENAME,
    ArtifactSpec,
    SefError,
    build_sef_bundle,
    read_manifest,
    validate_sef_bundle,
)
from pramaan.integrity.ledger import GENESIS_HASH, Ledger
from pramaan.integrity.signing import generate_keypair

CASE_KWARGS = {
    "case_id": "SIH26150-001",
    "title": "Test case",
    "investigating_agency": "NTRO",
    "examiner_name": "A. Examiner",
}


def _artifact(tmp_path, name: str, content: bytes, artifact_id: str = "clip-1") -> ArtifactSpec:
    path = tmp_path / name
    path.write_bytes(content)
    return ArtifactSpec(artifact_id=artifact_id, source_path=path, description="a test artifact")


def _ledger_with_entries(n: int) -> Ledger:
    ledger = Ledger()
    for i in range(n):
        ledger.append("examiner-1", "acquire", f"target-{i}")
    return ledger


# ---------------------------------------------------------------------------
# build_sef_bundle
# ---------------------------------------------------------------------------

def test_build_minimal_bundle_with_no_artifacts_or_ledger(tmp_path):
    dest = tmp_path / "case.sef.zip"
    build_sef_bundle(dest, **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    assert dest.exists()
    with zipfile.ZipFile(dest) as zf:
        assert MANIFEST_FILENAME in zf.namelist()
        assert LEDGER_FILENAME not in zf.namelist()


def test_build_raises_if_destination_already_exists(tmp_path):
    dest = tmp_path / "case.sef.zip"
    dest.write_bytes(b"already here")
    with pytest.raises(SefError):
        build_sef_bundle(dest, **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)


def test_build_raises_if_an_artifact_source_is_missing(tmp_path):
    missing = ArtifactSpec(artifact_id="x", source_path=tmp_path / "does-not-exist.mp4")
    with pytest.raises(SefError):
        build_sef_bundle(
            tmp_path / "case.sef.zip", **CASE_KWARGS, artifacts=[missing], ledger_head_hash=GENESIS_HASH,
        )


def test_build_raises_if_required_case_field_fails_schema_validation(tmp_path):
    """An empty case_id passes Python's own type check (it's still a str)
    but fails the schema's minLength constraint -- confirming the schema
    validation step in build_sef_bundle is a real check, not a formality
    that can never actually fire given how the function is normally called."""
    bad_kwargs = dict(CASE_KWARGS)
    bad_kwargs["case_id"] = ""
    with pytest.raises(SefError, match="SEF schema"):
        build_sef_bundle(tmp_path / "case.sef.zip", **bad_kwargs, ledger_head_hash=GENESIS_HASH)


def test_manifest_records_correct_hash_and_size_for_each_artifact(tmp_path):
    content = b"fake mp4 bytes " * 100
    spec = _artifact(tmp_path, "clip.mp4", content)
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, artifacts=[spec], ledger_head_hash=GENESIS_HASH,
    )
    manifest = read_manifest(dest)
    assert len(manifest["artifacts"]) == 1
    entry = manifest["artifacts"][0]
    assert entry["artifact_id"] == "clip-1"
    assert entry["size_bytes"] == len(content)
    assert entry["sha256"] == hashlib.sha256(content).hexdigest()


def test_manifest_includes_case_info(tmp_path):
    dest = build_sef_bundle(tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    manifest = read_manifest(dest)
    assert manifest["case"]["case_id"] == "SIH26150-001"
    assert manifest["case"]["examiner_name"] == "A. Examiner"
    assert manifest["sef_version"] == "1.0"


def test_bundle_with_ledger_entries_includes_ledger_file(tmp_path):
    ledger = _ledger_with_entries(3)
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS,
        ledger_entries=ledger.entries, ledger_head_hash=ledger.head_hash,
    )
    manifest = read_manifest(dest)
    assert manifest["ledger_filename"] == LEDGER_FILENAME
    assert manifest["ledger_head_hash"] == ledger.head_hash
    with zipfile.ZipFile(dest) as zf:
        lines = zf.read(LEDGER_FILENAME).decode("utf-8").strip().splitlines()
        assert len(lines) == 3


def test_read_manifest_on_a_bundle_missing_manifest_raises(tmp_path):
    bogus = tmp_path / "not-a-sef-bundle.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("something_else.txt", "hello")
    with pytest.raises(SefError):
        read_manifest(bogus)


def test_signed_bundle_includes_signature_and_public_key(tmp_path):
    key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=key,
    )
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert SIGNATURE_FILENAME in names
        assert PUBLIC_KEY_FILENAME in names


def test_unsigned_bundle_has_no_signature_files(tmp_path):
    dest = build_sef_bundle(tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert SIGNATURE_FILENAME not in names
        assert PUBLIC_KEY_FILENAME not in names


# ---------------------------------------------------------------------------
# validate_sef_bundle -- the happy paths
# ---------------------------------------------------------------------------

def test_validate_a_freshly_built_minimal_bundle_is_valid(tmp_path):
    dest = build_sef_bundle(tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    result = validate_sef_bundle(dest)
    assert result.valid is True
    assert result.errors == ()


def test_validate_a_bundle_with_artifacts_and_ledger_is_valid(tmp_path):
    spec = _artifact(tmp_path, "clip.mp4", b"real-looking video bytes")
    ledger = _ledger_with_entries(2)
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, artifacts=[spec],
        ledger_entries=ledger.entries, ledger_head_hash=ledger.head_hash,
    )
    result = validate_sef_bundle(dest)
    assert result.valid is True


def test_validate_a_signed_bundle_with_correct_signature_is_valid(tmp_path):
    key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=key,
    )
    result = validate_sef_bundle(dest)
    assert result.valid is True


def test_validate_accepts_a_signature_from_the_expected_trusted_key(tmp_path):
    key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=key,
    )
    result = validate_sef_bundle(dest, trusted_public_key=key.public_key())
    assert result.valid is True


# ---------------------------------------------------------------------------
# validate_sef_bundle -- tamper and corruption detection
# ---------------------------------------------------------------------------

def _rewrite_zip_entry(path, name: str, new_content: bytes) -> None:
    """Replace one entry's content in an existing ZIP -- simulating a
    bundle that was tampered with after being built, not one that was
    simply constructed wrong."""
    with zipfile.ZipFile(path) as zf:
        entries = {n: zf.read(n) for n in zf.namelist()}
    entries[name] = new_content
    path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, data in entries.items():
            zf.writestr(n, data)


def test_validate_rejects_a_file_that_is_not_a_zip(tmp_path):
    bogus = tmp_path / "not_a_zip.sef.zip"
    bogus.write_bytes(b"this is not a zip file at all")
    result = validate_sef_bundle(bogus)
    assert result.valid is False
    assert any("ZIP" in e for e in result.errors)


def test_validate_rejects_a_zip_with_no_manifest(tmp_path):
    bogus = tmp_path / "no_manifest.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("something.txt", "hello")
    result = validate_sef_bundle(bogus)
    assert result.valid is False
    assert any("missing" in e for e in result.errors)


def test_validate_rejects_invalid_json_manifest(tmp_path):
    bogus = tmp_path / "bad_json.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr(MANIFEST_FILENAME, "{not valid json")
    result = validate_sef_bundle(bogus)
    assert result.valid is False
    assert any("not valid JSON" in e for e in result.errors)


def test_validate_rejects_a_manifest_that_fails_the_schema(tmp_path):
    bogus = tmp_path / "bad_schema.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr(MANIFEST_FILENAME, '{"sef_version": "1.0"}')  # missing required fields
    result = validate_sef_bundle(bogus)
    assert result.valid is False
    assert any("SEF schema" in e for e in result.errors)


def test_validate_detects_a_tampered_artifact(tmp_path):
    spec = _artifact(tmp_path, "clip.mp4", b"original bytes")
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, artifacts=[spec], ledger_head_hash=GENESIS_HASH,
    )
    _rewrite_zip_entry(dest, spec.bundle_filename, b"TAMPERED bytes, different length!!")

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("hash mismatch" in e for e in result.errors)
    assert any("size mismatch" in e for e in result.errors)


def test_validate_detects_a_missing_declared_artifact(tmp_path):
    spec = _artifact(tmp_path, "clip.mp4", b"original bytes")
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, artifacts=[spec], ledger_head_hash=GENESIS_HASH,
    )
    with zipfile.ZipFile(dest) as zf:
        entries = {n: zf.read(n) for n in zf.namelist() if n != spec.bundle_filename}
    dest.unlink()
    with zipfile.ZipFile(dest, "w") as zf:
        for n, data in entries.items():
            zf.writestr(n, data)

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("not present in the bundle" in e for e in result.errors)


def test_validate_detects_a_tampered_manifest_after_signing(tmp_path):
    key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=key,
    )
    with zipfile.ZipFile(dest) as zf:
        manifest_text = zf.read(MANIFEST_FILENAME).decode("utf-8")
    tampered = manifest_text.replace("A. Examiner", "Someone Else")
    assert tampered != manifest_text
    _rewrite_zip_entry(dest, MANIFEST_FILENAME, tampered.encode("utf-8"))

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("does not verify" in e for e in result.errors)


def test_validate_detects_signature_from_an_unexpected_key(tmp_path):
    signer_key = generate_keypair()
    other_key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=signer_key,
    )
    result = validate_sef_bundle(dest, trusted_public_key=other_key.public_key())
    assert result.valid is False
    assert any("not by the expected trusted public key" in e for e in result.errors)


def test_validate_requires_signature_when_caller_demands_a_trusted_key(tmp_path):
    dest = build_sef_bundle(tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    key = generate_keypair()
    result = validate_sef_bundle(dest, trusted_public_key=key.public_key())
    assert result.valid is False
    assert any("not signed" in e for e in result.errors)


def test_validate_detects_signature_file_without_matching_public_key(tmp_path):
    dest = build_sef_bundle(tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    with zipfile.ZipFile(dest) as zf:
        entries = {n: zf.read(n) for n in zf.namelist()}
    entries[SIGNATURE_FILENAME] = b"deadbeef" * 8
    dest.unlink()
    with zipfile.ZipFile(dest, "w") as zf:
        for n, data in entries.items():
            zf.writestr(n, data)

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any(PUBLIC_KEY_FILENAME in e for e in result.errors)


def test_validate_detects_a_tampered_ledger_excerpt(tmp_path):
    ledger = _ledger_with_entries(3)
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS,
        ledger_entries=ledger.entries, ledger_head_hash=ledger.head_hash,
    )
    with zipfile.ZipFile(dest) as zf:
        lines = zf.read(LEDGER_FILENAME).decode("utf-8").strip().splitlines()

    doctored = json.loads(lines[1])
    doctored["prev_hash"] = "f" * 64
    lines[1] = json.dumps(doctored, sort_keys=True)
    _rewrite_zip_entry(dest, LEDGER_FILENAME, ("\n".join(lines) + "\n").encode("utf-8"))

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("chain verification" in e for e in result.errors)


def test_validate_detects_malformed_signature_hex(tmp_path):
    key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=key,
    )
    _rewrite_zip_entry(dest, SIGNATURE_FILENAME, b"this is not valid hexadecimal!!")

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("could not parse" in e for e in result.errors)


def test_validate_detects_non_ed25519_public_key(tmp_path):
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = generate_keypair()
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH, signing_key=key,
    )
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_pem = rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _rewrite_zip_entry(dest, PUBLIC_KEY_FILENAME, rsa_pem)

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("does not contain an Ed25519 public key" in e for e in result.errors)


def test_validate_detects_ledger_head_hash_mismatch(tmp_path):
    ledger = _ledger_with_entries(2)
    dest = build_sef_bundle(
        tmp_path / "case.sef.zip", **CASE_KWARGS,
        ledger_entries=ledger.entries, ledger_head_hash="a" * 64,  # deliberately wrong
    )
    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("does not match" in e for e in result.errors)


def test_validate_detects_ledger_filename_reference_to_missing_file(tmp_path):
    dest = build_sef_bundle(tmp_path / "case.sef.zip", **CASE_KWARGS, ledger_head_hash=GENESIS_HASH)
    with zipfile.ZipFile(dest) as zf:
        manifest = json.loads(zf.read(MANIFEST_FILENAME))
    manifest["ledger_filename"] = LEDGER_FILENAME  # reference a file that was never included
    _rewrite_zip_entry(dest, MANIFEST_FILENAME, json.dumps(manifest, sort_keys=True).encode("utf-8"))

    result = validate_sef_bundle(dest)
    assert result.valid is False
    assert any("not present in the bundle" in e for e in result.errors)
