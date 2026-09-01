"""
A Merkle tree over a case's artifact hashes (RFC 6962 §2.1 construction).

Deliberately the RFC 6962 tree, not the "pair up leaves, duplicate the odd
one out" construction many hand-rolled Merkle trees use — that duplication
scheme has a known second-preimage weakness (a leaf can sometimes be
reinterpreted as an internal node). RFC 6962 avoids it two ways: leaves and
internal nodes are hashed with different domain-separation prefixes
(``0x00`` vs ``0x01``), and an odd-sized tree is split at the largest power
of two smaller than its size rather than padded — every function below is a
direct, checkable translation of the RFC's own recursive definitions, so a
reviewer can compare this code against the spec line by line.

What this buys the rest of the project: one root hash can represent "every
artifact in this case," and an inclusion proof lets a party demonstrate one
specific artifact was part of that set without disclosing every other one —
useful when a case's evidence set as a whole shouldn't be handed over just
to confirm one item's provenance.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator

_LEAF_PREFIX = b"\x00"
_NODE_PREFIX = b"\x01"


def _largest_power_of_two_below(n: int) -> int:
    """The largest k such that k is a power of two and k < n. Requires n > 1."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def leaf_hash(data: bytes) -> bytes:
    """RFC 6962's leaf hash: ``SHA-256(0x00 || data)``."""
    return hashlib.sha256(_LEAF_PREFIX + data).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    """RFC 6962's internal node hash: ``SHA-256(0x01 || left || right)``."""
    return hashlib.sha256(_NODE_PREFIX + left + right).digest()


def root_hash(leaves: Iterable[bytes]) -> bytes:
    """RFC 6962 ``MTH(D[n])`` — the Merkle Tree Hash of raw leaf data.

    Each element of ``leaves`` is the artifact's own raw content or a
    representation of it (e.g. a decoded SHA-256 digest); this function
    applies the RFC's leaf hashing internally, so callers never need to
    call :func:`leaf_hash` themselves except when working with
    :func:`verify_inclusion`.

    An empty list hashes to ``SHA-256("")``, matching ``MTH({})`` in the
    RFC — a defined, non-arbitrary answer for "the root of nothing."
    """
    items = list(leaves)
    n = len(items)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return leaf_hash(items[0])
    k = _largest_power_of_two_below(n)
    return _node_hash(root_hash(items[:k]), root_hash(items[k:]))


def audit_path(index: int, leaves: Iterable[bytes]) -> list[bytes]:
    """RFC 6962 ``PATH(m, D[n])`` — the sibling hashes needed to recompute
    :func:`root_hash` starting from ``leaf_hash(leaves[index])`` alone.

    Ordered from the leaf's immediate sibling up toward the root, which is
    the order :func:`verify_inclusion` consumes them in.
    """
    items = list(leaves)
    n = len(items)
    if not 0 <= index < n:
        raise ValueError(f"index {index} out of range for {n} leaves")
    if n == 1:
        return []
    k = _largest_power_of_two_below(n)
    if index < k:
        return audit_path(index, items[:k]) + [root_hash(items[k:])]
    return audit_path(index - k, items[k:]) + [root_hash(items[:k])]


def verify_inclusion(
    leaf_data: bytes, index: int, size: int, path: list[bytes], root: bytes
) -> bool:
    """Confirm ``leaf_data`` was included at ``index`` in a tree of ``size``
    leaves whose root is ``root``, given an :func:`audit_path`.

    Returns ``False`` for any malformed or fabricated proof — a wrong
    index, a truncated or padded path, a path that doesn't recompute to
    ``root`` — rather than raising. Presenting a bad proof against a real
    root is exactly the case this function exists to catch, so failing
    closed with a plain ``False`` is the correct outcome, not an exception
    a caller has to remember to handle.
    """
    if size <= 0 or not 0 <= index < size:
        return False

    path_iter: Iterator[bytes] = iter(path)

    def _recompute(idx: int, sz: int) -> bytes:
        if sz == 1:
            return leaf_hash(leaf_data)
        k = _largest_power_of_two_below(sz)
        if idx < k:
            # Matches construction's audit_path(idx, D[:k]) + [sibling]:
            # the recursive (deeper) part is consumed from path_iter
            # first, and only this level's own sibling comes after it.
            left = _recompute(idx, k)
            right = next(path_iter)
            return _node_hash(left, right)
        # Matches construction's audit_path(idx-k, D[k:]) + [sibling]:
        # same order — recurse (and drain the deeper path elements) before
        # touching this level's own sibling, not after.
        right = _recompute(idx - k, sz - k)
        left = next(path_iter)
        return _node_hash(left, right)

    try:
        computed = _recompute(index, size)
    except StopIteration:
        return False  # path too short for a tree of this size

    if next(path_iter, None) is not None:
        return False  # path too long — extra, unconsumed elements

    return computed == root
