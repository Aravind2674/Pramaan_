"""Tests for the /cases routes (pramaan.api.routes.cases)."""

from __future__ import annotations


def test_create_case_returns_the_created_case_info(client):
    response = client.post(
        "/cases",
        json={
            "case_id": "c1", "title": "Sample", "investigating_agency": "Agency",
            "examiner_name": "Examiner",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["case_id"] == "c1"
    assert body["title"] == "Sample"
    assert body["investigating_agency"] == "Agency"
    assert body["examiner_name"] == "Examiner"
    assert "created_at" in body


def test_create_case_with_duplicate_id_returns_409(client):
    payload = {"case_id": "dup", "title": "T", "investigating_agency": "A", "examiner_name": "E"}
    client.post("/cases", json=payload)
    response = client.post("/cases", json=payload)
    assert response.status_code == 409


def test_create_case_with_invalid_id_returns_422(client):
    """An empty case_id fails Pydantic's own min_length before ever
    reaching the workspace -- a request-shape error, not a conflict."""
    response = client.post(
        "/cases", json={"case_id": "", "title": "T", "investigating_agency": "A", "examiner_name": "E"},
    )
    assert response.status_code == 422


def test_get_nonexistent_case_returns_404(client):
    response = client.get("/cases/does-not-exist")
    assert response.status_code == 404


def test_list_cases_reflects_created_cases(client):
    client.post("/cases", json={"case_id": "b", "title": "T", "investigating_agency": "A", "examiner_name": "E"})
    client.post("/cases", json={"case_id": "a", "title": "T", "investigating_agency": "A", "examiner_name": "E"})
    response = client.get("/cases")
    assert response.status_code == 200
    assert response.json() == ["a", "b"]


def test_get_case_info_for_an_existing_case(client, existing_case_id):
    response = client.get(f"/cases/{existing_case_id}")
    assert response.status_code == 200
    assert response.json()["case_id"] == existing_case_id
