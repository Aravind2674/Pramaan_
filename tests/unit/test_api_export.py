"""Tests for the export route (pramaan.api.routes.export)."""

from __future__ import annotations

import io
import zipfile


def test_export_with_no_artifacts_returns_a_valid_zip(client, existing_case_id):
    response = client.post(f"/cases/{existing_case_id}/export", json={"artifacts": []})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "manifest.json" in zf.namelist()


def test_export_includes_a_real_artifact_file(client, existing_case_id, tmp_path):
    artifact_path = tmp_path / "artifact.bin"
    artifact_path.write_bytes(b"evidence bytes")
    response = client.post(
        f"/cases/{existing_case_id}/export",
        json={"artifacts": [{"artifact_id": "img1", "source_path": str(artifact_path), "description": "disk image"}]},
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        matches = [n for n in zf.namelist() if n.startswith("artifacts/img1_")]
        assert matches
        assert zf.read(matches[0]) == b"evidence bytes"


def test_export_with_a_missing_artifact_file_returns_400(client, existing_case_id):
    response = client.post(
        f"/cases/{existing_case_id}/export",
        json={"artifacts": [{"artifact_id": "img1", "source_path": "/does/not/exist.img"}]},
    )
    assert response.status_code == 400


def test_export_without_ledger_omits_the_ledger_file(client, existing_case_id):
    response = client.post(f"/cases/{existing_case_id}/export", json={"include_ledger": False})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "ledger.jsonl" not in zf.namelist()


def test_export_for_nonexistent_case_returns_404(client):
    response = client.post("/cases/does-not-exist/export", json={})
    assert response.status_code == 404
