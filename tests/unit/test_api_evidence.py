"""Tests for the evidence-item routes (pramaan.api.routes.evidence)."""

from __future__ import annotations


def _evidence_payload(**overrides):
    payload = {
        "description": "Dahua XVR hard disk image",
        "source_path": "/evidence/disk1.img",
        "sha256": "a" * 64,
        "size_bytes": 1_000_000,
        "device_type": "DVR",
        "make_model": "Dahua XVR5108HS",
    }
    payload.update(overrides)
    return payload


def test_add_evidence_item_returns_the_created_item(client, existing_case_id):
    response = client.post(f"/cases/{existing_case_id}/evidence", json=_evidence_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "Dahua XVR hard disk image"
    assert body["sha256"] == "a" * 64
    assert body["device_type"] == "DVR"
    assert body["id"] == 1


def test_add_evidence_item_with_write_block_attestation(client, existing_case_id):
    attestation = {"path": "/dev/sdb", "write_open_refused": True, "detail": "blocked"}
    response = client.post(
        f"/cases/{existing_case_id}/evidence",
        json=_evidence_payload(write_block_attestation=attestation),
    )
    assert response.status_code == 201
    assert response.json()["write_block_attestation"] == attestation


def test_add_evidence_item_to_nonexistent_case_returns_404(client):
    response = client.post("/cases/does-not-exist/evidence", json=_evidence_payload())
    assert response.status_code == 404


def test_list_evidence_items_reflects_added_items(client, existing_case_id):
    client.post(f"/cases/{existing_case_id}/evidence", json=_evidence_payload())
    client.post(f"/cases/{existing_case_id}/evidence", json=_evidence_payload(sha256="b" * 64))
    response = client.get(f"/cases/{existing_case_id}/evidence")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_evidence_item_by_id(client, existing_case_id):
    created = client.post(f"/cases/{existing_case_id}/evidence", json=_evidence_payload()).json()
    response = client.get(f"/cases/{existing_case_id}/evidence/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_nonexistent_evidence_item_returns_404(client, existing_case_id):
    response = client.get(f"/cases/{existing_case_id}/evidence/999")
    assert response.status_code == 404
