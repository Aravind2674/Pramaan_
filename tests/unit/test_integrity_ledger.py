"""Tests for pramaan.integrity.ledger."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pramaan.integrity.ledger import GENESIS_HASH, Ledger, LedgerEntry, LedgerError


def test_empty_ledger_head_is_genesis():
    ledger = Ledger()
    assert ledger.head_hash == GENESIS_HASH
    assert ledger.entries == ()


def test_first_entry_chains_from_genesis():
    ledger = Ledger()
    entry = ledger.append("examiner-1", "acquire", "disk-image-001")
    assert entry.index == 0
    assert entry.prev_hash == GENESIS_HASH
    assert entry.entry_hash == entry.recompute_hash()


def test_sequential_entries_chain_correctly():
    ledger = Ledger()
    e0 = ledger.append("examiner-1", "acquire", "disk-image-001")
    e1 = ledger.append("examiner-1", "hash", "disk-image-001", {"sha256": "abc"})
    e2 = ledger.append("examiner-2", "export", "case-report.pdf")

    assert e1.prev_hash == e0.entry_hash
    assert e2.prev_hash == e1.entry_hash
    assert [e.index for e in (e0, e1, e2)] == [0, 1, 2]


def test_detail_defaults_to_empty_dict():
    ledger = Ledger()
    entry = ledger.append("examiner-1", "note", "case-1")
    assert entry.detail == {}


def test_detail_is_defensively_copied_on_append():
    ledger = Ledger()
    original = {"note": "initial"}
    entry = ledger.append("examiner-1", "note", "case-1", original)
    original["note"] = "mutated after append"
    assert entry.detail == {"note": "initial"}


def test_non_json_serializable_detail_raises_ledger_error():
    ledger = Ledger()
    with pytest.raises(LedgerError):
        ledger.append("examiner-1", "note", "case-1", {"bad": object()})


def test_explicit_timestamp_is_respected():
    ledger = Ledger()
    entry = ledger.append("examiner-1", "acquire", "disk-1", timestamp="2026-01-01T00:00:00+00:00")
    assert entry.timestamp == "2026-01-01T00:00:00+00:00"


def test_verify_chain_on_empty_ledger_is_valid():
    result = Ledger().verify_chain()
    assert result.valid is True
    assert result.break_at_index is None


def test_verify_chain_on_untampered_ledger_is_valid():
    ledger = Ledger()
    for i in range(5):
        ledger.append("examiner-1", "action", f"target-{i}")
    result = ledger.verify_chain()
    assert result.valid is True


def test_verify_chain_detects_in_place_mutation_of_a_stored_entry():
    """A frozen dataclass blocks reassigning `entry.detail` itself, but not
    mutating the dict object that attribute points to -- confirming
    verify_chain catches this is what makes the ledger's guarantee actually
    tamper-EVIDENT rather than a false sense of immutability."""
    ledger = Ledger()
    ledger.append("examiner-1", "acquire", "disk-1", {"note": "original"})
    ledger.append("examiner-1", "hash", "disk-1")

    ledger.entries[0].detail["note"] = "tampered after the fact"

    result = ledger.verify_chain()
    assert result.valid is False
    assert result.break_at_index == 0
    assert "altered" in result.reason


def test_verify_chain_detects_a_wrong_entry_hash():
    ledger = Ledger()
    ledger.append("examiner-1", "acquire", "disk-1")
    doctored = replace(ledger._entries[0], entry_hash="0" * 64)
    ledger._entries[0] = doctored

    result = ledger.verify_chain()
    assert result.valid is False
    assert result.break_at_index == 0


def test_verify_chain_detects_a_broken_prev_hash_link():
    ledger = Ledger()
    ledger.append("examiner-1", "acquire", "disk-1")
    ledger.append("examiner-1", "hash", "disk-1")
    ledger.append("examiner-1", "export", "report.pdf")

    # Break the link between entry 1 and entry 2, leaving entry 1 itself
    # internally consistent -- the break must be reported at entry 2 (the
    # one whose prev_hash no longer matches), not entry 1.
    ledger._entries[2] = replace(ledger._entries[2], prev_hash="f" * 64)

    result = ledger.verify_chain()
    assert result.valid is False
    assert result.break_at_index == 2
    assert "prev_hash" in result.reason


def test_verify_chain_detects_a_reordered_entry_index():
    ledger = Ledger()
    ledger.append("examiner-1", "acquire", "disk-1")
    ledger.append("examiner-1", "hash", "disk-1")
    ledger._entries[1] = replace(ledger._entries[1], index=5)

    result = ledger.verify_chain()
    assert result.valid is False
    assert result.break_at_index == 1


def test_ledger_persists_to_file_and_reloads_identically(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append("examiner-1", "acquire", "disk-1", {"sha256": "abc123"})
    ledger.append("examiner-1", "export", "report.pdf")

    reloaded = Ledger(path)
    assert reloaded.entries == ledger.entries
    assert reloaded.head_hash == ledger.head_hash
    assert reloaded.verify_chain().valid is True


def test_load_skips_blank_lines(tmp_path):
    """A trailing newline (or a stray blank line from manual editing) is a
    normal thing to find in a text file and must not become a phantom
    entry or a crash."""
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append("examiner-1", "acquire", "disk-1")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n\n")  # simulate stray blank lines appended by an editor

    reloaded = Ledger(path)
    assert len(reloaded.entries) == 1
    assert reloaded.verify_chain().valid is True


def test_recompute_hash_reports_non_serializable_detail_via_ledger_error():
    """recompute_hash is also reachable on an entry built directly (e.g.
    while loading a file, or in a test), bypassing append()'s own
    validation -- it must fail the same clear way, not with a raw
    TypeError from deep inside json.dumps."""
    entry = LedgerEntry(
        index=0, timestamp="2026-01-01T00:00:00+00:00", actor="x", action="y",
        target="z", detail={"bad": object()}, prev_hash=GENESIS_HASH, entry_hash="",
    )
    with pytest.raises(LedgerError):
        entry.recompute_hash()


def test_appending_after_reload_continues_the_chain(tmp_path):
    path = tmp_path / "ledger.jsonl"
    first = Ledger(path)
    first.append("examiner-1", "acquire", "disk-1")

    second = Ledger(path)
    entry = second.append("examiner-1", "hash", "disk-1")
    assert entry.index == 1
    assert entry.prev_hash == first.head_hash
    assert second.verify_chain().valid is True

    # A third instance re-reading the file sees both entries, correctly
    # chained end to end.
    third = Ledger(path)
    assert len(third.entries) == 2
    assert third.verify_chain().valid is True


def test_ledger_entry_is_frozen_against_reassignment():
    ledger = Ledger()
    entry = ledger.append("examiner-1", "acquire", "disk-1")
    with pytest.raises(Exception):  # noqa: B017 -- FrozenInstanceError, a dataclasses internal
        entry.actor = "someone-else"


def test_ledger_entry_dataclass_type_is_exported():
    assert LedgerEntry.__dataclass_fields__.keys() == {
        "index", "timestamp", "actor", "action", "target",
        "detail", "prev_hash", "entry_hash",
    }
