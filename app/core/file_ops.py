from __future__ import annotations

import getpass
import logging
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_WINDOWS_RETRY_ERRORS = {5, 32, 33}


def _retry_windows_file_operation(
    operation: Callable[[], _T],
    *,
    attempts: int = 5,
    initial_delay_seconds: float = 0.05,
) -> _T:
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except OSError as exc:
            retryable = os.name == "nt" and (
                isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in _WINDOWS_RETRY_ERRORS
            )
            if not retryable or attempt == attempts:
                raise
            time.sleep(initial_delay_seconds * attempt)
    raise AssertionError("unreachable")


def unlink_with_retry(path: Path, *, missing_ok: bool = False) -> None:
    def unlink() -> None:
        path.unlink(missing_ok=missing_ok)

    _retry_windows_file_operation(unlink)


def replace_with_retry(source: Path, destination: Path) -> None:
    _retry_windows_file_operation(lambda: source.replace(destination))


def copy2_with_retry(source: Path, destination: Path) -> Path:
    return _retry_windows_file_operation(lambda: Path(shutil.copy2(source, destination)))


def protect_sensitive_path(path: Path, *, is_directory: bool | None = None) -> bool:
    """Restrict a sensitive file or directory to the current user.

    POSIX uses owner-only mode bits. Windows uses an explicit ACL because
    ``Path.chmod`` does not remove inherited access-control entries there.
    Protection failures are logged and returned to the caller without
    damaging an already-written file.
    """

    directory = path.is_dir() if is_directory is None else is_directory
    if os.name != "nt":
        path.chmod(0o700 if directory else 0o600)
        return True

    username = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    principal = f"{domain}\\{username}" if domain and "\\" not in username else username
    permission = f"{principal}:(OI)(CI)F" if directory else f"{principal}:F"
    creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        result = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", permission],
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags,
        )
    except OSError:
        logger.warning("Failed to apply a private Windows ACL path=%s", path, exc_info=True)
        return False
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "unknown icacls failure").strip()
        logger.warning("Failed to apply a private Windows ACL path=%s error=%s", path, details)
        return False
    return True


def write_sensitive_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    protect_sensitive_path(path.parent, is_directory=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        protect_sensitive_path(temporary, is_directory=False)
        replace_with_retry(temporary, path)
        protect_sensitive_path(path, is_directory=False)
    finally:
        unlink_with_retry(temporary, missing_ok=True)
