"""Tests for pramaan.api.workspace."""

from __future__ import annotations

import pytest

from pramaan.api.workspace import CaseWorkspace, WorkspaceError


def test_create_case_and_open_it(tmp_path):
    ws = CaseWorkspace(tmp_path)
    created = ws.create_case("c1", title="T", investigating_agency="A", examiner_name="E")
    info = created.info()
    created.close()
    assert info.case_id == "c1"
    assert info.title == "T"

    opened = ws.open_case("c1")
    try:
        assert opened.info().case_id == "c1"
    finally:
        opened.close()


def test_create_case_twice_raises(tmp_path):
    ws = CaseWorkspace(tmp_path)
    ws.create_case("c1", title="T", investigating_agency="A", examiner_name="E").close()
    with pytest.raises(WorkspaceError):
        ws.create_case("c1", title="T2", investigating_agency="A", examiner_name="E")


def test_open_nonexistent_case_raises(tmp_path):
    ws = CaseWorkspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.open_case("does-not-exist")


def test_list_case_ids_is_sorted_and_reflects_created_cases(tmp_path):
    ws = CaseWorkspace(tmp_path)
    ws.create_case("bravo", title="T", investigating_agency="A", examiner_name="E").close()
    ws.create_case("alpha", title="T", investigating_agency="A", examiner_name="E").close()
    assert ws.list_case_ids() == ["alpha", "bravo"]


def test_workspace_creates_its_root_directory_if_missing(tmp_path):
    root = tmp_path / "nested" / "workspace"
    assert not root.exists()
    ws = CaseWorkspace(root)
    assert root.is_dir()
    assert ws.root == root


@pytest.mark.parametrize("bad_id", ["", ".", "..", "-leading-dash", "a/b", "a\\b", "trailing.", "a" * 101])
def test_rejects_invalid_case_ids(tmp_path, bad_id):
    ws = CaseWorkspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.create_case(bad_id, title="T", investigating_agency="A", examiner_name="E")


def test_case_id_cannot_escape_the_workspace_directory(tmp_path):
    """The whole point of the ID format: even a maximally adversarial
    case ID cannot land a case file outside the workspace root."""
    ws = CaseWorkspace(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.create_case("../escaped", title="T", investigating_agency="A", examiner_name="E")
    assert not (tmp_path.parent / "escaped.case").exists()


def test_a_valid_single_character_case_id_is_accepted(tmp_path):
    ws = CaseWorkspace(tmp_path)
    ws.create_case("a", title="T", investigating_agency="A", examiner_name="E").close()
    assert ws.list_case_ids() == ["a"]
