from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundAnthropicBatchManager:
    """Own local batch tasks without coupling them to request lifetimes."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, batch_id: str, work: Coroutine[Any, Any, None]) -> None:
        existing = self._tasks.get(batch_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(work, name=f"anthropic-message-batch:{batch_id}")
        self._tasks[batch_id] = task
        task.add_done_callback(lambda completed: self._task_done(batch_id, completed))

    async def cancel(self, batch_id: str) -> bool:
        task = self._tasks.get(batch_id)
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

    def is_active(self, batch_id: str) -> bool:
        task = self._tasks.get(batch_id)
        return task is not None and not task.done()

    def _task_done(self, batch_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(batch_id) is task:
            self._tasks.pop(batch_id, None)
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            logger.error(
                "Anthropic message batch task failed batch_id=%s",
                batch_id,
                exc_info=(type(exception), exception, exception.__traceback__),
            )


_manager = BackgroundAnthropicBatchManager()


def get_background_anthropic_batch_manager() -> BackgroundAnthropicBatchManager:
    return _manager
