from __future__ import annotations

import time
from typing import Any, cast

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.modules.codexneo.activity_log import CodexNeoActivityLogService


def add_codexneo_activity_log_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def codexneo_activity_log_middleware(request: Request, call_next: Any) -> Response:
        started = time.perf_counter()
        response = cast(Response, await call_next(request))
        await _append_activity_summary(request, response, elapsed_ms=(time.perf_counter() - started) * 1000)
        return response


async def _append_activity_summary(request: Request, response: Response, *, elapsed_ms: float) -> None:
    path = request.url.path
    if path.startswith("/api/codexneo/activity-log"):
        return
    if path.startswith("/v1/"):
        label = "Codex LB"
        stream = "codex_lb"
    elif path.startswith("/api/"):
        label = "CodexNeo" if path.startswith("/api/codexneo/") else "Codex LB"
        stream = "codexneo" if path.startswith("/api/codexneo/") else "codex_lb"
    else:
        return
    message = f"{label} {request.method} {path} -> {response.status_code}; {int(elapsed_ms)}ms."
    CodexNeoActivityLogService(respect_settings=False).append(stream, message)
