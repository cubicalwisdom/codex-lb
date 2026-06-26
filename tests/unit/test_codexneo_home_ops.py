from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import TokenEncryptor
from app.core.exceptions import DashboardBadRequestError
from app.modules.codexneo.accounts import CodexHomeAccountService
from app.modules.codexneo.home import CodexHomeService
from app.modules.codexneo.service import CodexNeoService

pytestmark = pytest.mark.unit


def _encryptor() -> TokenEncryptor:
    return TokenEncryptor(key=Fernet.generate_key())


@pytest.mark.asyncio
async def test_codex_home_save_reset_and_usage_by_service_and_accounts(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    custom_home = tmp_path / "custom-codex"
    custom_accounts = custom_home / "accounts"
    custom_accounts.mkdir(parents=True)
    (custom_accounts / "registry.json").write_text(
        json.dumps({"active_account_key": "acct-1", "accounts": [{"account_key": "acct-1", "email": "a@test"}]}),
        encoding="utf-8",
    )

    home = CodexHomeService(settings_path=settings_path, data_dir=tmp_path / "data")
    saved = home.save_codex_home(str(custom_home))

    assert saved.codex_home == str(custom_home.resolve())
    assert saved.custom_codex_home is True
    assert CodexNeoService(settings_path=settings_path, encryptor=_encryptor()).codex_home == custom_home.resolve()
    accounts = CodexHomeAccountService(settings_path=settings_path).load_accounts()
    assert accounts.registry_path == str(custom_accounts / "registry.json")
    assert accounts.accounts[0].email == "a@test"

    reset = home.reset_codex_home()

    assert reset.custom_codex_home is False
    assert json.loads(settings_path.read_text(encoding="utf-8"))["codex_home_path"] is None


def test_codex_home_rejects_missing_path_and_picker_cancellation(tmp_path) -> None:
    def cancelled_picker() -> str | None:
        return None

    home = CodexHomeService(
        settings_path=tmp_path / "settings.json",
        data_dir=tmp_path / "data",
        folder_picker=cancelled_picker,
    )

    with pytest.raises(DashboardBadRequestError, match="Codex Home folder does not exist"):
        home.save_codex_home(str(tmp_path / "missing"))

    result = home.select_codex_home()

    assert result.success is False
    assert result.message == "No Codex Home folder was selected"
    assert result.path is None
