from __future__ import annotations

import subprocess

import pytest

from app.modules.codexneo import command_runner

pytestmark = pytest.mark.unit


def test_codex_auth_command_runner_uses_resolved_windows_shim(monkeypatch, tmp_path) -> None:
    shim = tmp_path / "codex-auth.cmd"
    calls: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        assert command == "codex-auth"
        return str(shim)

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["env"]["CODEX_HOME"] == str(tmp_path / ".codex")
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(command_runner.shutil, "which", fake_which)
    monkeypatch.setattr(command_runner.subprocess, "run", fake_run)

    ok, output = command_runner._run_codex_auth_command_sync(["list"], codex_home=str(tmp_path / ".codex"))

    assert ok is True
    assert output == "ok"
    assert calls == [[str(shim), "list"]]
