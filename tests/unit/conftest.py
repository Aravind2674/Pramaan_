"""Shared fixtures for the API layer's unit tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from pramaan.api.app import create_app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    """A ``TestClient`` bound to a fresh, empty workspace directory --
    one per test, so no test can observe another's cases."""
    app = create_app(tmp_path / "workspace")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def existing_case_id(client: TestClient) -> str:
    """A case already created in ``client``'s workspace, for tests that
    only care about acting on an existing case rather than creation
    itself."""
    response = client.post(
        "/cases",
        json={
            "case_id": "sample-case",
            "title": "Sample Investigation",
            "investigating_agency": "Cyber Cell",
            "examiner_name": "Dr. A. Examiner",
        },
    )
    assert response.status_code == 201
    return "sample-case"
