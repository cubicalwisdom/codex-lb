from __future__ import annotations

import json
from datetime import datetime, timedelta

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


def test_activity_log_keeps_all_events_inside_the_one_day_retention_window(tmp_path) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    service = CodexNeoActivityLogService(log_path=log_path)

    for index in range(1005):
        service.append("management", f"Management API GET /api/dashboard/overview -> 200; seq={index}; 5ms.")

    lines = service.read().splitlines()

    assert len(lines) == 1005
    assert "seq=0;" in lines[0]
    assert "seq=1004;" in lines[-1]


def test_activity_log_prunes_entries_older_than_one_day(tmp_path) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    now = datetime(2026, 7, 12, 12, 0, 0)
    service = CodexNeoActivityLogService(log_path=log_path, now=lambda: now)

    service.append("codex_lb", "old event")
    now += timedelta(hours=24, seconds=1)
    service.append("codexneo", "new event")

    contents = service.read()

    assert "old event" not in contents
    assert "new event" in contents


def test_activity_log_read_prunes_without_a_new_event(tmp_path) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    now = datetime(2026, 7, 12, 12, 0, 0)
    service = CodexNeoActivityLogService(log_path=log_path, now=lambda: now)
    service.append("codex_lb", "old event")

    now += timedelta(hours=24, seconds=1)

    assert service.read() == ""


def test_activity_append_does_not_rewrite_the_full_log(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "codexneo-activity.log"
    service = CodexNeoActivityLogService(log_path=log_path)
    atomic_writes = 0

    def record_atomic_write(path, text) -> None:
        nonlocal atomic_writes
        atomic_writes += 1

    monkeypatch.setattr("app.modules.codexneo.activity_log.write_text_atomic", record_atomic_write)

    service.append("codex_lb", "Request routed -> 200")

    assert atomic_writes == 0


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


def test_combined_activity_records_every_safe_component_event(tmp_path) -> None:
    service = CodexNeoActivityLogService(log_path=tmp_path / "activity.log", respect_settings=False)

    service.append("codex_lb", "Request routed -> 200")
    service.append("codexneo", "Backup saved")
    service.append("provider", "Provider auth ingested")

    contents = service.read()
    assert "[codex_lb] Request routed -> 200" in contents
    assert "[codexneo] Backup saved" in contents
    assert "[provider] Provider auth ingested" in contents
