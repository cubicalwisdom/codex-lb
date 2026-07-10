from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundResponseManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, response_id: str, work: Coroutine[Any, Any, None]) -> None:
        existing = self._tasks.get(response_id)
        if existing is not None and not existing.done():
            raise RuntimeError(f"Background response task already exists: {response_id}")
        task = asyncio.create_task(work, name=f"response-background:{response_id}")
        self._tasks[response_id] = task
        task.add_done_callback(lambda completed: self._task_done(response_id, completed))

    async def cancel(self, response_id: str) -> bool:
        task = self._tasks.get(response_id)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    async def stop(self) -> None:
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def is_active(self, response_id: str) -> bool:
        task = self._tasks.get(response_id)
        return task is not None and not task.done()

    def _task_done(self, response_id: str, task: asyncio.Task[None]) -> None:
        current = self._tasks.get(response_id)
        if current is task:
            self._tasks.pop(response_id, None)
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            logger.error(
                "Background response task failed response_id=%s",
                response_id,
                exc_info=(type(exception), exception, exception.__traceback__),
            )


_manager = BackgroundResponseManager()


def get_background_response_manager() -> BackgroundResponseManager:
    return _manager
