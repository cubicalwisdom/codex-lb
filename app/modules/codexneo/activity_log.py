from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config.settings import get_settings as get_app_settings

_SENSITIVE_SEGMENT_PATTERN = re.compile(
    r"(^|;)\s*[^;]*(authorization|access_token|refresh_token|id_token|api[_ -]?key|buyer[_ -]?token)[^;]*",
    re.IGNORECASE,
)
MAX_ACTIVITY_LOG_LINES = 1000


def default_activity_log_path() -> Path:
    return get_app_settings().data_dir / "codexneo-activity.log"


def default_activity_settings_path() -> Path:
    return get_app_settings().data_dir / "codexneo-settings.json"


class CodexNeoActivityLogService:
    def __init__(
        self,
        *,
        log_path: Path | None = None,
        settings_path: Path | None = None,
        respect_settings: bool | None = None,
    ) -> None:
        self._log_path = log_path or default_activity_log_path()
        self._settings_path = settings_path or default_activity_settings_path()
        self._respect_settings = (
            (log_path is None or settings_path is not None) if respect_settings is None else respect_settings
        )

    @property
    def log_path(self) -> Path:
        return self._log_path

    def read(self) -> str:
        if not self._log_path.exists():
            return ""
        return self._log_path.read_text(encoding="utf-8")

    def append(self, stream: str, message: str) -> None:
        if self._respect_settings and not _stream_enabled(self._settings_path, stream):
            return
        safe_message = _sanitize_message(message)
        if not safe_message:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {safe_message}\n"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        _retain_latest_lines(self._log_path, MAX_ACTIVITY_LOG_LINES)

    def clear(self) -> None:
        try:
            self._log_path.unlink()
        except FileNotFoundError:
            pass


def _sanitize_message(message: str) -> str:
    first_line = message.splitlines()[0] if message else ""
    cleaned = _SENSITIVE_SEGMENT_PATTERN.sub("", first_line)
    cleaned = "".join(char if char >= " " else " " for char in cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ;")
    return cleaned[:1000]


def _stream_enabled(settings_path: Path, stream: str) -> bool:
    key_by_stream = {
        "openai": "openai_activity_log_enabled",
        "management": "management_activity_log_enabled",
    }
    setting_key = key_by_stream.get(stream)
    if setting_key is None:
        return False
    if not settings_path.exists():
        return False
    try:
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(loaded, dict):
        return False
    return bool(loaded.get(setting_key))


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _retain_latest_lines(path: Path, max_lines: int) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) <= max_lines:
        return
    write_text_atomic(path, "".join(lines[-max_lines:]))
