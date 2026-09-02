"""Tests for the report-generation routes (pramaan.api.routes.reports)."""

from __future__ import annotations

import io

from pypdf import PdfReader


def _device(**overrides):
    payload = {"device_type": "DVR", "make_and_model": "Dahua XVR5108HS"}
    payload.update(overrides)
    return payload


def _hash_decl(**overrides):
    payload = {"algorithm": "SHA256", "value": "a" * 64}
    payload.update(overrides)
    return payload


def _certificate_body(**overrides):
    body = {
        "part_a": {
            "custodian_name": "Inspector R. Kumar", "custodian_address": "Cyber Cell HQ",
            "device": _device(), "lawful_control_declared": True,
            "functioning_properly_declared": True, "hash": _hash_decl(),
            "place": "Chennai", "date": "2026-09-02", "time_ist": "14:00",
        },
        "part_b": {
            "expert_name": "Dr. A. Examiner", "expert_designation": "Digital Forensic Examiner",
            "device": _device(), "hash": _hash_decl(),
            "technical_statement": "Imaged read-only via a hardware write-blocker.",
            "place": "Chennai", "date": "2026-09-02", "time_ist": "15:00",
        },
    }
    body.update(overrides)
    return body


def test_generate_certificate_returns_a_real_pdf(client, existing_case_id):
    response = client.post(f"/cases/{existing_case_id}/reports/certificate", json=_certificate_body())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) == 2
    text = " ".join(page.extract_text() for page in reader.pages)
    assert existing_case_id in text
    assert "DVR" in text


def test_generate_certificate_with_invalid_device_type_returns_400(client, existing_case_id):
    body = _certificate_body()
    body["part_a"]["device"] = {"device_type": "Toaster", "make_and_model": "x"}
    response = client.post(f"/cases/{existing_case_id}/reports/certificate", json=body)
    assert response.status_code == 400


def test_generate_certificate_for_nonexistent_case_returns_404(client):
    response = client.post("/cases/does-not-exist/reports/certificate", json=_certificate_body())
    assert response.status_code == 404


def test_generate_case_report_returns_a_real_pdf(client, existing_case_id):
    response = client.post(f"/cases/{existing_case_id}/reports/case-report", json={})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(response.content))
    text = " ".join(page.extract_text() for page in reader.pages)
    assert existing_case_id in text
    assert "Skipped" in text


def test_generate_case_report_with_gap_analysis_window(client, existing_case_id):
    evidence_id = client.post(
        f"/cases/{existing_case_id}/evidence",
        json={"description": "x", "source_path": "/x", "sha256": "e" * 64, "size_bytes": 1},
    ).json()["id"]
    client.post(
        f"/cases/{existing_case_id}/clips",
        json={
            "evidence_item_id": evidence_id, "channel": 0, "kind": "recorded",
            "start_time": "2026-01-01T00:00:00+00:00", "end_time": "2026-01-01T01:00:00+00:00",
            "first_sequence": 1, "last_sequence": 10,
        },
    )
    response = client.post(
        f"/cases/{existing_case_id}/reports/case-report",
        json={
            "gap_analysis_window": {
                "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z",
            },
        },
    )
    assert response.status_code == 200
    reader = PdfReader(io.BytesIO(response.content))
    text = " ".join(page.extract_text() for page in reader.pages)
    assert "No anomalies were found" in text


def test_generate_case_report_with_invalid_gap_window_returns_400(client, existing_case_id):
    response = client.post(
        f"/cases/{existing_case_id}/reports/case-report",
        json={
            "gap_analysis_window": {
                "start": "2026-01-01T01:00:00Z", "end": "2026-01-01T00:00:00Z",
            },
        },
    )
    assert response.status_code == 400
