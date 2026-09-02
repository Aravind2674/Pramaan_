"""Tests for the findings routes (pramaan.api.routes.findings)."""

from __future__ import annotations


def test_add_finding_returns_the_created_finding(client, existing_case_id):
    response = client.post(
        f"/cases/{existing_case_id}/findings",
        json={"author": "Examiner", "category": "tamper_indicator", "description": "Something odd."},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["author"] == "Examiner"
    assert body["category"] == "tamper_indicator"
    assert body["clip_id"] is None


def test_add_finding_referencing_a_nonexistent_clip_returns_400(client, existing_case_id):
    response = client.post(
        f"/cases/{existing_case_id}/findings",
        json={"author": "Examiner", "category": "note", "description": "d", "clip_id": 999},
    )
    assert response.status_code == 400


def test_list_findings_reflects_added_findings(client, existing_case_id):
    client.post(
        f"/cases/{existing_case_id}/findings",
        json={"author": "Examiner", "category": "note", "description": "first"},
    )
    client.post(
        f"/cases/{existing_case_id}/findings",
        json={"author": "Examiner", "category": "note", "description": "second"},
    )
    response = client.get(f"/cases/{existing_case_id}/findings")
    assert response.status_code == 200
    assert len(response.json()) == 2
