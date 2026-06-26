from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.config.settings import get_settings as get_app_settings
from app.core.exceptions import DashboardBadRequestError
from app.modules.codexneo.schemas import CodexNeoCodexHomeResponse, CodexNeoPathResponse

type FolderPicker = Callable[[], str | None]


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def default_settings_path() -> Path:
    return get_app_settings().data_dir / "codexneo-settings.json"


def codexneo_data_dir() -> Path:
    return get_app_settings().data_dir


def resolve_configured_codex_home(*, settings_path: Path | None = None) -> Path:
    settings_file = settings_path or default_settings_path()
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8")) if settings_file.exists() else {}
    except json.JSONDecodeError:
        data = {}
    custom = data.get("codex_home_path") if isinstance(data, dict) else None
    if isinstance(custom, str) and custom.strip():
        return Path(custom).expanduser().resolve()
    return default_codex_home()


class CodexHomeService:
    def __init__(
        self,
        *,
        settings_path: Path | None = None,
        data_dir: Path | None = None,
        folder_picker: FolderPicker | None = None,
    ) -> None:
        self._settings_path = settings_path or default_settings_path()
        self._data_dir = data_dir or codexneo_data_dir()
        self._folder_picker = folder_picker or pick_windows_folder

    def get_codex_home(self) -> CodexNeoCodexHomeResponse:
        current = resolve_configured_codex_home(settings_path=self._settings_path)
        data = self._read_settings_data()
        custom = isinstance(data.get("codex_home_path"), str) and bool(str(data["codex_home_path"]).strip())
        return CodexNeoCodexHomeResponse(
            codex_home=str(current),
            default_codex_home=str(default_codex_home()),
            data_dir=str(self._data_dir),
            custom_codex_home=custom,
            exists=current.is_dir(),
        )

    def save_codex_home(self, path: str) -> CodexNeoCodexHomeResponse:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise DashboardBadRequestError("Codex Home folder does not exist", code="codex_home_not_found")
        data = self._read_settings_data()
        data["codex_home_path"] = str(resolved)
        self._write_settings_data(data)
        return self.get_codex_home()

    def reset_codex_home(self) -> CodexNeoCodexHomeResponse:
        data = self._read_settings_data()
        data["codex_home_path"] = None
        self._write_settings_data(data)
        return self.get_codex_home()

    def select_codex_home(self) -> CodexNeoPathResponse:
        selected = self._folder_picker()
        if not selected:
            return CodexNeoPathResponse(success=False, message="No Codex Home folder was selected", path=None)
        resolved = Path(selected).expanduser().resolve()
        if not resolved.is_dir():
            return CodexNeoPathResponse(success=False, message="Selected Codex Home folder does not exist", path=None)
        return CodexNeoPathResponse(success=True, message="Codex Home folder selected", path=str(resolved))

    def open_codex_home(self) -> CodexNeoPathResponse:
        current = resolve_configured_codex_home(settings_path=self._settings_path)
        return _open_folder(current, label="Codex Home")

    def open_data_folder(self) -> CodexNeoPathResponse:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        return _open_folder(self._data_dir, label="CodexNeo data folder")

    def _read_settings_data(self) -> dict[str, Any]:
        if not self._settings_path.exists():
            return {"codex_home_path": None}
        try:
            loaded = json.loads(self._settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DashboardBadRequestError("CodexNeo settings file is invalid JSON") from exc
        return loaded if isinstance(loaded, dict) else {"codex_home_path": None}

    def _write_settings_data(self, data: dict[str, Any]) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._settings_path.with_name(f".{self._settings_path.name}.{os.getpid()}.tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.replace(self._settings_path)


def pick_windows_folder() -> str | None:
    if platform.system().lower() != "windows":
        return None
    script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "Choose the existing Codex home folder to use."
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::Out.Write($dialog.SelectedPath)
}
'''
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Sta", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        check=False,
    )
    selected = completed.stdout.strip()
    return selected or None


def _open_folder(path: Path, *, label: str) -> CodexNeoPathResponse:
    if not path.is_dir():
        return CodexNeoPathResponse(success=False, message=f"{label} folder was not found", path=str(path))
    try:
        if platform.system().lower() == "windows":
            subprocess.Popen(["explorer.exe", str(path)])
        return CodexNeoPathResponse(success=True, message=f"Opened {label}", path=str(path))
    except Exception as exc:
        return CodexNeoPathResponse(success=False, message=f"Could not open {label}: {exc}", path=str(path))
