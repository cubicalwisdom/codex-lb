from __future__ import annotations

import base64
from pathlib import Path


def encoded_snapshot_name(account_key: str) -> str:
    encoded = base64.urlsafe_b64encode(account_key.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{encoded}.auth.json"


def raw_snapshot_name(account_key: str) -> str:
    return f"{account_key}.auth.json"


def preferred_snapshot_path(directory: Path, account_key: str) -> Path:
    if _is_simple_filename_stem(account_key):
        return directory / raw_snapshot_name(account_key)
    return directory / encoded_snapshot_name(account_key)


def existing_snapshot_path(directory: Path, account_key: str) -> Path | None:
    for name in _snapshot_names(account_key):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def snapshot_exists(directory: Path, account_key: str) -> bool:
    return existing_snapshot_path(directory, account_key) is not None


def delete_snapshot_files(directory: Path, account_key: str) -> None:
    for name in _snapshot_names(account_key):
        try:
            (directory / name).unlink()
        except FileNotFoundError:
            pass


def account_key_from_snapshot(path: Path) -> str:
    stem = path.name.removesuffix(".auth.json")
    decoded = _decode_snapshot_stem(stem)
    return decoded or stem


def _snapshot_names(account_key: str) -> list[str]:
    names = [encoded_snapshot_name(account_key)]
    if _is_simple_filename_stem(account_key):
        names.insert(0, raw_snapshot_name(account_key))
    result: list[str] = []
    for name in names:
        if name not in result:
            result.append(name)
    return result


def _is_simple_filename_stem(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in {"_", ".", "-"} for char in value)


def _decode_snapshot_stem(stem: str) -> str | None:
    padding = "=" * (-len(stem) % 4)
    try:
        decoded = base64.urlsafe_b64decode((stem + padding).encode("ascii")).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return None
    if not decoded or encoded_snapshot_name(decoded).removesuffix(".auth.json") != stem:
        return None
    return decoded
