"""Tests for pramaan.integrity.merkle."""

from __future__ import annotations

import hashlib

import pytest

from pramaan.integrity.merkle import audit_path, leaf_hash, root_hash, verify_inclusion


def _manual_node_hash(left: bytes, right: bytes) -> bytes:
    """Recomputed independently of pramaan.integrity.merkle's own (private)
    node-hash helper, so this test can't just be checking the code against
    itself."""
    return hashlib.sha256(b"\x01" + left + right).digest()


def test_root_hash_of_empty_list_is_sha256_of_empty_string():
    assert root_hash([]) == hashlib.sha256(b"").digest()


def test_root_hash_of_single_leaf_is_its_leaf_hash():
    data = b"artifact-one"
    assert root_hash([data]) == leaf_hash(data)


def test_root_hash_of_two_leaves_matches_manual_rfc6962_computation():
    a, b = b"leaf-a", b"leaf-b"
    expected = _manual_node_hash(leaf_hash(a), leaf_hash(b))
    assert root_hash([a, b]) == expected


def test_root_hash_of_five_leaves_matches_manual_rfc6962_computation():
    """5 leaves forces the largest-power-of-two-below split (k=4) rather
    than an even pairing -- this is the case a naive pairwise tree gets
    wrong."""
    leaves = [f"leaf-{i}".encode() for i in range(5)]
    left = root_hash(leaves[:4])
    right = root_hash(leaves[4:])
    expected = _manual_node_hash(left, right)
    assert root_hash(leaves) == expected


def test_root_hash_is_sensitive_to_leaf_order():
    a, b, c = b"a", b"b", b"c"
    assert root_hash([a, b, c]) != root_hash([c, b, a])


def test_root_hash_is_sensitive_to_leaf_content():
    assert root_hash([b"x"]) != root_hash([b"y"])


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 9, 16, 17])
def test_inclusion_proof_round_trips_for_every_index(n):
    leaves = [f"artifact-{i}".encode() for i in range(n)]
    root = root_hash(leaves)
    for index in range(n):
        path = audit_path(index, leaves)
        assert verify_inclusion(leaves[index], index, n, path, root) is True


def test_inclusion_proof_round_trips_exhaustively_up_to_64_leaves():
    """The parametrized test above caught a real ordering bug in
    verify_inclusion that several smaller hand-picked sizes missed --
    the bug only manifested when the 'far' branch of the split needed to
    recurse more than one level deep. Covering every size from 1 to 64,
    every index in each, is the actual property this module promises and
    is cheap enough to just check exhaustively rather than sample it."""
    for n in range(1, 65):
        leaves = [i.to_bytes(4, "big") for i in range(n)]
        root = root_hash(leaves)
        for index in range(n):
            path = audit_path(index, leaves)
            assert verify_inclusion(leaves[index], index, n, path, root) is True, (
                f"failed at n={n}, index={index}"
            )


def test_audit_path_out_of_range_index_raises():
    leaves = [b"a", b"b", b"c"]
    with pytest.raises(ValueError):
        audit_path(3, leaves)
    with pytest.raises(ValueError):
        audit_path(-1, leaves)


def test_verify_inclusion_rejects_wrong_leaf_data():
    leaves = [f"leaf-{i}".encode() for i in range(6)]
    root = root_hash(leaves)
    path = audit_path(2, leaves)
    assert verify_inclusion(b"not-the-real-leaf", 2, 6, path, root) is False


def test_verify_inclusion_rejects_wrong_root():
    leaves = [f"leaf-{i}".encode() for i in range(6)]
    path = audit_path(2, leaves)
    wrong_root = hashlib.sha256(b"decoy").digest()
    assert verify_inclusion(leaves[2], 2, 6, path, wrong_root) is False


def test_verify_inclusion_rejects_truncated_path():
    leaves = [f"leaf-{i}".encode() for i in range(9)]
    root = root_hash(leaves)
    path = audit_path(5, leaves)
    assert len(path) > 0
    assert verify_inclusion(leaves[5], 5, 9, path[:-1], root) is False


def test_verify_inclusion_rejects_padded_path():
    leaves = [f"leaf-{i}".encode() for i in range(9)]
    root = root_hash(leaves)
    path = audit_path(5, leaves)
    padded = [*path, hashlib.sha256(b"extra").digest()]
    assert verify_inclusion(leaves[5], 5, 9, padded, root) is False


def test_verify_inclusion_rejects_out_of_range_index():
    leaves = [b"a", b"b", b"c"]
    root = root_hash(leaves)
    assert verify_inclusion(b"a", 3, 3, [], root) is False
    assert verify_inclusion(b"a", -1, 3, [], root) is False


def test_verify_inclusion_rejects_non_positive_size():
    assert verify_inclusion(b"a", 0, 0, [], hashlib.sha256(b"").digest()) is False
