from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

import app.core.bootstrap as bootstrap_module
from app.core.crypto import TokenEncryptor

pytestmark = pytest.mark.unit


def _patch_settings(monkeypatch: pytest.MonkeyPatch, *, token: str | None) -> None:
    monkeypatch.setattr(
        "app.core.bootstrap.get_settings",
        lambda: SimpleNamespace(dashboard_bootstrap_token=token),
    )


def _patch_shared_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    password_hash: str | None,
    bootstrap_token_encrypted: bytes | None,
    bootstrap_token_hash: bytes | None,
) -> None:
    monkeypatch.setattr(
        bootstrap_module,
        "_get_shared_bootstrap_state",
        AsyncMock(return_value=(password_hash, bootstrap_token_encrypted, bootstrap_token_hash)),
    )


def _patch_encryptor(monkeypatch: pytest.MonkeyPatch) -> TokenEncryptor:
    encryptor = TokenEncryptor(key=Fernet.generate_key())
    monkeypatch.setattr(bootstrap_module, "_get_encryptor", lambda: encryptor)
    return encryptor


@pytest.mark.asyncio
async def test_has_active_bootstrap_token_returns_true_when_env_var_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token="manual-token")
    _patch_shared_state(
        monkeypatch, password_hash=None, bootstrap_token_encrypted=b"ignored", bootstrap_token_hash=b"ignored"
    )

    assert await bootstrap_module.has_active_bootstrap_token() is True


@pytest.mark.asyncio
async def test_has_active_bootstrap_token_returns_true_when_hash_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(
        monkeypatch, password_hash=None, bootstrap_token_encrypted=b"encrypted", bootstrap_token_hash=b"hash"
    )

    assert await bootstrap_module.has_active_bootstrap_token() is True


@pytest.mark.asyncio
async def test_has_active_bootstrap_token_returns_false_when_password_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(
        monkeypatch, password_hash="configured", bootstrap_token_encrypted=b"encrypted", bootstrap_token_hash=b"hash"
    )

    assert await bootstrap_module.has_active_bootstrap_token() is False


@pytest.mark.asyncio
async def test_has_active_bootstrap_token_returns_false_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(monkeypatch, password_hash=None, bootstrap_token_encrypted=None, bootstrap_token_hash=None)

    assert await bootstrap_module.has_active_bootstrap_token() is False


@pytest.mark.asyncio
async def test_validate_bootstrap_token_accepts_non_ascii_manual_env_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token="부트스트랩-토큰")
    _patch_shared_state(monkeypatch, password_hash=None, bootstrap_token_encrypted=None, bootstrap_token_hash=None)

    assert await bootstrap_module.validate_bootstrap_token("부트스트랩-토큰") is True


@pytest.mark.asyncio
async def test_validate_bootstrap_token_checks_stored_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(
        monkeypatch,
        password_hash=None,
        bootstrap_token_encrypted=b"encrypted",
        bootstrap_token_hash=hashlib.sha256("shared-auto-token".encode("utf-8")).digest(),
    )

    assert await bootstrap_module.validate_bootstrap_token("shared-auto-token") is True
    assert await bootstrap_module.validate_bootstrap_token("wrong-token") is False


@pytest.mark.asyncio
async def test_has_active_bootstrap_token_reads_uncached_shared_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(
        monkeypatch, password_hash=None, bootstrap_token_encrypted=b"encrypted", bootstrap_token_hash=b"hash"
    )

    assert await bootstrap_module.has_active_bootstrap_token() is True


@pytest.mark.asyncio
async def test_validate_bootstrap_token_reads_uncached_shared_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(
        monkeypatch,
        password_hash=None,
        bootstrap_token_encrypted=b"encrypted",
        bootstrap_token_hash=hashlib.sha256("shared-auto-token".encode("utf-8")).digest(),
    )

    assert await bootstrap_module.validate_bootstrap_token("shared-auto-token") is True


@pytest.mark.asyncio
async def test_get_bootstrap_validation_status_reports_password_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    _patch_shared_state(
        monkeypatch, password_hash="configured", bootstrap_token_encrypted=None, bootstrap_token_hash=None
    )

    assert await bootstrap_module.get_bootstrap_validation_status("shared-auto-token") == "password_already_configured"


@pytest.mark.asyncio
async def test_ensure_auto_bootstrap_token_reuses_existing_encrypted_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token=None)
    encryptor = _patch_encryptor(monkeypatch)
    encrypted = encryptor.encrypt("shared-auto-token")

    async def _get_settings() -> SimpleNamespace:
        return SimpleNamespace(
            password_hash=None,
            bootstrap_token_encrypted=encrypted,
            bootstrap_token_hash=hashlib.sha256("shared-auto-token".encode("utf-8")).digest(),
        )

    repository = SimpleNamespace(
        get_settings=AsyncMock(side_effect=_get_settings),
        clear_bootstrap_token=AsyncMock(),
        store_bootstrap_token_if_absent=AsyncMock(),
    )

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(bootstrap_module, "SessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(bootstrap_module, "DashboardAuthRepository", lambda _session: repository)

    assert await bootstrap_module.ensure_auto_bootstrap_token() == "shared-auto-token"
    repository.store_bootstrap_token_if_absent.assert_not_called()


def test_log_bootstrap_token_emits_at_warning_level_so_docker_default_surfaces_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for #458.

    The token must be logged at a level that survives docker's default
    root-logger WARNING threshold. If it downgrades to INFO, operators
    following the README quickstart cannot find their first-run token.
    """
    import io
    import logging

    monkeypatch.delenv("CODEX_LB_BOOTSTRAP_TOKEN_FILE", raising=False)
    handler_stream = io.StringIO()
    handler = logging.StreamHandler(handler_stream)
    handler.setLevel(logging.WARNING)
    test_logger = logging.getLogger("app.core.bootstrap.test_458_regression")
    test_logger.setLevel(logging.WARNING)
    test_logger.addHandler(handler)
    test_logger.propagate = False

    try:
        bootstrap_module.log_bootstrap_token(test_logger, "tok-regression-458")
    finally:
        test_logger.removeHandler(handler)

    output = handler_stream.getvalue()
    assert "Dashboard bootstrap token" in output
    assert "tok-regression-458" in output


def test_log_bootstrap_token_uses_protected_file_for_portable_runtime(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import logging

    token_file = tmp_path / "bootstrap-token.txt"
    monkeypatch.setenv("CODEX_LB_BOOTSTRAP_TOKEN_FILE", str(token_file))
    monkeypatch.setattr(bootstrap_module, "write_sensitive_bytes_atomic", lambda path, data: path.write_bytes(data))
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    test_logger = logging.getLogger("app.core.bootstrap.test_portable_token")
    test_logger.addHandler(handler)
    test_logger.propagate = False
    try:
        bootstrap_module.log_bootstrap_token(test_logger, "portable-secret")
    finally:
        test_logger.removeHandler(handler)

    assert token_file.read_text(encoding="utf-8") == "portable-secret\n"
    assert "portable-secret" not in stream.getvalue()
    assert str(token_file.resolve()) in stream.getvalue()


@pytest.mark.asyncio
async def test_clear_auto_generated_token_removes_portable_token_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_file = tmp_path / "bootstrap-token.txt"
    token_file.write_text("stale-token", encoding="utf-8")
    monkeypatch.setenv("CODEX_LB_BOOTSTRAP_TOKEN_FILE", str(token_file))
    repository = SimpleNamespace(clear_bootstrap_token=AsyncMock(return_value=True))

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    settings_cache = SimpleNamespace(invalidate=AsyncMock())
    monkeypatch.setattr(bootstrap_module, "SessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(bootstrap_module, "DashboardAuthRepository", lambda _session: repository)
    monkeypatch.setattr(bootstrap_module, "get_settings_cache", lambda: settings_cache)

    await bootstrap_module.clear_auto_generated_token()

    assert token_file.exists() is False
    settings_cache.invalidate.assert_awaited_once()
