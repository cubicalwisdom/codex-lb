from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

type CodexAuthCommandRunner = Callable[[list[str]], Awaitable[tuple[bool, str]]]
type CodexAuthCommandRunnerWithHome = Callable[[list[str]], Awaitable[tuple[bool, str]]]


async def run_codex_auth_command(args: list[str], *, codex_home: str) -> tuple[bool, str]:
    import asyncio

    return await asyncio.to_thread(_run_codex_auth_command_sync, args, codex_home=codex_home)


def _run_codex_auth_command_sync(args: list[str], *, codex_home: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(Path(codex_home))
    executable = shutil.which("codex-auth") or shutil.which("codex-auth.cmd") or "codex-auth"
    try:
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            check=False,
        )
    except FileNotFoundError:
        return False, "codex-auth command was not found on PATH"
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return completed.returncode == 0, output
