"""Tests for the clip routes (pramaan.api.routes.clips)."""

from __future__ import annotations


def _add_evidence(client, case_id) -> int:
    response = client.post(
        f"/cases/{case_id}/evidence",
        json={"description": "x", "source_path": "/x", "sha256": "c" * 64, "size_bytes": 10},
    )
    return response.json()["id"]


def test_add_clip_returns_the_created_clip(client, existing_case_id):
    evidence_id = _add_evidence(client, existing_case_id)
    response = client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": evidence_id, "channel": 0, "kind": "recorded"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["evidence_item_id"] == evidence_id
    assert body["channel"] == 0
    assert body["kind"] == "recorded"


def test_add_clip_with_invalid_kind_returns_400(client, existing_case_id):
    evidence_id = _add_evidence(client, existing_case_id)
    response = client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": evidence_id, "channel": 0, "kind": "not-a-real-kind"},
    )
    assert response.status_code == 400


def test_add_clip_for_nonexistent_evidence_item_returns_400(client, existing_case_id):
    response = client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": 999, "channel": 0, "kind": "recorded"},
    )
    assert response.status_code == 400


def test_list_clips_filters_by_channel(client, existing_case_id):
    evidence_id = _add_evidence(client, existing_case_id)
    client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": evidence_id, "channel": 0, "kind": "recorded"},
    )
    client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": evidence_id, "channel": 1, "kind": "recorded"},
    )
    response = client.get(f"/cases/{existing_case_id}/clips", params={"channel": 1})
    assert response.status_code == 200
    clips = response.json()
    assert len(clips) == 1
    assert clips[0]["channel"] == 1


def test_set_clip_time_range_updates_the_clip(client, existing_case_id):
    evidence_id = _add_evidence(client, existing_case_id)
    clip = client.post(
        f"/cases/{existing_case_id}/clips",
        json={"evidence_item_id": evidence_id, "channel": 0, "kind": "recovered"},
    ).json()
    response = client.patch(
        f"/cases/{existing_case_id}/clips/{clip['id']}/time-range",
        json={"start_time": "2026-01-01T00:00:00+00:00", "end_time": "2026-01-01T01:00:00+00:00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["start_time"] == "2026-01-01T00:00:00+00:00"
    assert body["end_time"] == "2026-01-01T01:00:00+00:00"


def test_set_time_range_for_nonexistent_clip_returns_404(client, existing_case_id):
    response = client.patch(
        f"/cases/{existing_case_id}/clips/999/time-range",
        json={"start_time": "2026-01-01T00:00:00+00:00", "end_time": "2026-01-01T01:00:00+00:00"},
    )
    assert response.status_code == 404
