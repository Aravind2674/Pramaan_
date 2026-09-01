"""
Ed25519 signing for an examiner's key: sign a ledger's head hash or an
export manifest, and verify that signature later.

Ed25519 over RSA/ECDSA-with-a-choice-of-curve for one practical reason: it
has no parameter choices to get wrong (no curve selection, no hash-function
pairing to reason about), so there is nothing here for a future change to
misconfigure. Keys are handled as opaque objects from ``cryptography``
throughout — nothing in this module reimplements or touches the actual
signature math.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair() -> Ed25519PrivateKey:
    """A fresh private key. Its public key is available via ``.public_key()``."""
    return Ed25519PrivateKey.generate()


def sign(private_key: Ed25519PrivateKey, data: bytes) -> bytes:
    """The raw 64-byte Ed25519 signature over ``data``."""
    return private_key.sign(data)


def verify(public_key: Ed25519PublicKey, data: bytes, signature: bytes) -> bool:
    """Whether ``signature`` is a valid Ed25519 signature over ``data``
    from ``public_key``.

    Never raises: ``cryptography``'s own ``verify()`` raises
    ``InvalidSignature`` on a bad signature, which this converts to a plain
    ``False`` — a caller checking a signature should get an answer, not
    have to wrap every check in its own try/except for the expected
    failure case.
    """
    try:
        public_key.verify(signature, data)
    except InvalidSignature:
        return False
    return True


def public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    """A stable, displayable identifier for a public key: the SHA-256 hex
    digest of its raw 32-byte encoding — short enough to put on a
    certificate, long enough that two examiners' keys won't collide."""
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


def save_private_key(
    private_key: Ed25519PrivateKey, path: str | Path, password: bytes | None = None
) -> None:
    """Write ``private_key`` as PEM (PKCS8), optionally encrypted.

    Always pass a password for a key that will ever leave the examiner's
    own workstation — an unencrypted private key file is a bearer token
    for every signature it can produce.
    """
    encryption: serialization.KeySerializationEncryption = (
        serialization.BestAvailableEncryption(password)
        if password is not None
        else serialization.NoEncryption()
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    Path(path).write_bytes(pem)


def load_private_key(path: str | Path, password: bytes | None = None) -> Ed25519PrivateKey:
    """Load a private key written by :func:`save_private_key`."""
    pem = Path(path).read_bytes()
    key = serialization.load_pem_private_key(pem, password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError(f"{path} does not contain an Ed25519 private key")
    return key


def save_public_key(public_key: Ed25519PublicKey, path: str | Path) -> None:
    """Write ``public_key`` as PEM (SubjectPublicKeyInfo) — the form
    intended to be shared, e.g. attached to a case for later signature
    verification by someone who never held the private key."""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    Path(path).write_bytes(pem)


def load_public_key(path: str | Path) -> Ed25519PublicKey:
    """Load a public key written by :func:`save_public_key`."""
    pem = Path(path).read_bytes()
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError(f"{path} does not contain an Ed25519 public key")
    return key
