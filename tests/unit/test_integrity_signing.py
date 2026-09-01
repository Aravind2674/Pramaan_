"""Tests for pramaan.integrity.signing."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pramaan.integrity.signing import (
    generate_keypair,
    load_private_key,
    load_public_key,
    public_key_fingerprint,
    save_private_key,
    save_public_key,
    sign,
    verify,
)


def test_sign_and_verify_round_trip():
    key = generate_keypair()
    data = b"case-report-hash:deadbeef"
    signature = sign(key, data)
    assert verify(key.public_key(), data, signature) is True


def test_verify_rejects_tampered_data():
    key = generate_keypair()
    signature = sign(key, b"original data")
    assert verify(key.public_key(), b"tampered data", signature) is False


def test_verify_rejects_signature_from_a_different_key():
    key_a = generate_keypair()
    key_b = generate_keypair()
    data = b"case-report-hash:deadbeef"
    signature = sign(key_a, data)
    assert verify(key_b.public_key(), data, signature) is False


def test_verify_rejects_garbage_signature_bytes_without_raising():
    key = generate_keypair()
    assert verify(key.public_key(), b"some data", b"not a real signature") is False
    assert verify(key.public_key(), b"some data", b"") is False


def test_generated_keys_are_ed25519():
    key = generate_keypair()
    assert isinstance(key, Ed25519PrivateKey)


def test_private_key_round_trips_through_disk_unencrypted(tmp_path):
    key = generate_keypair()
    path = tmp_path / "examiner.pem"
    save_private_key(key, path)

    reloaded = load_private_key(path)
    data = b"integrity check"
    assert verify(reloaded.public_key(), data, sign(key, data)) is True


def test_private_key_round_trips_through_disk_encrypted(tmp_path):
    key = generate_keypair()
    path = tmp_path / "examiner.pem"
    save_private_key(key, path, password=b"correct horse battery staple")

    reloaded = load_private_key(path, password=b"correct horse battery staple")
    data = b"integrity check"
    assert verify(reloaded.public_key(), data, sign(key, data)) is True


def test_loading_encrypted_key_with_wrong_password_fails(tmp_path):
    key = generate_keypair()
    path = tmp_path / "examiner.pem"
    save_private_key(key, path, password=b"the-real-password")

    with pytest.raises(Exception):  # noqa: B017 -- cryptography's own decrypt-failure type
        load_private_key(path, password=b"a-wrong-password")


def test_public_key_round_trips_through_disk(tmp_path):
    key = generate_keypair()
    path = tmp_path / "examiner.pub.pem"
    save_public_key(key.public_key(), path)

    reloaded = load_public_key(path)
    data = b"integrity check"
    assert verify(reloaded, data, sign(key, data)) is True


def test_load_private_key_rejects_a_non_ed25519_key_type(tmp_path):
    """A well-formed PEM private key of the wrong algorithm parses without
    error at the cryptography layer -- rejecting it is entirely this
    module's own responsibility, not something the library does for us."""
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    path = tmp_path / "rsa-key.pem"
    path.write_bytes(pem)

    with pytest.raises(TypeError, match="Ed25519"):
        load_private_key(path)


def test_load_public_key_rejects_a_non_ed25519_key_type(tmp_path):
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = tmp_path / "rsa-key.pub.pem"
    path.write_bytes(pem)

    with pytest.raises(TypeError, match="Ed25519"):
        load_public_key(path)


def test_load_private_key_rejects_a_file_holding_a_public_key(tmp_path):
    key = generate_keypair()
    path = tmp_path / "not-a-private-key.pem"
    save_public_key(key.public_key(), path)

    with pytest.raises(Exception):  # noqa: B017 -- cryptography rejects the PEM header itself
        load_private_key(path)


def test_load_public_key_rejects_a_file_holding_a_private_key(tmp_path):
    key = generate_keypair()
    path = tmp_path / "not-a-public-key.pem"
    save_private_key(key, path)

    with pytest.raises(Exception):  # noqa: B017 -- cryptography rejects the PEM header itself
        load_public_key(path)


def test_fingerprint_is_deterministic():
    key = generate_keypair()
    pub = key.public_key()
    assert public_key_fingerprint(pub) == public_key_fingerprint(pub)


def test_fingerprint_differs_between_keys():
    key_a = generate_keypair()
    key_b = generate_keypair()
    assert public_key_fingerprint(key_a.public_key()) != public_key_fingerprint(key_b.public_key())


def test_fingerprint_is_a_sha256_hex_string():
    key = generate_keypair()
    fp = public_key_fingerprint(key.public_key())
    assert len(fp) == 64
    int(fp, 16)  # raises ValueError if not valid hex
