"""
Integration test for scripts/seed_demo_case.py.

This invokes the actual script as a subprocess -- a real process
boundary, not just a function call -- which is why it lives here
alongside the other tests that cross one (see conftest.py).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo_case.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True, text=True, check=False,
    )


def test_seeding_a_fresh_workspace_succeeds(tmp_path):
    result = _run("--workspace", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "Evidence items: 2" in result.stdout
    assert "Clips:          9" in result.stdout
    assert "Findings:       3" in result.stdout
    assert "Ledger chain:   VALID" in result.stdout


def test_seeding_the_same_workspace_twice_fails_without_force(tmp_path):
    first = _run("--workspace", str(tmp_path))
    assert first.returncode == 0, first.stderr

    second = _run("--workspace", str(tmp_path))
    assert second.returncode == 1
    assert "already exists" in second.stderr
    assert "--force" in second.stderr


def test_force_replaces_an_existing_demo_case(tmp_path):
    first = _run("--workspace", str(tmp_path))
    assert first.returncode == 0, first.stderr

    second = _run("--workspace", str(tmp_path), "--force")
    assert second.returncode == 0, second.stderr
    assert "Evidence items: 2" in second.stdout


def test_a_custom_case_id_is_reflected_in_the_workspace(tmp_path):
    result = _run("--workspace", str(tmp_path), "--case-id", "MY-DEMO-1")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "MY-DEMO-1.case").exists()
