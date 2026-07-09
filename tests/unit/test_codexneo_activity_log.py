from __future__ import annotations

import json

from app.modules.codexneo.activity_log import CodexNeoActivityLogService

pytestmark = __import__("pytest").mark.unit


def test_activity_log_appends_sanitized_lines_and_clear_deletes_file(tmp_path) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    service = CodexNeoActivityLogService(log_path=log_path)

    service.append(
        "openai",
        "OpenAI API POST /v1/responses -> 200; Authorization: Bearer sk-secret; "
        "access_token=secret-access; refresh_token=secret-refresh; requestBytes=123;\nraw body",
    )
    service.append("management", "Management API GET /api/accounts -> 200; 5ms.")

    contents = service.read()

    assert log_path.exists()
    assert "OpenAI API POST /v1/responses -> 200" in contents
    assert "Management API GET /api/accounts -> 200" in contents
    assert "Authorization" not in contents
    assert "sk-secret" not in contents
    assert "secret-access" not in contents
    assert "secret-refresh" not in contents
    assert "raw body" not in contents

    service.clear()

    assert not log_path.exists()
    assert service.read() == ""


def test_activity_log_retains_only_latest_1000_lines(tmp_path) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    service = CodexNeoActivityLogService(log_path=log_path)

    for index in range(1005):
        service.append("management", f"Management API GET /api/dashboard/overview -> 200; seq={index}; 5ms.")

    lines = service.read().splitlines()

    assert len(lines) == 1000
    assert "seq=0;" not in service.read()
    assert "seq=4;" not in service.read()
    assert "seq=5;" in lines[0]
    assert "seq=1004;" in lines[-1]


def test_activity_log_respects_saved_stream_settings(tmp_path) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    settings_path = tmp_path / "codexneo-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "codex_api_base_url": "http://127.0.0.1:2455/backend-api/codex",
                "codexgo_api_base_url": "https://codexgo.eu/api/codex-auth",
                "codexgo_auto_refresh_enabled": False,
                "codexgo_auto_refresh_interval_minutes": 30,
                "openai_activity_log_enabled": True,
                "management_activity_log_enabled": False,
                "codex_home_path": None,
                "buyer_token_encrypted": None,
            }
        ),
        encoding="utf-8",
    )
    service = CodexNeoActivityLogService(log_path=log_path, settings_path=settings_path)

    service.append("management", "Management API GET /api/dashboard/overview -> 200; 5ms.")
    service.append("openai", "OpenAI API GET /v1/models -> 200; 5ms.")

    contents = service.read()

    assert "Management API" not in contents
    assert "OpenAI API GET /v1/models -> 200" in contents
