"""Tests for pramaan.core.writeblock.

These deliberately do not attempt to simulate a hardware write-blocker or a
read-only device special file — that would need real hardware or root-level
device manipulation neither available nor appropriate in a unit test. What
is tested is the one thing this module actually claims: it accurately
reports what the OS did when asked to open a source for writing, and it
never pretends a permitted write-open means something it doesn't.
"""

from __future__ import annotations

import os
import stat

from pramaan.core.writeblock import verify_source_read_only


def test_ordinary_writable_file_is_reported_as_not_blocked(tmp_path):
    p = tmp_path / "case.dd"
    p.write_bytes(b"evidence")
    result = verify_source_read_only(p)
    assert result.write_open_refused is False
    assert "Pramaan itself never performs a write" in result.detail


def test_check_never_modifies_the_file(tmp_path):
    p = tmp_path / "case.dd"
    original = b"evidence-bytes-must-survive"
    p.write_bytes(original)
    verify_source_read_only(p)
    assert p.read_bytes() == original


def test_readonly_file_is_detected_as_permission_refused(tmp_path):
    """os.chmod's read-only bit is honoured on both POSIX (permission bits)
    and Windows (the file's read-only attribute), so this is written once,
    cross-platform, rather than duplicated per OS."""
    p = tmp_path / "case.dd"
    p.write_bytes(b"evidence")
    p.chmod(stat.S_IREAD)
    try:
        result = verify_source_read_only(p)
        assert result.write_open_refused is True
        assert "write-blocker" in result.detail
    finally:
        p.chmod(stat.S_IREAD | stat.S_IWRITE)  # restore so tmp_path cleanup can delete it


def test_generic_os_error_is_reported_as_refused_with_its_own_reason(tmp_path, monkeypatch):
    """A write-open can fail for a reason other than a permission refusal
    (e.g. the device is busy). That must still be reported as refused, but
    with its own explanation rather than being mislabelled as the
    permission-refusal case."""
    p = tmp_path / "case.dd"
    p.write_bytes(b"evidence")

    def _raise_generic_os_error(*args, **kwargs):
        raise OSError("simulated: device or resource busy")

    monkeypatch.setattr(os, "open", _raise_generic_os_error)
    result = verify_source_read_only(p)
    assert result.write_open_refused is True
    assert "simulated: device or resource busy" in result.detail


def test_ledger_entry_shape(tmp_path):
    p = tmp_path / "case.dd"
    p.write_bytes(b"evidence")
    result = verify_source_read_only(p)
    entry = result.as_ledger_entry()
    assert entry["path"] == str(p)
    assert isinstance(entry["write_open_refused"], bool)
    assert isinstance(entry["detail"], str) and entry["detail"]
