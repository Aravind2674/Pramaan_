"""Tests for the timeline and integrity routes."""

from __future__ import annotations


def _add_evidence(client, case_id) -> int:
    response = client.post(
        f"/cases/{case_id}/evidence",
        json={"description": "x", "source_path": "/x", "sha256": "d" * 64, "size_bytes": 10},
    )
    return response.json()["id"]


def test_timeline_is_empty_for_a_case_with_no_timed_clips(client, existing_case_id):
    response = client.get(f"/cases/{existing_case_id}/timeline")
    assert response.status_code == 200
    assert response.json() == {"segments": []}


def test_timeline_reflects_a_clip_with_a_known_time_range(client, existing_case_id):
    evidence_id = _add_evidence(client, existing_case_id)
    client.post(
        f"/cases/{existing_case_id}/clips",
        json={
            "evidence_item_id": evidence_id, "channel": 0, "kind": "recorded",
            "start_time": "2026-01-01T00:00:00+00:00", "end_time": "2026-01-01T01:00:00+00:00",
        },
    )
    response = client.get(f"/cases/{existing_case_id}/timeline")
    assert response.status_code == 200
    segments = response.json()["segments"]
    assert len(segments) == 1
    assert segments[0]["channel"] == 0
    assert segments[0]["kind"] == "recorded"


def test_timeline_excludes_a_clip_with_no_known_time_range(client, existing_case_id):
    evidence_id = _add_evidence(client, existing_case_id)
    client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": evidence_id, "channel": 0, "kind": "corrupt"},
    )
    response = client.get(f"/cases/{existing_case_id}/timeline")
    assert response.json() == {"segments": []}


def test_integrity_is_valid_for_a_freshly_created_case(client, existing_case_id):
    response = client.get(f"/cases/{existing_case_id}/integrity")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["break_at_index"] is None
    assert body["reason"] is None


def test_integrity_reflects_a_tampered_ledger(client, existing_case_id, tmp_path):
    """Corrupt the case's own ledger file on disk between requests --
    the API must surface a broken chain, not just an initially-healthy
    snapshot."""
    import json

    ledger_path = tmp_path / "workspace" / f"{existing_case_id}.case.ledger.jsonl"
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert lines
    tampered = json.loads(lines[0])
    tampered["detail"] = {"tampered": True}
    lines[0] = json.dumps(tampered)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    response = client.get(f"/cases/{existing_case_id}/integrity")
    assert response.status_code == 200
    assert response.json()["valid"] is False
