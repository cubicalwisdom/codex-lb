from __future__ import annotations

import json
from typing import Any

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import TokenEncryptor
from app.core.exceptions import DashboardBadRequestError
from app.modules.codexneo.service import (
    CodexGoAction,
    CodexNeoService,
    CodexRestartResult,
    normalize_codexgo_provider_base_url,
)

pytestmark = pytest.mark.unit


def _encryptor() -> TokenEncryptor:
    return TokenEncryptor(key=Fernet.generate_key())


async def _restart_success() -> CodexRestartResult:
    return CodexRestartResult(success=True, message="Codex Desktop restart skipped in test")


class FakeAccountSync:
    def __init__(self) -> None:
        self.calls = 0

    async def sync_codex_home_to_accounts(self):
        self.calls += 1

        class Result:
            success = True
            message = "Synced 1 account(s) into Accounts"
            count = 1

        return Result()


class _FakeApiResponse:
    def __init__(self, payload: Any, *, status: int = 200, json_error: Exception | None = None) -> None:
        self.status = status
        self._payload = payload
        self._json_error = json_error

    async def __aenter__(self) -> _FakeApiResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def json(self, *_args: object, **_kwargs: object) -> Any:
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    async def text(self) -> str:
        return json.dumps(self._payload) if self._json_error is None else "not-json"


class _FakeApiSession:
    def __init__(self, response: _FakeApiResponse) -> None:
        self._response = response
        self.requested_url: str | None = None

    async def __aenter__(self) -> _FakeApiSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def get(self, url: str, **_kwargs: object) -> _FakeApiResponse:
        self.requested_url = url
        return self._response


@pytest.mark.asyncio
async def test_get_settings_defaults_to_native_codex_provider_url(tmp_path) -> None:
    service = CodexNeoService(
        settings_path=tmp_path / "codexneo-settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    settings = await service.get_settings()

    assert settings.codex_api_base_url == "http://127.0.0.1:2455/backend-api/codex"


@pytest.mark.asyncio
async def test_get_settings_persists_exact_legacy_local_provider_migration(tmp_path) -> None:
    settings_path = tmp_path / "codexneo-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "codex_api_base_url": " http://127.0.0.1:2455/v1/ ",
                "openai_activity_log_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=settings_path,
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    settings = await service.get_settings()
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))

    assert settings.codex_api_base_url == "http://127.0.0.1:2455/backend-api/codex"
    assert persisted["codex_api_base_url"] == "http://127.0.0.1:2455/backend-api/codex"
    assert persisted["openai_activity_log_enabled"] is True


@pytest.mark.asyncio
async def test_get_settings_migration_preserves_unknown_persisted_values(tmp_path) -> None:
    settings_path = tmp_path / "codexneo-settings.json"
    future_setting = {"enabled": True, "nested": ["preserve", "me"]}
    settings_path.write_text(
        json.dumps(
            {
                "codex_api_base_url": "http://127.0.0.1:2455/v1",
                "future_setting": future_setting,
            }
        ),
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=settings_path,
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    await service.get_settings()

    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "codex_api_base_url": "http://127.0.0.1:2455/backend-api/codex",
        "future_setting": future_setting,
    }


@pytest.mark.asyncio
async def test_get_settings_preserves_custom_v1_provider_url(tmp_path) -> None:
    settings_path = tmp_path / "codexneo-settings.json"
    settings_path.write_text(
        json.dumps({"codex_api_base_url": "https://codex.example.test/v1/"}),
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=settings_path,
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    settings = await service.get_settings()

    assert settings.codex_api_base_url == "https://codex.example.test/v1"


@pytest.mark.asyncio
async def test_update_settings_encrypts_buyer_token_and_never_returns_plaintext(tmp_path) -> None:
    service = CodexNeoService(
        settings_path=tmp_path / "codexneo-settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    settings = await service.update_settings(
        codex_api_base_url=" http://127.0.0.1:2455/v1/ ",
        codexgo_api_base_url="https://codexgo.eu/api/codex-auth/use",
        codexgo_auto_refresh_enabled=True,
        codexgo_auto_refresh_interval_minutes=1,
        openai_activity_log_enabled=True,
        management_activity_log_enabled=False,
        buyer_token="cg_secret_token",
    )

    raw = (tmp_path / "codexneo-settings.json").read_text(encoding="utf-8")
    saved = json.loads(raw)

    assert settings.codex_api_base_url == "http://127.0.0.1:2455/backend-api/codex"
    assert settings.codexgo_api_base_url == "https://codexgo.eu/api/codex-auth"
    assert settings.codexgo_auto_refresh_enabled is True
    assert settings.codexgo_auto_refresh_interval_minutes == 5
    assert settings.openai_activity_log_enabled is True
    assert settings.management_activity_log_enabled is False
    assert settings.buyer_token_saved is True
    assert "cg_secret_token" not in raw
    assert saved["openai_activity_log_enabled"] is True
    assert saved["management_activity_log_enabled"] is False
    assert saved["buyer_token_encrypted"]


@pytest.mark.asyncio
async def test_get_settings_handles_invalid_saved_refresh_interval(tmp_path) -> None:
    settings_path = tmp_path / "codexneo-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "codexgo_auto_refresh_enabled": True,
                "codexgo_auto_refresh_interval_minutes": "bad-value",
            }
        ),
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=settings_path,
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    settings = await service.get_settings()

    assert settings.codexgo_auto_refresh_interval_minutes == 30


@pytest.mark.asyncio
async def test_update_settings_persists_codex_home_ui_preferences(tmp_path) -> None:
    service = CodexNeoService(
        settings_path=tmp_path / "codexneo-settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    settings = await service.update_settings(
        codex_home_auto_refresh_enabled=True,
        codex_home_auto_refresh_interval_seconds=2,
        codex_home_auto_sync_enabled=True,
        minimize_to_tray_enabled=True,
        start_with_windows_enabled=True,
        auto_delete_free_reauth_accounts_enabled=True,
        auto_delete_quota_exceeded_accounts_enabled=True,
    )

    saved = json.loads((tmp_path / "codexneo-settings.json").read_text(encoding="utf-8"))
    assert settings.codex_home_auto_refresh_enabled is True
    assert settings.codex_home_auto_refresh_interval_seconds == 5
    assert settings.codex_home_auto_sync_enabled is True
    assert settings.minimize_to_tray_enabled is True
    assert settings.start_with_windows_enabled is True
    assert settings.auto_delete_free_reauth_accounts_enabled is True
    assert settings.auto_delete_quota_exceeded_accounts_enabled is True
    assert saved["codex_home_auto_refresh_enabled"] is True
    assert saved["codex_home_auto_refresh_interval_seconds"] == 5
    assert saved["codex_home_auto_sync_enabled"] is True
    assert saved["minimize_to_tray_enabled"] is True
    assert saved["start_with_windows_enabled"] is True
    assert saved["auto_delete_free_reauth_accounts_enabled"] is True
    assert saved["auto_delete_quota_exceeded_accounts_enabled"] is True


def test_normalize_codexgo_provider_base_url_strips_action_suffixes() -> None:
    assert (
        normalize_codexgo_provider_base_url("https://codexgo.eu/api/codex-auth/refresh/")
        == "https://codexgo.eu/api/codex-auth"
    )
    assert (
        normalize_codexgo_provider_base_url("https://codexgo.eu/api/codex-auth/use")
        == "https://codexgo.eu/api/codex-auth"
    )


@pytest.mark.asyncio
async def test_api_provider_test_accepts_native_model_catalog(tmp_path, monkeypatch) -> None:
    session = _FakeApiSession(_FakeApiResponse({"models": [{"slug": "gpt-5.6-sol"}]}))
    monkeypatch.setattr("app.modules.codexneo.service.aiohttp.ClientSession", lambda **_kwargs: session)
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    result = await service.test_api_provider("https://codex.example.test/backend-api/codex")

    assert result.success is True
    assert session.requested_url == "https://codex.example.test/backend-api/codex/models"


@pytest.mark.asyncio
async def test_api_provider_test_rejects_redirected_native_model_catalog(tmp_path, monkeypatch) -> None:
    session = _FakeApiSession(_FakeApiResponse({"models": []}, status=302))
    monkeypatch.setattr("app.modules.codexneo.service.aiohttp.ClientSession", lambda **_kwargs: session)
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    result = await service.test_api_provider("https://codex.example.test/backend-api/codex")

    assert result.success is False
    assert "HTTP 302" in result.message


@pytest.mark.asyncio
async def test_api_provider_test_rejects_generic_openai_model_catalog(tmp_path, monkeypatch) -> None:
    session = _FakeApiSession(_FakeApiResponse({"object": "list", "data": [{"id": "gpt-5.6-sol"}]}))
    monkeypatch.setattr("app.modules.codexneo.service.aiohttp.ClientSession", lambda **_kwargs: session)
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    result = await service.test_api_provider("https://codex.example.test/v1")

    assert result.success is False
    assert "Codex-native model catalog" in result.message


@pytest.mark.asyncio
async def test_api_provider_test_rejects_invalid_json_model_catalog(tmp_path, monkeypatch) -> None:
    session = _FakeApiSession(
        _FakeApiResponse(None, json_error=json.JSONDecodeError("invalid", "not-json", 0))
    )
    monkeypatch.setattr("app.modules.codexneo.service.aiohttp.ClientSession", lambda **_kwargs: session)
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=tmp_path / ".codex",
        encryptor=_encryptor(),
    )

    result = await service.test_api_provider("https://codex.example.test/backend-api/codex")

    assert result.success is False
    assert "valid JSON" in result.message


@pytest.mark.asyncio
async def test_set_api_provider_config_writes_managed_block_and_backup(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text('model = "gpt-5.5"\n\n[profiles.default]\nmodel = "gpt-5.4"\n', encoding="utf-8")
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    result = await service.set_api_provider("https://codex.local/v1/")

    updated = config_path.read_text(encoding="utf-8")
    backups = list(codex_home.glob("config.toml.codexneo-backup-*"))
    assert result.success is True
    assert result.config_path == str(config_path)
    assert backups
    assert "# BEGIN CodexNeo provider" in updated
    assert 'model_provider = "openai"' in updated
    assert 'openai_base_url = "https://codex.local/v1"' in updated
    assert updated.index('openai_base_url = "https://codex.local/v1"') < updated.index("[profiles.default]")


@pytest.mark.asyncio
async def test_set_api_provider_without_override_writes_native_local_default(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text('model = "gpt-5.6-sol"\n', encoding="utf-8")
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    result = await service.set_api_provider()

    updated = config_path.read_text(encoding="utf-8")
    assert result.success is True
    assert 'openai_base_url = "http://127.0.0.1:2455/backend-api/codex"' in updated


@pytest.mark.asyncio
async def test_revert_api_provider_config_removes_managed_override(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text(
        'model = "gpt-5.5"\n'
        "# BEGIN CodexNeo provider\n"
        'model_provider = "openai"\n'
        'openai_base_url = "https://codex.local/v1"\n'
        "# END CodexNeo provider\n\n"
        "[profiles.default]\n"
        'model = "gpt-5.4"\n',
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    result = await service.revert_api_provider()

    updated = config_path.read_text(encoding="utf-8")
    assert result.success is True
    assert "# BEGIN CodexNeo provider" not in updated
    assert "openai_base_url" not in updated
    assert "[profiles.default]" in updated


@pytest.mark.asyncio
async def test_set_api_provider_preserves_original_config_baseline(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    original = 'model = "gpt-5.5"\nmodel_provider = "openai"\n\n[desktop]\nnotifications = true\n'
    config_path.write_text(original, encoding="utf-8")
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    await service.set_api_provider("https://codex.local/v1")
    result = await service.revert_api_provider()

    baseline_path = codex_home / "config.toml.codexneo-original"
    assert result.success is True
    assert baseline_path.read_text(encoding="utf-8") == original
    assert config_path.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_set_api_provider_sanitizes_existing_managed_config_before_saving_original_baseline(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text(
        'model = "gpt-5.5"\n'
        "# BEGIN CodexNeo provider\n"
        'model_provider = "openai"\n'
        'openai_base_url = "http://127.0.0.1:18766/v1"\n'
        "# END CodexNeo provider\n\n"
        "[desktop]\n"
        "notifications = true\n",
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    await service.set_api_provider("https://codex.local/v1")
    result = await service.revert_api_provider()

    baseline = (codex_home / "config.toml.codexneo-original").read_text(encoding="utf-8")
    reverted = config_path.read_text(encoding="utf-8")
    assert result.success is True
    assert "openai_base_url" not in baseline
    assert "# BEGIN CodexNeo provider" not in baseline
    assert 'model = "gpt-5.5"' in baseline
    assert "[desktop]" in baseline
    assert reverted == baseline


@pytest.mark.asyncio
async def test_revert_api_provider_preserves_plain_openai_provider_without_managed_override(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text(
        'model = "gpt-5.5"\n'
        'model_provider = "openai"\n\n'
        "[desktop]\n"
        "notifications = true\n",
        encoding="utf-8",
    )
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    result = await service.revert_api_provider()

    updated = config_path.read_text(encoding="utf-8")
    assert result.success is True
    assert 'model_provider = "openai"' in updated
    assert "openai_base_url" not in updated
    assert "[desktop]" in updated


@pytest.mark.asyncio
async def test_api_provider_config_backup_retention_prunes_old_codexneo_backups_only(tmp_path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text('model = "gpt-5.5"\n', encoding="utf-8")
    original_baseline = codex_home / "config.toml.codexneo-original"
    original_baseline.write_text("protected baseline\n", encoding="utf-8")
    unrelated_backup = codex_home / "config.toml.rc-switcher-backup-20000101-000000"
    unrelated_backup.write_text("windows backup\n", encoding="utf-8")
    for index in range(12):
        backup = codex_home / f"config.toml.codexneo-backup-20000101-0000{index:02d}-000000"
        backup.write_text(f"old backup {index}\n", encoding="utf-8")

    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codex_restart_provider=_restart_success,
    )

    await service.set_api_provider("https://codex.local/v1")

    codexneo_backups = list(codex_home.glob("config.toml.codexneo-backup-*"))
    assert len(codexneo_backups) <= 10
    assert original_baseline.read_text(encoding="utf-8") == "protected baseline\n"
    assert unrelated_backup.read_text(encoding="utf-8") == "windows backup\n"


@pytest.mark.asyncio
async def test_codexgo_use_auth_validates_and_replaces_auth_json(tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    async def provider(url: str, token: str) -> dict[str, object]:
        calls.append((url, token))
        return {"tokens": {"access_token": "access", "account_id": "acct_123"}}

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    auth_path.write_text('{"tokens":{"access_token":"old","account_id":"old"}}', encoding="utf-8")
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codexgo_provider=provider,
    )
    await service.update_settings(
        codexgo_api_base_url="https://codexgo.eu/api/codex-auth/",
        buyer_token="buyer-token",
    )

    result = await service.apply_codexgo_auth(CodexGoAction.USE)

    assert result.success is True
    assert calls == [("https://codexgo.eu/api/codex-auth/use", "buyer-token")]
    assert json.loads(auth_path.read_text(encoding="utf-8")) == {
        "tokens": {"access_token": "access", "account_id": "acct_123"}
    }
    assert list(codex_home.glob("auth.json.codexgo-backup-*"))


@pytest.mark.asyncio
async def test_codexgo_use_auth_syncs_written_auth_to_accounts(tmp_path) -> None:
    async def provider(_url: str, _token: str) -> dict[str, object]:
        return {"tokens": {"access_token": "access", "account_id": "acct_123"}}

    sync = FakeAccountSync()
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codexgo_provider=provider,
        account_sync=sync,
    )
    await service.update_settings(buyer_token="buyer-token")

    result = await service.apply_codexgo_auth(CodexGoAction.USE)

    assert result.success is True
    assert sync.calls == 1
    assert "Accounts sync: Synced 1 account(s) into Accounts" in result.message


@pytest.mark.asyncio
async def test_codexgo_refresh_rejects_invalid_auth_json_without_replacing_file(tmp_path) -> None:
    async def provider(_url: str, _token: str) -> dict[str, object]:
        return {"tokens": {"access_token": "access"}}

    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    auth_path.write_text('{"tokens":{"access_token":"old","account_id":"old"}}', encoding="utf-8")
    service = CodexNeoService(
        settings_path=tmp_path / "settings.json",
        codex_home=codex_home,
        encryptor=_encryptor(),
        codexgo_provider=provider,
    )
    await service.update_settings(buyer_token="buyer-token")

    with pytest.raises(DashboardBadRequestError, match="valid Codex auth JSON"):
        await service.apply_codexgo_auth(CodexGoAction.REFRESH)

    assert json.loads(auth_path.read_text(encoding="utf-8")) == {
        "tokens": {"access_token": "old", "account_id": "old"}
    }
