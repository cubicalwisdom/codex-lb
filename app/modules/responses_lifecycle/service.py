from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from sqlalchemy import delete, func, select, update

from app.core.types import JsonValue
from app.core.utils.json_guards import is_json_mapping
from app.db.models import StoredConversation, StoredConversationItem, StoredResponse
from app.db.session import get_background_session, sqlite_writer_section

ANONYMOUS_API_KEY_SCOPE = "local:anonymous"
ACTIVE_RESPONSE_STATUSES = frozenset({"queued", "in_progress"})
TERMINAL_RESPONSE_STATUSES = frozenset({"completed", "failed", "cancelled", "incomplete"})


class LifecycleResourceNotFoundError(LookupError):
    pass


class LifecycleStateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredResponseData:
    id: str
    api_key_scope: str
    upstream_response_id: str | None
    conversation_id: str | None
    status: str
    background: bool
    request: dict[str, JsonValue]
    input_items: list[JsonValue]
    response: dict[str, JsonValue]
    created_at: int
    updated_at: int
    completed_at: int | None


@dataclass(frozen=True, slots=True)
class ConversationData:
    id: str
    metadata: dict[str, str]
    created_at: int
    updated_at: int

    def to_public(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "object": "conversation",
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


def new_response_id() -> str:
    return f"resp_{uuid4().hex}"


def new_conversation_id() -> str:
    return f"conv_{uuid4().hex}"


def normalize_input_items(input_value: JsonValue) -> list[JsonValue]:
    if isinstance(input_value, str):
        return [_normalize_item({"type": "message", "role": "user", "content": input_value})]
    if not isinstance(input_value, list):
        return []
    return [_normalize_item(item) for item in cast(list[JsonValue], input_value)]


def normalize_conversation_items(items: Sequence[JsonValue]) -> list[JsonValue]:
    return [_normalize_item(item) for item in items]


def public_response_shell(
    *,
    response_id: str,
    model: str,
    created_at: int,
    status: str,
    background: bool,
    instructions: str | None,
    tools: Sequence[JsonValue],
    tool_choice: JsonValue | None,
    parallel_tool_calls: bool | None,
    metadata: Mapping[str, str] | None,
    previous_response_id: str | None,
    conversation_id: str | None,
) -> dict[str, JsonValue]:
    response: dict[str, JsonValue] = {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": status,
        "background": background,
        "model": model,
        "output": [],
        "parallel_tool_calls": True if parallel_tool_calls is None else parallel_tool_calls,
        "tool_choice": tool_choice if tool_choice is not None else "auto",
        "tools": list(tools),
        "error": None,
        "incomplete_details": None,
    }
    if instructions is not None:
        response["instructions"] = instructions
    if metadata is not None:
        response["metadata"] = dict(metadata)
    if previous_response_id is not None:
        response["previous_response_id"] = previous_response_id
    if conversation_id is not None:
        response["conversation"] = {"id": conversation_id}
    return response


def finalize_public_response(
    response: Mapping[str, JsonValue],
    *,
    public_response_id: str,
    background: bool,
    metadata: Mapping[str, str] | None,
    conversation_id: str | None,
) -> dict[str, JsonValue]:
    normalized = dict(response)
    normalized["id"] = public_response_id
    normalized["object"] = "response"
    normalized["background"] = background
    if metadata is not None:
        normalized["metadata"] = dict(metadata)
    if conversation_id is not None:
        normalized["conversation"] = {"id": conversation_id}
    return normalized


async def create_response(
    *,
    response_id: str,
    api_key_scope: str,
    status: str,
    background: bool,
    request: Mapping[str, JsonValue],
    input_items: Sequence[JsonValue],
    response: Mapping[str, JsonValue],
    conversation_id: str | None,
    created_at: int | None = None,
) -> StoredResponseData:
    now = int(time.time()) if created_at is None else created_at
    record = StoredResponse(
        id=response_id,
        api_key_scope=api_key_scope,
        upstream_response_id=None,
        conversation_id=conversation_id,
        status=status,
        background=background,
        request_json=_dump_json(dict(request)),
        input_items_json=_dump_json(list(input_items)),
        response_json=_dump_json(dict(response)),
        created_at=now,
        updated_at=now,
        completed_at=now if status in TERMINAL_RESPONSE_STATUSES else None,
    )
    async with sqlite_writer_section(), get_background_session() as session:
        session.add(record)
        await session.commit()
    return _stored_response_data(record)


async def get_response(response_id: str, api_key_scope: str) -> StoredResponseData:
    async with get_background_session() as session:
        record = await session.scalar(
            select(StoredResponse).where(
                StoredResponse.id == response_id,
                StoredResponse.api_key_scope == api_key_scope,
            )
        )
        if record is None:
            raise LifecycleResourceNotFoundError(response_id)
        return _stored_response_data(record)


async def resolve_previous_response_id(response_id: str, api_key_scope: str) -> str:
    async with get_background_session() as session:
        record = await session.scalar(
            select(StoredResponse).where(StoredResponse.id == response_id)
        )
        if record is None:
            return response_id
        if record.api_key_scope != api_key_scope:
            raise LifecycleResourceNotFoundError(response_id)
        if not record.upstream_response_id:
            raise LifecycleStateError("The previous response has not completed yet.")
        return record.upstream_response_id


async def update_response_status(
    response_id: str,
    api_key_scope: str,
    *,
    status: str,
    response: Mapping[str, JsonValue] | None = None,
    upstream_response_id: str | None = None,
) -> StoredResponseData:
    now = int(time.time())
    values: dict[str, object] = {
        "status": status,
        "updated_at": now,
        "completed_at": now if status in TERMINAL_RESPONSE_STATUSES else None,
    }
    if response is not None:
        values["response_json"] = _dump_json(dict(response))
    if upstream_response_id is not None:
        values["upstream_response_id"] = upstream_response_id
    async with sqlite_writer_section(), get_background_session() as session:
        result = await session.execute(
            update(StoredResponse)
            .where(
                StoredResponse.id == response_id,
                StoredResponse.api_key_scope == api_key_scope,
            )
            .values(**values)
        )
        if _rowcount(result) == 0:
            raise LifecycleResourceNotFoundError(response_id)
        await session.commit()
    return await get_response(response_id, api_key_scope)


async def delete_response(response_id: str, api_key_scope: str) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        result = await session.execute(
            delete(StoredResponse).where(
                StoredResponse.id == response_id,
                StoredResponse.api_key_scope == api_key_scope,
            )
        )
        if _rowcount(result) == 0:
            raise LifecycleResourceNotFoundError(response_id)
        await session.commit()


async def mark_stranded_responses_failed() -> int:
    now = int(time.time())
    count = 0
    async with sqlite_writer_section(), get_background_session() as session:
        records = list(
            (
                await session.scalars(
                    select(StoredResponse).where(StoredResponse.status.in_(ACTIVE_RESPONSE_STATUSES))
                )
            ).all()
        )
        for record in records:
            payload = _load_object(record.response_json)
            payload.update(
                {
                    "status": "failed",
                    "error": {
                        "code": "background_worker_restarted",
                        "message": "The local background worker stopped before this response completed.",
                        "type": "server_error",
                    },
                }
            )
            record.status = "failed"
            record.response_json = _dump_json(payload)
            record.updated_at = now
            record.completed_at = now
            count += 1
        if count:
            await session.commit()
    return count


async def create_conversation(
    api_key_scope: str,
    *,
    metadata: Mapping[str, str] | None = None,
    items: Sequence[JsonValue] = (),
) -> ConversationData:
    now = int(time.time())
    conversation = StoredConversation(
        id=new_conversation_id(),
        api_key_scope=api_key_scope,
        metadata_json=_dump_json(dict(metadata or {})),
        created_at=now,
        updated_at=now,
    )
    normalized_items = normalize_conversation_items(items)
    async with sqlite_writer_section(), get_background_session() as session:
        session.add(conversation)
        await session.flush()
        _add_item_records(session, conversation.id, normalized_items, start_sequence=1, created_at=now)
        await session.commit()
    return _conversation_data(conversation)


async def get_conversation(conversation_id: str, api_key_scope: str) -> ConversationData:
    async with get_background_session() as session:
        conversation = await session.scalar(
            select(StoredConversation).where(
                StoredConversation.id == conversation_id,
                StoredConversation.api_key_scope == api_key_scope,
            )
        )
        if conversation is None:
            raise LifecycleResourceNotFoundError(conversation_id)
        return _conversation_data(conversation)


async def update_conversation(
    conversation_id: str,
    api_key_scope: str,
    metadata: Mapping[str, str],
) -> ConversationData:
    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        result = await session.execute(
            update(StoredConversation)
            .where(
                StoredConversation.id == conversation_id,
                StoredConversation.api_key_scope == api_key_scope,
            )
            .values(metadata_json=_dump_json(dict(metadata)), updated_at=now)
        )
        if _rowcount(result) == 0:
            raise LifecycleResourceNotFoundError(conversation_id)
        await session.commit()
    return await get_conversation(conversation_id, api_key_scope)


async def delete_conversation(conversation_id: str, api_key_scope: str) -> None:
    async with sqlite_writer_section(), get_background_session() as session:
        result = await session.execute(
            delete(StoredConversation).where(
                StoredConversation.id == conversation_id,
                StoredConversation.api_key_scope == api_key_scope,
            )
        )
        if _rowcount(result) == 0:
            raise LifecycleResourceNotFoundError(conversation_id)
        await session.commit()


async def append_conversation_items(
    conversation_id: str,
    api_key_scope: str,
    items: Sequence[JsonValue],
) -> list[JsonValue]:
    normalized_items = normalize_conversation_items(items)
    if not normalized_items:
        await get_conversation(conversation_id, api_key_scope)
        return []
    now = int(time.time())
    async with sqlite_writer_section(), get_background_session() as session:
        conversation = await session.scalar(
            select(StoredConversation)
            .where(
                StoredConversation.id == conversation_id,
                StoredConversation.api_key_scope == api_key_scope,
            )
            .with_for_update()
        )
        if conversation is None:
            raise LifecycleResourceNotFoundError(conversation_id)
        current_max = await session.scalar(
            select(func.max(StoredConversationItem.sequence)).where(
                StoredConversationItem.conversation_id == conversation_id
            )
        )
        start_sequence = int(current_max or 0) + 1
        _add_item_records(
            session,
            conversation_id,
            normalized_items,
            start_sequence=start_sequence,
            created_at=now,
        )
        conversation.updated_at = now
        await session.commit()
    return normalized_items


async def list_conversation_items(
    conversation_id: str,
    api_key_scope: str,
    *,
    after: str | None = None,
    limit: int = 20,
    order: str = "desc",
) -> dict[str, JsonValue]:
    await get_conversation(conversation_id, api_key_scope)
    async with get_background_session() as session:
        records = list(
            (
                await session.scalars(
                    select(StoredConversationItem)
                    .where(StoredConversationItem.conversation_id == conversation_id)
                    .order_by(
                        StoredConversationItem.sequence.asc()
                        if order == "asc"
                        else StoredConversationItem.sequence.desc()
                    )
                )
            ).all()
        )
        page_records, has_more = _cursor_page(records, after=after, limit=limit)
        data = [_load_json(record.item_json) for record in page_records]
        ids = [record.id for record in page_records]
    return {
        "object": "list",
        "data": data,
        "first_id": ids[0] if ids else "",
        "last_id": ids[-1] if ids else "",
        "has_more": has_more,
    }


async def get_conversation_item(
    conversation_id: str,
    item_id: str,
    api_key_scope: str,
) -> JsonValue:
    await get_conversation(conversation_id, api_key_scope)
    async with get_background_session() as session:
        record = await session.scalar(
            select(StoredConversationItem).where(
                StoredConversationItem.id == item_id,
                StoredConversationItem.conversation_id == conversation_id,
            )
        )
        if record is None:
            raise LifecycleResourceNotFoundError(item_id)
        return _load_json(record.item_json)


async def delete_conversation_item(
    conversation_id: str,
    item_id: str,
    api_key_scope: str,
) -> ConversationData:
    conversation = await get_conversation(conversation_id, api_key_scope)
    async with sqlite_writer_section(), get_background_session() as session:
        result = await session.execute(
            delete(StoredConversationItem).where(
                StoredConversationItem.id == item_id,
                StoredConversationItem.conversation_id == conversation_id,
            )
        )
        if _rowcount(result) == 0:
            raise LifecycleResourceNotFoundError(item_id)
        await session.commit()
    return conversation


async def conversation_items_for_execution(conversation_id: str, api_key_scope: str) -> list[JsonValue]:
    await get_conversation(conversation_id, api_key_scope)
    async with get_background_session() as session:
        records = list(
            (
                await session.scalars(
                    select(StoredConversationItem)
                    .where(StoredConversationItem.conversation_id == conversation_id)
                    .order_by(StoredConversationItem.sequence.asc())
                )
            ).all()
        )
        return [_load_json(record.item_json) for record in records]


def paginate_input_items(
    items: Sequence[JsonValue],
    *,
    after: str | None,
    limit: int,
    order: str,
) -> dict[str, JsonValue]:
    ordered = list(items if order == "asc" else reversed(items))
    if after is not None:
        after_index = next(
            (
                index
                for index, item in enumerate(ordered)
                if is_json_mapping(item) and item.get("id") == after
            ),
            None,
        )
        ordered = [] if after_index is None else ordered[after_index + 1 :]
    has_more = len(ordered) > limit
    data = ordered[:limit]
    return {"object": "list", "data": data, "has_more": has_more}


def _normalize_item(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        value = {"type": "message", "role": "user", "content": value}
    if not isinstance(value, dict):
        return value
    item = dict(value)
    item_type = item.get("type")
    if not isinstance(item_type, str):
        item_type = "message" if isinstance(item.get("role"), str) else "item"
        item["type"] = item_type
    if not isinstance(item.get("id"), str) or not str(item["id"]).strip():
        prefix = "msg" if item_type == "message" else "item"
        item["id"] = f"{prefix}_{uuid4().hex}"
    if item_type == "message":
        content = item.get("content")
        if isinstance(content, str):
            content_type = "output_text" if item.get("role") == "assistant" else "input_text"
            item["content"] = [{"type": content_type, "text": content}]
        item.setdefault("status", "completed")
    return item


def _add_item_records(
    session: object,
    conversation_id: str,
    items: Sequence[JsonValue],
    *,
    start_sequence: int,
    created_at: int,
) -> None:
    add = getattr(session, "add")
    for offset, item in enumerate(items):
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str):
            item_id = f"item_{uuid4().hex}"
            item = {"id": item_id, "type": "item", "value": item}
        add(
            StoredConversationItem(
                id=item_id,
                conversation_id=conversation_id,
                sequence=start_sequence + offset,
                item_json=_dump_json(item),
                created_at=created_at,
            )
        )


def _cursor_page(
    records: Sequence[StoredConversationItem],
    *,
    after: str | None,
    limit: int,
) -> tuple[list[StoredConversationItem], bool]:
    remaining = list(records)
    if after is not None:
        index = next((i for i, record in enumerate(remaining) if record.id == after), None)
        remaining = [] if index is None else remaining[index + 1 :]
    return remaining[:limit], len(remaining) > limit


def _stored_response_data(record: StoredResponse) -> StoredResponseData:
    request = _load_object(record.request_json)
    input_items_value = _load_json(record.input_items_json)
    input_items = input_items_value if isinstance(input_items_value, list) else []
    return StoredResponseData(
        id=record.id,
        api_key_scope=record.api_key_scope,
        upstream_response_id=record.upstream_response_id,
        conversation_id=record.conversation_id,
        status=record.status,
        background=record.background,
        request=request,
        input_items=cast(list[JsonValue], input_items),
        response=_load_object(record.response_json),
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )


def _conversation_data(record: StoredConversation) -> ConversationData:
    metadata_value = _load_object(record.metadata_json)
    metadata = {str(key): str(value) for key, value in metadata_value.items()}
    return ConversationData(
        id=record.id,
        metadata=metadata,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _dump_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _load_json(value: str) -> JsonValue:
    return cast(JsonValue, json.loads(value))


def _load_object(value: str) -> dict[str, JsonValue]:
    parsed = _load_json(value)
    return cast(dict[str, JsonValue], parsed) if isinstance(parsed, dict) else {}


def _rowcount(result: object) -> int:
    value = getattr(result, "rowcount", 0)
    return value if isinstance(value, int) else 0
