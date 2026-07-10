from __future__ import annotations

import json
from typing import cast

import tiktoken

from app.core.types import JsonValue
from app.core.utils.json_guards import is_json_mapping
from app.modules.responses_lifecycle.schemas import InputTokenCountRequest
from app.modules.responses_lifecycle.service import conversation_items_for_execution


class OpaqueTokenCountInputError(ValueError):
    pass


async def count_input_tokens(payload: InputTokenCountRequest, api_key_scope: str) -> int:
    if payload.previous_response_id:
        raise OpaqueTokenCountInputError(
            "Input tokens cannot be counted locally when previous_response_id supplies opaque upstream context."
        )

    data = payload.model_dump(mode="json", exclude_none=True)
    conversation_id = _conversation_id(payload.conversation)
    if conversation_id is not None:
        data["conversation_items"] = await conversation_items_for_execution(conversation_id, api_key_scope)
        data.pop("conversation", None)
    if _contains_opaque_input(data):
        raise OpaqueTokenCountInputError(
            "Input tokens cannot be counted locally for file or image references."
        )

    model = payload.model or "gpt-5"
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")
    countable = {key: value for key, value in data.items() if key not in {"model"}}
    serialized = json.dumps(countable, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return len(encoding.encode(serialized, disallowed_special=()))


def _conversation_id(value: str | dict[str, JsonValue] | None) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if is_json_mapping(value):
        identifier = value.get("id")
        if isinstance(identifier, str):
            stripped = identifier.strip()
            return stripped or None
    return None


def _contains_opaque_input(value: JsonValue) -> bool:
    if isinstance(value, list):
        return any(_contains_opaque_input(item) for item in cast(list[JsonValue], value))
    if not isinstance(value, dict):
        return False
    mapping = cast(dict[str, JsonValue], value)
    item_type = mapping.get("type")
    if item_type in {"input_file", "input_image"}:
        return True
    if "file_id" in mapping or "image_url" in mapping:
        return True
    return any(_contains_opaque_input(child) for child in mapping.values())
