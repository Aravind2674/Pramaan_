"""Tests for pramaan.api.app.create_app itself."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pramaan.api.app import create_app
from pramaan.api.workspace import CaseWorkspace


def test_create_app_builds_a_workspace_at_the_given_root(tmp_path):
    root = tmp_path / "ws"
    app = create_app(root)
    assert isinstance(app.state.workspace, CaseWorkspace)
    assert app.state.workspace.root == root
    assert root.is_dir()


def test_two_apps_have_independent_workspaces(tmp_path):
    app1 = create_app(tmp_path / "ws1")
    app2 = create_app(tmp_path / "ws2")
    with TestClient(app1) as client1:
        client1.post(
            "/cases", json={"case_id": "only-in-1", "title": "T", "investigating_agency": "A", "examiner_name": "E"},
        )
    with TestClient(app2) as client2:
        response = client2.get("/cases")
        assert response.json() == []
