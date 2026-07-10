from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import TokenEncryptor
from app.modules.codexneo.activity_log import CodexNeoActivityLogService
from app.modules.codexneo.service import (
    CodexNeoService,
    CodexRestartResult,
    _build_codex_desktop_restart_script,
)

pytestmark = pytest.mark.unit


def _encryptor() -> TokenEncryptor:
    return TokenEncryptor(key=Fernet.generate_key())


def test_restart_script_targets_packaged_chatgpt_shell_and_process_tree() -> None:
    script = _build_codex_desktop_restart_script()

    assert "Get-CimInstance Win32_Process" in script
    assert "*\\WindowsApps\\OpenAI.Codex_*" in script
    assert '$_.Name -ieq "ChatGPT.exe"' in script
    assert "CloseMainWindow" in script
    assert "Stop-Process -Id $target.ProcessId" in script
    assert 'Get-Process -Name "Codex"' not in script
    assert 'Get-Process -Name "codex"' not in script


@pytest.mark.asyncio
async def test_set_api_provider_does_not_restart_codex_after_verified_config_write(tmp_path) -> None:
    calls: list[str] = []

    async def restart_provider() -> CodexRestartResult:
        calls.append("restart")
        return CodexRestartResult(success=True, message="Codex Desktop restarted")

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=restart_provider,
    )

    result = await service.set_api_provider("https://codex.local/v1")

    assert calls == []
    assert result.success is True
    assert result.restart_attempted is False
    assert result.restart_succeeded is None
    assert result.restart_output is None
    assert 'openai_base_url = "https://codex.local/v1"' in (codex_home / "config.toml").read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_revert_api_provider_does_not_restart_codex_after_verified_revert(tmp_path) -> None:
    calls: list[str] = []

    async def restart_provider() -> CodexRestartResult:
        calls.append("restart")
        return CodexRestartResult(success=True, message="Codex Desktop restarted")

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        "# BEGIN CodexNeo provider\n"
        'model_provider = "openai"\n'
        'openai_base_url = "https://codex.local/v1"\n'
        "# END CodexNeo provider\n",
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=restart_provider,
    )

    result = await service.revert_api_provider()

    assert calls == []
    assert result.success is True
    assert result.restart_attempted is False
    assert result.restart_succeeded is None
    assert result.restart_output is None
    assert "CodexNeo provider override reverted" in result.message
    assert "openai_base_url" not in (codex_home / "config.toml").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_restart_codex_app_reports_restart_failure(tmp_path) -> None:
    async def restart_provider() -> CodexRestartResult:
        return CodexRestartResult(success=False, message="Could not relaunch Codex Desktop")

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=restart_provider,
        activity_log_service=CodexNeoActivityLogService(log_path=tmp_path / "activity.log"),
    )

    result = await service.restart_codex_app()

    assert result.success is False
    assert result.restart_attempted is True
    assert result.restart_succeeded is False
    assert result.restart_output == "Could not relaunch Codex Desktop"
    assert "Codex restart failed" in result.message


@pytest.mark.asyncio
async def test_api_provider_set_does_not_restart_when_config_write_fails(tmp_path) -> None:
    calls: list[str] = []

    async def restart_provider() -> CodexRestartResult:
        calls.append("restart")
        return CodexRestartResult(success=True, message="Codex Desktop restarted")

    bad_home = tmp_path / ".codex"
    bad_home.write_text("not a directory", encoding="utf-8")
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=bad_home,
        encryptor=_encryptor(),
        codex_restart_provider=restart_provider,
    )

    with pytest.raises(OSError):
        await service.set_api_provider("https://codex.local/v1")

    assert calls == []
