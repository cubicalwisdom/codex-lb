from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import uuid4

from sqlalchemy import select, update

from app.core.types import JsonValue
from app.core.utils.json_guards import is_json_mapping
from app.db.models import AnthropicMessageBatch, AnthropicMessageBatchItem
from app.db.session import get_background_session, sqlite_writer_section

_ACTIVE_BATCH_STATUSES: Final[frozenset[str]] = frozenset({"in_progress", "cancelling"})
_TERMINAL_ITEM_STATUSES: Final[frozenset[str]] = frozenset({"succeeded", "errored", "canceled", "expired"})
_BATCH_EXPIRY_SECONDS: Final = 24 * 60 * 60


class BatchNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class BatchCreateItem:
    custom_id: str
    params: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class BatchItemData:
    id: int
    batch_id: str
    sequence: int
    custom_id: str
    status: str
    params: dict[str, JsonValue]
    result: dict[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class BatchData:
    id: str
    api_key_scope: str
    processing_status: str
    created_at: int
    updated_at: int
    ended_at: int | None
    expires_at: int
    request_counts: dict[str, int]

    def to_public(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "type": "message_batch",
            "processing_status": self.processing_status,
            "request_counts": dict(self.request_counts),
            "ended_at": self.ended_at,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "archived_at": None,
            "cancel_initiated_at": self.updated_at if self.processing_status == "cancelling" else None,
            "results_url": f"/v1/messages/batches/{self.id}/results",
        }


def new_batch_id() -> str:
    return f"msgbatch_{uuid4().hex}"


async def create_batch(
    *,
    api_key_scope: str,
    requests: Sequence[BatchCreateItem],
) -> BatchData:
    now = int(time.time())
    batch = AnthropicMessageBatch(
        id=new_batch_id(),
        api_key_scope=api_key_scope,
        processing_status="in_progress",
        created_at=now,
        updated_at=now,
        ended_at=None,
        expires_at=now + _BATCH_EXPIRY_SECONDS,
    )
    items = [
        AnthropicMessageBatchItem(
            batch_id=batch.id,
            sequence=index,
            custom_id=request.custom_id,
            status="queued",
            params_json=_dump_json(request.params),
            result_json=None,
            created_at=now,
            updated_at=now,
        )
        for index, request in enumerate(requests)
    ]
    async with sqlite_writer_section(), get_background_session() as session:
        session.add(batch)
        session.add_all(items)
        await session.commit()
    return await get_batch(batch.id, api_key_scope)


async def get_batch(batch_id: str, api_key_scope: str) -> BatchData:
    async with get_background_session() as session:
        batch = await session.scalar(
            select(AnthropicMessageBatch).where(
                AnthropicMessageBatch.id == batch_id,
                AnthropicMessageBatch.api_key_scope == api_key_scope,
            )
        )
        if batch is None:
            raise BatchNotFoundError(batch_id)
        items = list(
            (
                await session.scalars(
                    select(AnthropicMessageBatchItem).where(AnthropicMessageBatchItem.batch_id == batch.id)
                )
            ).all()
        )
        return _batch_data(batch, items)


async def list_batches(*, api_key_scope: str, limit: int = 20, after_id: str | None = None) -> list[BatchData]:
    async with get_background_session() as session:
        statement = (
            select(AnthropicMessageBatch)
            .where(AnthropicMessageBatch.api_key_scope == api_key_scope)
            .order_by(AnthropicMessageBatch.created_at.desc(), AnthropicMessageBatch.id.desc())
            .limit(limit)
        )
        if after_id:
            cursor = await session.scalar(
                select(AnthropicMessageBatch).where(
                    AnthropicMessageBatch.id == after_id,
                    AnthropicMessageBatch.api_key_scope == api_key_scope,
                )
            )
            if cursor is not None:
                statement = (
                    select(AnthropicMessageBatch)
                    .where(
                        AnthropicMessageBatch.api_key_scope == api_key_scope,
                        AnthropicMessageBatch.created_at <= cursor.created_at,
                        AnthropicMessageBatch.id < cursor.id,
                    )
                    .order_by(AnthropicMessageBatch.created_at.desc(), AnthropicMessageBatch.id.desc())
                    .limit(limit)
                )
        batches = list((await session.scalars(statement)).all())
        result: list[BatchData] = []
        for batch in batches:
            items = list(
                (
                    await session.scalars(
                        select(AnthropicMessageBatchItem).where(AnthropicMessageBatchItem.batch_id == batch.id)
                    )
                ).all()
            )
            result.append(_batch_data(batch, items))
        return result


async def get_batch_items(batch_id: str, api_key_scope: str) -> list[BatchItemData]:
    await get_batch(batch_id, api_key_scope)
    async with get_background_session() as session:
        rows = list(
            (
                await session.scalars(
                    select(AnthropicMessageBatchItem)
                    .where(AnthropicMessageBatchItem.batch_id == batch_id)
                    .order_by(AnthropicMessageBatchItem.sequence.asc())
                )
            ).all()
        )
        return [_item_data(item) for item in rows]


async def claim_next_item(batch_id: str, api_key_scope: str) -> BatchItemData | None:
    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        batch = await session.scalar(
            select(AnthropicMessageBatch).where(
                AnthropicMessageBatch.id == batch_id,
                AnthropicMessageBatch.api_key_scope == api_key_scope,
            )
        )
        if batch is None:
            raise BatchNotFoundError(batch_id)
        if batch.processing_status != "in_progress":
            return None
        if now >= batch.expires_at:
            await session.execute(
                update(AnthropicMessageBatchItem)
                .where(
                    AnthropicMessageBatchItem.batch_id == batch_id,
                    AnthropicMessageBatchItem.status.not_in(_TERMINAL_ITEM_STATUSES),
                )
                .values(
                    status="expired",
                    result_json=_dump_json({"type": "expired"}),
                    updated_at=now,
                )
            )
            batch.processing_status = "ended"
            batch.ended_at = now
            batch.updated_at = now
            await session.commit()
            return None
        item = await session.scalar(
            select(AnthropicMessageBatchItem)
            .where(
                AnthropicMessageBatchItem.batch_id == batch_id,
                AnthropicMessageBatchItem.status == "queued",
            )
            .order_by(AnthropicMessageBatchItem.sequence.asc())
        )
        if item is None:
            return None
        item.status = "in_progress"
        item.updated_at = now
        batch.updated_at = now
        await session.commit()
        return _item_data(item)


async def complete_item(
    *,
    item_id: int,
    status: str,
    result: Mapping[str, JsonValue],
) -> None:
    if status not in _TERMINAL_ITEM_STATUSES:
        raise ValueError("Batch item status must be terminal.")
    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        item = await session.get(AnthropicMessageBatchItem, item_id)
        if item is None:
            return
        if item.status == "canceled":
            return
        item.status = status
        item.result_json = _dump_json(dict(result))
        item.updated_at = now
        batch = await session.get(AnthropicMessageBatch, item.batch_id)
        if batch is not None:
            batch.updated_at = now
        await session.commit()


async def finalize_batch(batch_id: str, api_key_scope: str) -> BatchData:
    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        batch = await session.scalar(
            select(AnthropicMessageBatch).where(
                AnthropicMessageBatch.id == batch_id,
                AnthropicMessageBatch.api_key_scope == api_key_scope,
            )
        )
        if batch is None:
            raise BatchNotFoundError(batch_id)
        items = list(
            (
                await session.scalars(
                    select(AnthropicMessageBatchItem).where(AnthropicMessageBatchItem.batch_id == batch_id)
                )
            ).all()
        )
        if all(item.status in _TERMINAL_ITEM_STATUSES for item in items):
            batch.processing_status = "ended"
            batch.ended_at = now
            batch.updated_at = now
            await session.commit()
        return _batch_data(batch, items)


async def cancel_batch(batch_id: str, api_key_scope: str) -> BatchData:
    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        batch = await session.scalar(
            select(AnthropicMessageBatch).where(
                AnthropicMessageBatch.id == batch_id,
                AnthropicMessageBatch.api_key_scope == api_key_scope,
            )
        )
        if batch is None:
            raise BatchNotFoundError(batch_id)
        await session.execute(
            update(AnthropicMessageBatchItem)
            .where(
                AnthropicMessageBatchItem.batch_id == batch_id,
                AnthropicMessageBatchItem.status.not_in(_TERMINAL_ITEM_STATUSES),
            )
            .values(
                status="canceled",
                result_json=_dump_json({"type": "canceled"}),
                updated_at=now,
            )
        )
        batch.processing_status = "ended"
        batch.updated_at = now
        batch.ended_at = now
        await session.commit()
    return await get_batch(batch_id, api_key_scope)


async def delete_batch(batch_id: str, api_key_scope: str) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        batch = await session.scalar(
            select(AnthropicMessageBatch).where(
                AnthropicMessageBatch.id == batch_id,
                AnthropicMessageBatch.api_key_scope == api_key_scope,
            )
        )
        if batch is None:
            raise BatchNotFoundError(batch_id)
        await session.delete(batch)
        await session.commit()


async def requeue_stranded_batches() -> int:
    """Make restart-interrupted jobs resumable on their next authenticated poll."""

    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        active_batches = list(
            (
                await session.scalars(
                    select(AnthropicMessageBatch).where(AnthropicMessageBatch.processing_status == "in_progress")
                )
            ).all()
        )
        if not active_batches:
            return 0
        batch_ids = [batch.id for batch in active_batches]
        await session.execute(
            update(AnthropicMessageBatchItem)
            .where(
                AnthropicMessageBatchItem.batch_id.in_(batch_ids),
                AnthropicMessageBatchItem.status == "in_progress",
            )
            .values(status="queued", updated_at=now)
        )
        for batch in active_batches:
            batch.updated_at = now
        await session.commit()
        return len(active_batches)


def is_active(batch: BatchData) -> bool:
    return batch.processing_status in _ACTIVE_BATCH_STATUSES


def _batch_data(batch: AnthropicMessageBatch, items: Sequence[AnthropicMessageBatchItem]) -> BatchData:
    counts = {"processing": 0, "succeeded": 0, "errored": 0, "canceled": 0, "expired": 0}
    for item in items:
        if item.status in {"queued", "in_progress"}:
            counts["processing"] += 1
        elif item.status in counts:
            counts[item.status] += 1
    return BatchData(
        id=batch.id,
        api_key_scope=batch.api_key_scope,
        processing_status=batch.processing_status,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        ended_at=batch.ended_at,
        expires_at=batch.expires_at,
        request_counts=counts,
    )


def _item_data(item: AnthropicMessageBatchItem) -> BatchItemData:
    return BatchItemData(
        id=item.id,
        batch_id=item.batch_id,
        sequence=item.sequence,
        custom_id=item.custom_id,
        status=item.status,
        params=_load_object(item.params_json),
        result=_load_object(item.result_json) if item.result_json else None,
    )


def _dump_json(value: Mapping[str, JsonValue]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_object(value: str) -> dict[str, JsonValue]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return dict(decoded) if is_json_mapping(decoded) else {}
