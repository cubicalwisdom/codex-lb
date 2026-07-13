from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.core import file_ops


def test_retry_windows_file_operation_retries_sharing_violation(monkeypatch) -> None:
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            exc = PermissionError("busy")
            exc.winerror = 32  # type: ignore[attr-defined]
            raise exc
        return "done"

    monkeypatch.setattr(file_ops.os, "name", "nt")
    monkeypatch.setattr(file_ops.time, "sleep", lambda _seconds: None)

    assert file_ops._retry_windows_file_operation(operation) == "done"
    assert attempts == 3


def test_write_sensitive_bytes_atomic_replaces_destination(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "secret.txt"
    monkeypatch.setattr(file_ops, "protect_sensitive_path", lambda *_args, **_kwargs: True)

    file_ops.write_sensitive_bytes_atomic(target, b"new-secret")

    assert target.read_bytes() == b"new-secret"
    assert list(tmp_path.glob("*.tmp")) == []


def test_protect_sensitive_path_uses_windows_acl(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("secret", encoding="utf-8")
    calls: list[list[str]] = []

    def run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(file_ops.os, "name", "nt")
    monkeypatch.setenv("USERNAME", "test-user")
    monkeypatch.setenv("USERDOMAIN", "TESTDOMAIN")
    monkeypatch.setattr(file_ops.subprocess, "run", run)

    assert file_ops.protect_sensitive_path(target, is_directory=False) is True
    assert calls == [
        [
            "icacls",
            str(target),
            "/inheritance:r",
            "/grant:r",
            "TESTDOMAIN\\test-user:F",
        ]
    ]
