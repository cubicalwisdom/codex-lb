from __future__ import annotations

import base64
import binascii
import hashlib
import io
import ipaddress
import json
import logging
import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Final, cast
from urllib.parse import urlparse

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.requests import ResponsesRequest
from app.core.types import JsonValue
from app.core.utils.json_guards import is_json_list, is_json_mapping
from app.core.utils.sse import format_sse_event, parse_sse_data_json
from app.modules.api_keys.service import ApiKeyData

logger = logging.getLogger(__name__)

CLAUDE_DESKTOP_MODEL_IDS: Final[tuple[str, str]] = (
    "claude-opus-4-8",
    "claude-sonnet-5",
)

_CLAUDE_DESKTOP_OPUS_TARGET: Final = "gpt-5.6-sol"
_CLAUDE_DESKTOP_SONNET_TARGET: Final = "gpt-5.6-terra"
_CLAUDE_DESKTOP_EFFORTS: Final[dict[str, str]] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra": "xhigh",
    "xhigh": "xhigh",
    "max": "max",
}
_SUPPORTED_IMAGE_MEDIA_TYPES: Final[frozenset[str]] = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_SUPPORTED_DOCUMENT_MEDIA_TYPES: Final[frozenset[str]] = frozenset({"application/pdf", "text/plain", "text/csv"})
_SUPPORTED_WEB_SERVER_TOOLS: Final[dict[str, frozenset[str]]] = {
    "web_search": frozenset(
        {
            "web_search_20250305",
            "web_search_20260209",
            "web_search_20260318",
        }
    ),
    "web_fetch": frozenset(
        {
            "web_fetch_20250910",
            "web_fetch_20260209",
            "web_fetch_20260309",
            "web_fetch_20260318",
        }
    ),
}
_WEB_SERVER_TOOL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "type",
        "name",
        "max_uses",
        "allowed_domains",
        "blocked_domains",
        "user_location",
        "allowed_callers",
        "response_inclusion",
        "citations",
        "max_content_tokens",
        "use_cache",
        "cache_control",
        "strict",
        "defer_loading",
    }
)
_WEB_USER_LOCATION_FIELDS: Final[frozenset[str]] = frozenset({"type", "city", "region", "country", "timezone"})
_CLAUDE_TOOL_SEARCH_NAME: Final = "ToolSearch"
_CLAUDE_WORKSPACE_WEB_FETCH_NAME: Final = "mcp__workspace__web_fetch"
_PUBLIC_HTTP_URL_RE: Final = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
_LOCAL_WEB_HOST_SUFFIXES: Final[tuple[str, ...]] = (".localhost", ".local", ".internal")
_MAX_INLINE_ATTACHMENT_BYTES: Final = 10 * 1024 * 1024
_MAX_PDF_PAGES: Final = 500
_MAX_PDF_PAGE_CONTENT_BYTES: Final = 16 * 1024 * 1024
_MAX_EXTRACTED_DOCUMENT_CHARS: Final = 1_000_000
_RESPONSES_IDENTIFIER_MAX_BYTES: Final = 64
_RESPONSES_IDENTIFIER_HASH_HEX_CHARS: Final = 16


def anthropic_error(error_type: str, message: str) -> dict[str, JsonValue]:
    return {"type": "error", "error": {"type": error_type, "message": message}}


def anthropic_error_from_openai(payload: Mapping[str, JsonValue], *, status_code: int) -> dict[str, JsonValue]:
    error_value = payload.get("error")
    error = error_value if is_json_mapping(error_value) else {}
    message = error.get("message")
    code = error.get("code")
    provider_type = error.get("type")
    return anthropic_error(
        _anthropic_error_type(
            code=code if isinstance(code, str) else None,
            provider_type=provider_type if isinstance(provider_type, str) else None,
            status_code=status_code,
        ),
        message if isinstance(message, str) and message else "Request failed",
    )


def anthropic_error_type_for_status(status_code: int, *, code: str | None = None) -> str:
    return _anthropic_error_type(code=code, provider_type=None, status_code=status_code)


def _anthropic_error_type(*, code: str | None, provider_type: str | None, status_code: int) -> str:
    if code == "invalid_api_key" or provider_type == "authentication_error" or status_code == 401:
        return "authentication_error"
    if provider_type == "permission_error" or status_code == 403:
        return "permission_error"
    if status_code == 404:
        return "not_found_error"
    if code == "rate_limit_exceeded" or provider_type == "rate_limit_error" or status_code == 429:
        return "rate_limit_error"
    if status_code == 400 or provider_type == "invalid_request_error":
        return "invalid_request_error"
    if status_code == 529:
        return "overloaded_error"
    return "api_error"


@dataclass(frozen=True, slots=True)
class AnthropicMessagesRequest:
    responses: ResponsesRequest
    client_model: str
    max_output_tokens: int
    context_management_requested: bool
    tool_name_aliases: Mapping[str, str] = field(default_factory=dict)


def to_responses_request(
    payload: Mapping[str, JsonValue],
    *,
    api_key: ApiKeyData | None,
    claude_desktop: bool = False,
    claude_desktop_sonnet_reasoning_effort: str = "high",
) -> AnthropicMessagesRequest:
    client_model = _required_string(payload, "model")
    max_output_tokens = _required_positive_integer(payload, "max_tokens")
    effective_model = _resolve_model(client_model, api_key, claude_desktop=claude_desktop)
    messages = _required_list(payload, "messages")
    tools = payload.get("tools")
    if tools is not None:
        (
            converted_tools,
            hosted_web_aliases,
            tool_names_to_responses,
            tool_name_aliases,
        ) = _tools_to_responses(
            tools,
            claude_desktop=claude_desktop,
            route_workspace_web_fetch=claude_desktop and _latest_user_prompt_targets_public_web(messages),
        )
    else:
        converted_tools = []
        hosted_web_aliases = frozenset()
        tool_names_to_responses = {}
        tool_name_aliases = {}
    tool_search_history = _tool_search_history(
        messages,
        converted_tools=converted_tools,
        hosted_tool_aliases=hosted_web_aliases,
        tool_names_to_responses=tool_names_to_responses,
    )

    input_items: list[JsonValue] = []
    for index, message_value in enumerate(messages):
        message = _required_mapping(message_value, f"messages.{index}")
        input_items.extend(
            _message_to_responses_input(
                message,
                index=index,
                claude_desktop=claude_desktop,
                tool_search_history=tool_search_history,
                tool_names_to_responses=tool_names_to_responses,
            )
        )

    request_data: dict[str, JsonValue] = {
        "model": effective_model,
        "instructions": _system_instructions(payload.get("system")),
        "input": input_items,
        "stream": _optional_bool(payload.get("stream"), "stream") or False,
    }

    if tools is not None:
        request_data["tools"] = converted_tools
    tool_choice, parallel_tool_calls = _tool_choice_to_responses(
        payload.get("tool_choice"),
        hosted_web_aliases=hosted_web_aliases,
        tool_names_to_responses=tool_names_to_responses,
    )
    if tool_choice is not None:
        request_data["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        request_data["parallel_tool_calls"] = parallel_tool_calls
    if claude_desktop:
        request_data["reasoning"] = {
            "effort": _claude_desktop_reasoning_effort(
                payload.get("output_config"),
                default_effort=_claude_desktop_default_reasoning_effort(
                    client_model,
                    sonnet_effort=claude_desktop_sonnet_reasoning_effort,
                ),
            ),
            "summary": "auto",
        }
        request_data["include"] = ["reasoning.encrypted_content"]
    cache_affinity_key = _cache_affinity_key(payload, effective_model=effective_model)
    if cache_affinity_key is not None:
        request_data["prompt_cache_key"] = cache_affinity_key

    return AnthropicMessagesRequest(
        responses=ResponsesRequest.model_validate(request_data),
        client_model=client_model,
        max_output_tokens=max_output_tokens,
        context_management_requested=_context_management_requested(payload.get("context_management")),
        tool_name_aliases=tool_name_aliases,
    )


def to_responses_token_count_request(
    payload: Mapping[str, JsonValue],
    *,
    api_key: ApiKeyData | None,
    claude_desktop: bool = False,
    claude_desktop_sonnet_reasoning_effort: str = "high",
) -> AnthropicMessagesRequest:
    """Normalize a token-count body through the Messages request parser.

    Anthropic's count-tokens request omits ``max_tokens``. The shared parser
    needs it only for Messages validation, so inject a private placeholder
    which is neither forwarded upstream nor included in the token count.
    """

    messages_payload = dict(payload)
    messages_payload["max_tokens"] = 1
    return to_responses_request(
        messages_payload,
        api_key=api_key,
        claude_desktop=claude_desktop,
        claude_desktop_sonnet_reasoning_effort=claude_desktop_sonnet_reasoning_effort,
    )


def message_from_responses(
    response: Mapping[str, JsonValue],
    *,
    client_model: str,
    tool_name_aliases: Mapping[str, str] | None = None,
) -> dict[str, JsonValue]:
    content: list[JsonValue] = []
    saw_tool_use = False
    output = response.get("output")
    if is_json_list(output):
        for item_value in output:
            item = item_value if is_json_mapping(item_value) else None
            if item is None:
                continue
            item_type = item.get("type")
            if item_type == "reasoning":
                reasoning_block = _anthropic_reasoning_block(item)
                if reasoning_block is not None:
                    content.append(reasoning_block)
                continue
            if item_type == "web_search_call":
                content.extend(_anthropic_web_search_blocks(item))
                continue
            if item_type == "function_call":
                content.append(_tool_use_block(item, tool_name_aliases=tool_name_aliases))
                saw_tool_use = True
                continue
            if item_type != "message":
                continue
            item_content = item.get("content")
            if not is_json_list(item_content):
                continue
            for part_value in item_content:
                part = part_value if is_json_mapping(part_value) else None
                if part is None:
                    continue
                text = _response_text(part)
                if text is not None:
                    text_block: dict[str, JsonValue] = {"type": "text", "text": text}
                    citations = _anthropic_text_citations(part)
                    if citations:
                        text_block["citations"] = citations
                    content.append(text_block)

    response_id = response.get("id")
    usage_value = response.get("usage")
    usage = usage_value if is_json_mapping(usage_value) else {}
    return {
        "id": response_id if isinstance(response_id, str) and response_id else "msg_unknown",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": client_model,
        "stop_reason": _stop_reason(response, saw_tool_use=saw_tool_use),
        "stop_sequence": None,
        "usage": _anthropic_usage(usage),
    }


async def iter_messages_events(
    source: AsyncIterator[str | bytes],
    *,
    client_model: str,
    recover_incomplete_stream: bool = False,
    tool_name_aliases: Mapping[str, str] | None = None,
) -> AsyncIterator[str]:
    state = _MessagesStreamState(
        client_model=client_model,
        tool_name_aliases=tool_name_aliases or {},
    )
    async for raw_chunk in source:
        chunk = raw_chunk.decode("utf-8", errors="replace") if isinstance(raw_chunk, bytes) else raw_chunk
        payload = parse_sse_data_json(chunk)
        if payload is None:
            if chunk.lstrip().startswith(":"):
                yield chunk
            continue
        event_type = payload.get("type")
        if not isinstance(event_type, str):
            continue
        if event_type == "response.created":
            for event in state.ensure_started(payload.get("response")):
                yield event
            continue
        if event_type == "response.output_item.added":
            for event in state.handle_output_item_added(payload):
                yield event
            continue
        if event_type == "response.reasoning_summary_part.added":
            for event in state.handle_reasoning_summary_part_added(payload):
                yield event
            continue
        if event_type == "response.reasoning_summary_text.delta":
            for event in state.handle_reasoning_summary_delta(payload):
                yield event
            continue
        if event_type == "response.reasoning_summary_part.done":
            continue
        if event_type == "response.content_part.added":
            for event in state.handle_content_part_added(payload):
                yield event
            continue
        if event_type == "response.output_text.delta":
            for event in state.handle_text_delta(payload):
                yield event
            continue
        if event_type == "response.content_part.done":
            for event in state.handle_content_part_done(payload):
                yield event
            continue
        if event_type == "response.function_call_arguments.delta":
            for event in state.handle_function_arguments_delta(payload):
                yield event
            continue
        if event_type == "response.output_item.done":
            for event in state.handle_output_item_done(payload):
                yield event
            continue
        if event_type in {"response.completed", "response.incomplete"}:
            for event in state.handle_terminal(payload):
                yield event
            return
        if event_type in {"response.failed", "error"}:
            if recover_incomplete_stream and _is_stream_incomplete_event(payload):
                recovered = state.handle_recoverable_incomplete()
                if recovered is not None:
                    for event in recovered:
                        yield event
                    return
            for event in state.handle_error(payload):
                yield event
            return

    if not state.terminal:
        yield format_sse_event(anthropic_error("api_error", "Upstream stream ended before message completion."))


@dataclass(slots=True)
class _ContentBlockState:
    index: int
    kind: str
    output_index: int | None
    item_id: str | None
    call_id: str | None = None
    name: str | None = None
    arguments: str = ""
    reasoning_text: str = ""
    signature: str | None = None
    signature_emitted: bool = False
    started: bool = False
    closed: bool = False
    emitted: bool = False


@dataclass(slots=True)
class _MessagesStreamState:
    client_model: str
    tool_name_aliases: Mapping[str, str] = field(default_factory=dict)
    started: bool = False
    terminal: bool = False
    next_index: int = 0
    blocks: dict[str, _ContentBlockState] = field(default_factory=dict)
    saw_tool_use: bool = False
    current_reasoning_key: str | None = None

    def ensure_started(self, response_value: JsonValue) -> list[str]:
        if self.started:
            return []
        response = response_value if is_json_mapping(response_value) else {}
        response_id = response.get("id")
        self.started = True
        return [
            _anthropic_event(
                "message_start",
                {
                    "message": {
                        "id": response_id if isinstance(response_id, str) and response_id else "msg_unknown",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": self.client_model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    }
                },
            )
        ]

    def handle_output_item_added(self, payload: Mapping[str, JsonValue]) -> list[str]:
        item_value = payload.get("item")
        item = item_value if is_json_mapping(item_value) else None
        if item is None:
            return []
        if item.get("type") == "reasoning":
            block = self._reasoning_block(payload, item)
            block.signature = _optional_string(item.get("encrypted_content"))
            return []
        if item.get("type") != "function_call":
            return []
        block = self._tool_block(payload, item)
        return self._start_tool_block(block)

    def handle_reasoning_summary_part_added(self, payload: Mapping[str, JsonValue]) -> list[str]:
        return self._start_reasoning_block(self._reasoning_block(payload, None))

    def handle_reasoning_summary_delta(self, payload: Mapping[str, JsonValue]) -> list[str]:
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return []
        block = self._reasoning_block(payload, None)
        events = self._start_reasoning_block(block)
        block.reasoning_text += delta
        events.append(
            _anthropic_event(
                "content_block_delta",
                {"index": block.index, "delta": {"type": "thinking_delta", "thinking": delta}},
            )
        )
        return events

    def handle_content_part_added(self, payload: Mapping[str, JsonValue]) -> list[str]:
        part_value = payload.get("part")
        part = part_value if is_json_mapping(part_value) else None
        if part is None or _response_text(part) is None:
            return []
        block = self._text_block(payload)
        return self._start_text_block(block)

    def handle_text_delta(self, payload: Mapping[str, JsonValue]) -> list[str]:
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return []
        block = self._text_block(payload)
        events = self._start_text_block(block)
        if delta:
            block.emitted = True
        events.append(
            _anthropic_event(
                "content_block_delta", {"index": block.index, "delta": {"type": "text_delta", "text": delta}}
            )
        )
        return events

    def handle_content_part_done(self, payload: Mapping[str, JsonValue]) -> list[str]:
        block = self._block_for_text(payload)
        if block is None:
            return []
        events: list[str] = []
        part_value = payload.get("part")
        part = part_value if is_json_mapping(part_value) else None
        if part is not None:
            events.extend(self._citation_events(block, part))
        events.extend(self._stop_block(block))
        return events

    def handle_function_arguments_delta(self, payload: Mapping[str, JsonValue]) -> list[str]:
        delta = payload.get("delta")
        if not isinstance(delta, str):
            return []
        block = self._tool_block(payload, None)
        block.arguments += delta
        events = self._start_tool_block(block)
        events.append(
            _anthropic_event(
                "content_block_delta",
                {"index": block.index, "delta": {"type": "input_json_delta", "partial_json": delta}},
            )
        )
        return events

    def handle_output_item_done(self, payload: Mapping[str, JsonValue]) -> list[str]:
        item_value = payload.get("item")
        item = item_value if is_json_mapping(item_value) else None
        if item is None:
            return []
        if item.get("type") == "reasoning":
            block = self._reasoning_block(payload, item)
            final_signature = _optional_string(item.get("encrypted_content"))
            if final_signature is not None:
                block.signature = final_signature
            events: list[str] = []
            summary_text = _reasoning_summary_text(item)
            if summary_text and not block.reasoning_text:
                events.extend(self._start_reasoning_block(block))
                block.reasoning_text = summary_text
                events.append(
                    _anthropic_event(
                        "content_block_delta",
                        {
                            "index": block.index,
                            "delta": {"type": "thinking_delta", "thinking": summary_text},
                        },
                    )
                )
            events.extend(self._finish_reasoning_block(block))
            self.current_reasoning_key = None
            return events
        if item.get("type") == "web_search_call":
            blocks = _anthropic_web_search_blocks(item)
            events: list[str] = []
            for content_block in blocks:
                events.extend(self._complete_content_block(content_block))
            return events
        if item.get("type") == "function_call":
            block = self._tool_block(payload, item)
            events = self._start_tool_block(block)
            arguments = item.get("arguments")
            if isinstance(arguments, str) and not block.arguments:
                block.arguments = arguments
                if arguments:
                    events.append(
                        _anthropic_event(
                            "content_block_delta",
                            {"index": block.index, "delta": {"type": "input_json_delta", "partial_json": arguments}},
                        )
                    )
            events.extend(self._stop_block(block))
            return events
        if item.get("type") != "message":
            return []
        events: list[str] = []
        output_index = _integer_or_none(payload.get("output_index"))
        if any(block.kind == "text" and block.output_index == output_index for block in self.blocks.values()):
            return events
        content_value = item.get("content")
        if not is_json_list(content_value):
            return events
        item_id = _optional_string(item.get("id"))
        for content_index, part_value in enumerate(content_value):
            part = part_value if is_json_mapping(part_value) else None
            if part is None:
                continue
            text = _response_text(part)
            if text is None:
                continue
            fallback_payload = dict(payload)
            fallback_payload["content_index"] = content_index
            if item_id is not None:
                fallback_payload["item_id"] = item_id
            block = self._text_block(fallback_payload)
            if block.closed:
                continue
            events.extend(self._start_text_block(block))
            if text:
                block.emitted = True
            events.append(
                _anthropic_event(
                    "content_block_delta", {"index": block.index, "delta": {"type": "text_delta", "text": text}}
                )
            )
            events.extend(self._citation_events(block, part))
            events.extend(self._stop_block(block))
        return events

    def handle_terminal(self, payload: Mapping[str, JsonValue]) -> list[str]:
        response_value = payload.get("response")
        response = response_value if is_json_mapping(response_value) else {}
        events = self.ensure_started(response)
        for block in self.blocks.values():
            if block.kind == "thinking":
                events.extend(self._finish_reasoning_block(block))
            else:
                events.extend(self._stop_block(block))
        usage_value = response.get("usage")
        usage = usage_value if is_json_mapping(usage_value) else {}
        events.append(
            _anthropic_event(
                "message_delta",
                {
                    "delta": {
                        "stop_reason": _stop_reason(response, saw_tool_use=self.saw_tool_use),
                        "stop_sequence": None,
                    },
                    "usage": {"output_tokens": _integer(usage.get("output_tokens"))},
                },
            )
        )
        events.append(_anthropic_event("message_stop", {}))
        self.terminal = True
        return events

    def handle_error(self, payload: Mapping[str, JsonValue]) -> list[str]:
        error_payload: Mapping[str, JsonValue]
        if payload.get("type") == "response.failed":
            response_value = payload.get("response")
            response = response_value if is_json_mapping(response_value) else {}
            error_value = response.get("error")
            error_payload = {"error": error_value} if is_json_mapping(error_value) else {}
        else:
            error_payload = payload
        self.terminal = True
        return [format_sse_event(anthropic_error_from_openai(error_payload, status_code=502))]

    def handle_recoverable_incomplete(self) -> list[str] | None:
        """Close a Desktop text stream after its upstream terminal frame is lost.

        A retry after text is delivered would duplicate that text. This narrow
        recovery therefore applies only to a non-empty, text-only stream.
        Tool-use and empty streams remain explicit errors.
        """

        has_emitted_text = any(block.kind == "text" and block.emitted for block in self.blocks.values())
        if self.saw_tool_use or not has_emitted_text:
            return None
        events: list[str] = []
        for block in self.blocks.values():
            events.extend(self._stop_block(block))
        events.append(
            _anthropic_event(
                "message_delta",
                {
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 0},
                },
            )
        )
        events.append(_anthropic_event("message_stop", {}))
        self.terminal = True
        return events

    def _text_block(self, payload: Mapping[str, JsonValue]) -> _ContentBlockState:
        output_index = _integer_or_none(payload.get("output_index"))
        content_index = _integer_or_none(payload.get("content_index"))
        item_id = _optional_string(payload.get("item_id"))
        key = f"text:{output_index}:{content_index}:{item_id}"
        block = self.blocks.get(key)
        if block is None:
            block = self._new_block("text", key=key, output_index=output_index, item_id=item_id)
        return block

    def _reasoning_block(
        self,
        payload: Mapping[str, JsonValue],
        item: Mapping[str, JsonValue] | None,
    ) -> _ContentBlockState:
        output_index = _integer_or_none(payload.get("output_index"))
        item_id = _optional_string(payload.get("item_id"))
        if item is not None:
            item_id = _optional_string(item.get("id")) or item_id
        if item_id is None and self.current_reasoning_key is not None:
            current = self.blocks.get(self.current_reasoning_key)
            if current is not None:
                return current
        key = f"thinking:{output_index}:{item_id}"
        block = self.blocks.get(key)
        if block is None:
            block = self._new_block("thinking", key=key, output_index=output_index, item_id=item_id)
        self.current_reasoning_key = key
        return block

    def _block_for_text(self, payload: Mapping[str, JsonValue]) -> _ContentBlockState | None:
        output_index = _integer_or_none(payload.get("output_index"))
        content_index = _integer_or_none(payload.get("content_index"))
        item_id = _optional_string(payload.get("item_id"))
        return self.blocks.get(f"text:{output_index}:{content_index}:{item_id}")

    def _tool_block(
        self,
        payload: Mapping[str, JsonValue],
        item: Mapping[str, JsonValue] | None,
    ) -> _ContentBlockState:
        output_index = _integer_or_none(payload.get("output_index"))
        item_id = _optional_string(payload.get("item_id"))
        if item is not None:
            item_id = _optional_string(item.get("id")) or item_id
        call_id = _optional_string(item.get("call_id")) if item is not None else None
        name = _optional_string(item.get("name")) if item is not None else None
        key = f"tool:{output_index}:{item_id}"
        block = self.blocks.get(key)
        if block is None:
            block = self._new_block(
                "tool_use",
                key=key,
                output_index=output_index,
                item_id=item_id,
                call_id=call_id,
                name=name,
            )
        else:
            block.call_id = call_id or block.call_id
            block.name = name or block.name
        return block

    def _new_block(
        self,
        kind: str,
        *,
        key: str,
        output_index: int | None,
        item_id: str | None,
        call_id: str | None = None,
        name: str | None = None,
    ) -> _ContentBlockState:
        block = _ContentBlockState(
            index=self.next_index,
            kind=kind,
            output_index=output_index,
            item_id=item_id,
            call_id=call_id,
            name=name,
        )
        self.blocks[key] = block
        self.next_index += 1
        return block

    def _start_text_block(self, block: _ContentBlockState) -> list[str]:
        if block.started:
            return []
        block.started = True
        return self.ensure_started(None) + [
            _anthropic_event(
                "content_block_start", {"index": block.index, "content_block": {"type": "text", "text": ""}}
            )
        ]

    def _start_reasoning_block(self, block: _ContentBlockState) -> list[str]:
        if block.started:
            return []
        block.started = True
        return self.ensure_started(None) + [
            _anthropic_event(
                "content_block_start",
                {"index": block.index, "content_block": {"type": "thinking", "thinking": ""}},
            )
        ]

    def _finish_reasoning_block(self, block: _ContentBlockState) -> list[str]:
        if block.closed:
            return []
        if not block.started and block.signature is None and not block.reasoning_text:
            return []
        events = self._start_reasoning_block(block)
        if block.signature is not None and not block.signature_emitted:
            block.signature_emitted = True
            events.append(
                _anthropic_event(
                    "content_block_delta",
                    {
                        "index": block.index,
                        "delta": {"type": "signature_delta", "signature": block.signature},
                    },
                )
            )
        events.extend(self._stop_block(block))
        _log_reasoning_translation(
            direction="response_stream",
            outcome="emitted",
            summary_chars=len(block.reasoning_text),
            signature_chars=len(block.signature or ""),
        )
        return events

    def _start_tool_block(self, block: _ContentBlockState) -> list[str]:
        if block.started:
            return []
        block.started = True
        self.saw_tool_use = True
        call_id = block.call_id or block.item_id or f"toolu_{block.index}"
        upstream_name = block.name or "unknown_tool"
        name = self.tool_name_aliases.get(upstream_name, upstream_name)
        return self.ensure_started(None) + [
            _anthropic_event(
                "content_block_start",
                {"index": block.index, "content_block": {"type": "tool_use", "id": call_id, "name": name, "input": {}}},
            )
        ]

    def _complete_content_block(self, content_block: Mapping[str, JsonValue]) -> list[str]:
        index = self.next_index
        self.next_index += 1
        return self.ensure_started(None) + [
            _anthropic_event(
                "content_block_start",
                {"index": index, "content_block": dict(content_block)},
            ),
            _anthropic_event("content_block_stop", {"index": index}),
        ]

    def _citation_events(
        self,
        block: _ContentBlockState,
        part: Mapping[str, JsonValue],
    ) -> list[str]:
        if block.closed:
            return []
        return [
            _anthropic_event(
                "content_block_delta",
                {
                    "index": block.index,
                    "delta": {"type": "citations_delta", "citation": citation},
                },
            )
            for citation in _anthropic_text_citations(part)
        ]

    def _stop_block(self, block: _ContentBlockState) -> list[str]:
        if block.closed or not block.started:
            return []
        block.closed = True
        return [_anthropic_event("content_block_stop", {"index": block.index})]


def _anthropic_event(event_type: str, values: Mapping[str, JsonValue]) -> str:
    return format_sse_event({"type": event_type, **values})


def _anthropic_web_search_blocks(item: Mapping[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Return server-tool blocks only for a complete, lossless result shape.

    Public Responses web-search items expose lifecycle/action data but not the
    opaque fields Claude requires for replay. Private upstreams may preserve
    those fields; this adapter passes them through only when every result is
    complete and otherwise retains the existing final-text fallback.
    """

    if item.get("status") != "completed":
        return []
    item_id = _optional_string(item.get("id"))
    action_value = item.get("action")
    action = action_value if is_json_mapping(action_value) else None
    if item_id is None or not item_id.startswith("srvtoolu_") or action is None or action.get("type") != "search":
        return []
    query = _optional_string(action.get("query"))
    if query is None:
        queries_value = action.get("queries")
        if is_json_list(queries_value) and len(queries_value) == 1:
            query = _optional_string(queries_value[0])
    if query is None:
        return []
    results_value = item.get("results")
    if not is_json_list(results_value) or not results_value:
        return []
    results: list[JsonValue] = []
    for result_value in results_value:
        result = result_value if is_json_mapping(result_value) else None
        if result is None:
            return []
        result_type = result.get("type")
        if result_type is not None and result_type != "web_search_result":
            return []
        url = _optional_string(result.get("url"))
        title = _optional_string(result.get("title"))
        encrypted_content = _optional_string(result.get("encrypted_content"))
        if url is None or title is None or encrypted_content is None:
            return []
        translated: dict[str, JsonValue] = {
            "type": "web_search_result",
            "url": url,
            "title": title,
            "encrypted_content": encrypted_content,
        }
        page_age = _optional_string(result.get("page_age"))
        if page_age is not None:
            translated["page_age"] = page_age
        results.append(translated)
    return [
        {
            "type": "server_tool_use",
            "id": item_id,
            "name": "web_search",
            "input": {"query": query},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": item_id,
            "content": results,
        },
    ]


def _anthropic_text_citations(part: Mapping[str, JsonValue]) -> list[JsonValue]:
    annotations_value = part.get("annotations")
    if not is_json_list(annotations_value):
        return []
    citations: list[JsonValue] = []
    for annotation_value in annotations_value:
        annotation = annotation_value if is_json_mapping(annotation_value) else None
        if annotation is None or annotation.get("type") not in {
            "url_citation",
            "web_search_result_location",
        }:
            continue
        url = _optional_string(annotation.get("url"))
        title = _optional_string(annotation.get("title"))
        encrypted_index = _optional_string(annotation.get("encrypted_index"))
        cited_text = _optional_string(annotation.get("cited_text"))
        if url is None or title is None or encrypted_index is None or cited_text is None:
            continue
        citations.append(
            {
                "type": "web_search_result_location",
                "url": url,
                "title": title,
                "encrypted_index": encrypted_index,
                "cited_text": cited_text,
            }
        )
    return citations


def _is_stream_incomplete_event(payload: Mapping[str, JsonValue]) -> bool:
    if payload.get("type") == "response.failed":
        response_value = payload.get("response")
        response = response_value if is_json_mapping(response_value) else {}
        error_value = response.get("error")
        error = error_value if is_json_mapping(error_value) else {}
    else:
        error_value = payload.get("error")
        error = error_value if is_json_mapping(error_value) else {}
    return error.get("code") == "stream_incomplete"


def _required_string(payload: Mapping[str, JsonValue], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ClientPayloadError(f"'{field}' must be a non-empty string.", param=field)
    return value.strip()


def _required_positive_integer(payload: Mapping[str, JsonValue], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ClientPayloadError(f"'{field}' must be a positive integer.", param=field)
    return value


def _required_list(payload: Mapping[str, JsonValue], field: str) -> list[JsonValue]:
    value = payload.get(field)
    if not is_json_list(value):
        raise ClientPayloadError(f"'{field}' must be an array.", param=field)
    return value


def _required_mapping(value: JsonValue, param: str) -> Mapping[str, JsonValue]:
    if not is_json_mapping(value):
        raise ClientPayloadError(f"'{param}' must be an object.", param=param)
    return value


def _optional_bool(value: JsonValue, param: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ClientPayloadError(f"'{param}' must be a boolean.", param=param)
    return value


def _resolve_model(client_model: str, api_key: ApiKeyData | None, *, claude_desktop: bool) -> str:
    if claude_desktop:
        desktop_target = _claude_desktop_model_target(client_model)
        if desktop_target is not None:
            return desktop_target

    if not client_model.lower().startswith("claude"):
        return client_model
    if api_key is not None and api_key.enforced_model:
        return api_key.enforced_model
    raise ClientPayloadError(
        "Claude model identifiers require a codex-lb API key with an enforced model. "
        "Otherwise configure Claude Code to send a codex-lb model identifier.",
        param="model",
    )


def _claude_desktop_model_target(client_model: str) -> str | None:
    normalized = client_model.strip().lower()
    if normalized == "opus" or normalized.startswith("claude-opus-"):
        return _CLAUDE_DESKTOP_OPUS_TARGET
    if _is_claude_sonnet_model(normalized):
        return _CLAUDE_DESKTOP_SONNET_TARGET
    return None


def _is_claude_sonnet_model(model: str) -> bool:
    return model == "sonnet" or model.startswith("claude-sonnet-")


def _claude_desktop_default_reasoning_effort(client_model: str, *, sonnet_effort: str) -> str:
    if not _is_claude_sonnet_model(client_model.strip().lower()):
        return "high"
    normalized = sonnet_effort.strip().lower()
    return _CLAUDE_DESKTOP_EFFORTS.get(normalized, "high")


def _claude_desktop_reasoning_effort(output_config: JsonValue, *, default_effort: str) -> str:
    if output_config is None:
        return default_effort
    config = _required_mapping(output_config, "output_config")
    effort_value = config.get("effort")
    if effort_value is None:
        return default_effort
    if not isinstance(effort_value, str) or not effort_value.strip():
        raise ClientPayloadError("'output_config.effort' must be a non-empty string.", param="output_config.effort")
    normalized = effort_value.strip().lower()
    mapped = _CLAUDE_DESKTOP_EFFORTS.get(normalized)
    if mapped is None:
        raise ClientPayloadError(
            "Unsupported Claude Desktop effort. Use low, medium, high, xhigh, or max.",
            param="output_config.effort",
        )
    return mapped


def _system_instructions(value: JsonValue) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not is_json_list(value):
        raise ClientPayloadError("'system' must be a string or an array of text blocks.", param="system")
    text_parts: list[str] = []
    for index, part_value in enumerate(value):
        part = _required_mapping(part_value, f"system.{index}")
        if part.get("type") != "text":
            raise ClientPayloadError("Only text system blocks are supported.", param=f"system.{index}")
        text = part.get("text")
        if not isinstance(text, str):
            raise ClientPayloadError("System text blocks require 'text'.", param=f"system.{index}.text")
        text_parts.append(text)
    return "\n".join(text_parts)


def _context_management_requested(value: JsonValue) -> bool:
    """Validate Anthropic's opt-in context controls without pretending to be Anthropic.

    The facade uses the presence of requested edits as permission to compact a
    near-limit transcript through the upstream Responses compact contract.
    Individual edit types are provider-versioned, so they remain opaque after
    this shape validation instead of being silently rewritten.
    """

    if value is None:
        return False
    management = _required_mapping(value, "context_management")
    edits = management.get("edits")
    if not is_json_list(edits):
        raise ClientPayloadError("context_management.edits must be an array.", param="context_management.edits")
    for index, edit_value in enumerate(edits):
        edit = _required_mapping(edit_value, f"context_management.edits.{index}")
        _required_string(edit, "type")
    return bool(edits)


def _cache_affinity_key(payload: Mapping[str, JsonValue], *, effective_model: str) -> str | None:
    """Return a stable upstream cache key for an Anthropic-marked static prefix.

    Anthropic cache controls identify a prefix, whereas Responses uses an
    affinity key.  The key deliberately contains only data through the last
    marked boundary, so changing the current user turn does not move the
    request away from the same upstream cache affinity bucket.
    """

    top_level_cache = payload.get("cache_control")
    if top_level_cache is not None:
        _validate_cache_control(top_level_cache, param="cache_control")
        prefix: dict[str, JsonValue] = {
            "model": effective_model,
            "system": _without_cache_control(payload.get("system")),
            "tools": _without_cache_control(payload.get("tools")),
            "messages": _without_cache_control(payload.get("messages")),
        }
        return _cache_key_for_prefix(prefix)

    system_prefix = _cached_system_prefix(payload.get("system"))
    tools_prefix = _cached_tools_prefix(payload.get("tools"))
    messages_prefix = _cached_messages_prefix(payload.get("messages"))
    if system_prefix is None and tools_prefix is None and messages_prefix is None:
        return None

    prefix: dict[str, JsonValue] = {"model": effective_model}
    if messages_prefix is not None:
        # System and tools precede every Messages turn and therefore form part
        # of the actual cached prefix when the latest marker is in messages.
        prefix["system"] = _without_cache_control(payload.get("system"))
        prefix["tools"] = _without_cache_control(payload.get("tools"))
        prefix["messages"] = messages_prefix
    elif tools_prefix is not None:
        prefix["system"] = _without_cache_control(payload.get("system"))
        prefix["tools"] = tools_prefix
    else:
        prefix["system"] = system_prefix
    return _cache_key_for_prefix(prefix)


def _cached_system_prefix(value: JsonValue) -> JsonValue | None:
    if not is_json_list(value):
        return None
    prefix: list[JsonValue] = []
    found = False
    for index, block_value in enumerate(value):
        block = _required_mapping(block_value, f"system.{index}")
        prefix.append(_without_cache_control(block))
        control = block.get("cache_control")
        if control is not None:
            _validate_cache_control(control, param=f"system.{index}.cache_control")
            found = True
    return prefix if found else None


def _cached_tools_prefix(value: JsonValue) -> JsonValue | None:
    if not is_json_list(value):
        return None
    prefix: list[JsonValue] = []
    found = False
    for index, tool_value in enumerate(value):
        tool = _required_mapping(tool_value, f"tools.{index}")
        prefix.append(_without_cache_control(tool))
        control = tool.get("cache_control")
        if control is not None:
            _validate_cache_control(control, param=f"tools.{index}.cache_control")
            found = True
    return prefix if found else None


def _cached_messages_prefix(value: JsonValue) -> JsonValue | None:
    if not is_json_list(value):
        return None
    prefix: list[JsonValue] = []
    last_marked_prefix: list[JsonValue] | None = None
    for message_index, message_value in enumerate(value):
        message = _required_mapping(message_value, f"messages.{message_index}")
        content_value = message.get("content")
        if isinstance(content_value, str):
            prefix.append(_without_cache_control(message))
            continue
        content = _content_blocks(content_value, param=f"messages.{message_index}.content")
        cached_content: list[JsonValue] = []
        latest_marked_content_index: int | None = None
        for content_index, block_value in enumerate(content):
            block = _required_mapping(block_value, f"messages.{message_index}.content.{content_index}")
            cached_content.append(_without_cache_control(block))
            control = block.get("cache_control")
            if control is not None:
                _validate_cache_control(
                    control,
                    param=f"messages.{message_index}.content.{content_index}.cache_control",
                )
                latest_marked_content_index = content_index
        if latest_marked_content_index is None:
            prefix.append(_without_cache_control(message))
            continue
        truncated_message = _without_cache_control(message)
        if is_json_mapping(truncated_message):
            updated = dict(truncated_message)
            updated["content"] = cached_content[: latest_marked_content_index + 1]
            last_marked_prefix = [*prefix, updated]
        else:  # pragma: no cover - _without_cache_control preserves mappings
            last_marked_prefix = [*prefix, truncated_message]
        prefix.append(_without_cache_control(message))
    return last_marked_prefix


def _validate_cache_control(value: JsonValue, *, param: str) -> None:
    control = _required_mapping(value, param)
    control_type = _required_string(control, "type")
    if control_type not in {"ephemeral", "auto"}:
        raise ClientPayloadError("cache_control.type must be 'ephemeral' or 'auto'.", param=f"{param}.type")


def _without_cache_control(value: JsonValue) -> JsonValue:
    if is_json_mapping(value):
        return {key: _without_cache_control(item) for key, item in value.items() if key != "cache_control"}
    if is_json_list(value):
        return [_without_cache_control(item) for item in value]
    return value


def _cache_key_for_prefix(prefix: Mapping[str, JsonValue]) -> str:
    canonical = json.dumps(prefix, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"anthropic-cache-{digest[:32]}"


def _responses_identifier(value: str, *, kind: str) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= _RESPONSES_IDENTIFIER_MAX_BYTES:
        return value

    suffix = f"_{hashlib.sha256(encoded).hexdigest()[:_RESPONSES_IDENTIFIER_HASH_HEX_CHARS]}"
    prefix_bytes = encoded[: _RESPONSES_IDENTIFIER_MAX_BYTES - len(suffix)]
    while True:
        try:
            prefix = prefix_bytes.decode("utf-8")
            break
        except UnicodeDecodeError:
            prefix_bytes = prefix_bytes[:-1]
    mapped = f"{prefix}{suffix}"
    logger.info(
        "anthropic_protocol_identifier_mapped kind=%s original_bytes=%d mapped_bytes=%d",
        kind,
        len(encoded),
        len(mapped.encode("utf-8")),
    )
    return mapped


def _message_to_responses_input(
    message: Mapping[str, JsonValue],
    *,
    index: int,
    claude_desktop: bool,
    tool_search_history: Mapping[str, list[JsonValue] | None],
    tool_names_to_responses: Mapping[str, str],
) -> list[JsonValue]:
    role = _required_string(message, "role")
    if role not in {"user", "assistant", "system", "developer"}:
        raise ClientPayloadError("Messages role must be 'user' or 'assistant'.", param=f"messages.{index}.role")
    content = _content_blocks(message.get("content"), param=f"messages.{index}.content")
    if role in {"system", "developer"}:
        if not claude_desktop:
            raise ClientPayloadError("Messages role must be 'user' or 'assistant'.", param=f"messages.{index}.role")
        return _desktop_instruction_input(content, index=index, role=role)
    if role == "assistant":
        return _assistant_input(
            content,
            index=index,
            tool_search_history=tool_search_history,
            tool_names_to_responses=tool_names_to_responses,
        )
    return _user_content(content, index=index, tool_search_history=tool_search_history)


def _desktop_instruction_input(content: list[JsonValue], *, index: int, role: str) -> list[JsonValue]:
    converted: list[JsonValue] = []
    for content_index, block_value in enumerate(content):
        block = _required_mapping(block_value, f"messages.{index}.content.{content_index}")
        if block.get("type") != "text":
            raise ClientPayloadError(
                f"{role.title()} messages only support text content.",
                param=f"messages.{index}.content.{content_index}.type",
            )
        text = block.get("text")
        if not isinstance(text, str):
            raise ClientPayloadError(
                "Text blocks require 'text'.", param=f"messages.{index}.content.{content_index}.text"
            )
        converted.append({"type": "input_text", "text": text})
    return [{"role": role, "content": converted}]


def _content_blocks(value: JsonValue, *, param: str) -> list[JsonValue]:
    if isinstance(value, str):
        return [{"type": "text", "text": value}]
    if not is_json_list(value):
        raise ClientPayloadError("Message content must be a string or array of blocks.", param=param)
    return value


def _assistant_input(
    content: list[JsonValue],
    *,
    index: int,
    tool_search_history: Mapping[str, list[JsonValue] | None],
    tool_names_to_responses: Mapping[str, str],
) -> list[JsonValue]:
    converted: list[JsonValue] = []
    pending_text: list[JsonValue] = []

    def flush_text() -> None:
        if pending_text:
            converted.append({"role": "assistant", "content": list(pending_text)})
            pending_text.clear()

    for content_index, block_value in enumerate(content):
        block = _required_mapping(block_value, f"messages.{index}.content.{content_index}")
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if not isinstance(text, str):
                raise ClientPayloadError(
                    "Text blocks require 'text'.", param=f"messages.{index}.content.{content_index}.text"
                )
            pending_text.append({"type": "output_text", "text": text})
            continue
        if block_type == "thinking":
            flush_text()
            thinking = block.get("thinking")
            signature = block.get("signature")
            if not isinstance(thinking, str):
                raise ClientPayloadError(
                    "Assistant thinking blocks require string 'thinking'.",
                    param=f"messages.{index}.content.{content_index}.thinking",
                )
            if not isinstance(signature, str) or not signature:
                raise ClientPayloadError(
                    "Assistant thinking blocks require non-empty string 'signature'.",
                    param=f"messages.{index}.content.{content_index}.signature",
                )
            converted.append(
                {
                    "type": "reasoning",
                    "encrypted_content": signature,
                    "summary": [],
                    "content": None,
                }
            )
            _log_reasoning_translation(
                direction="request",
                outcome="replayed",
                summary_chars=len(thinking),
                signature_chars=len(signature),
            )
            continue
        if block_type == "tool_use":
            flush_text()
            tool_id = _required_string(block, "id")
            responses_tool_id = _responses_identifier(tool_id, kind="call_id")
            name = _required_string(block, "name")
            responses_name = tool_names_to_responses.get(name) or _responses_identifier(name, kind="tool_name")
            tool_input = block.get("input")
            if not is_json_mapping(tool_input):
                raise ClientPayloadError(
                    "tool_use blocks require object 'input'.", param=f"messages.{index}.content.{content_index}.input"
                )
            if tool_id in tool_search_history:
                if tool_search_history[tool_id] is None:
                    continue
                converted.append(
                    {
                        "type": "tool_search_call",
                        "call_id": responses_tool_id,
                        "arguments": dict(tool_input),
                        "execution": "client",
                        "status": "completed",
                    }
                )
            else:
                converted.append(
                    {
                        "type": "function_call",
                        "call_id": responses_tool_id,
                        "name": responses_name,
                        "arguments": json.dumps(tool_input, ensure_ascii=False, separators=(",", ":")),
                    }
                )
            continue
        raise ClientPayloadError(
            f"Unsupported assistant content block type '{block_type}'.",
            param=f"messages.{index}.content.{content_index}.type",
        )
    flush_text()
    return converted


def _user_content(
    content: list[JsonValue],
    *,
    index: int,
    tool_search_history: Mapping[str, list[JsonValue] | None],
) -> list[JsonValue]:
    converted: list[JsonValue] = []
    pending_text: list[JsonValue] = []

    def flush_text() -> None:
        if pending_text:
            converted.append({"role": "user", "content": list(pending_text)})
            pending_text.clear()

    for content_index, block_value in enumerate(content):
        block = _required_mapping(block_value, f"messages.{index}.content.{content_index}")
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if not isinstance(text, str):
                raise ClientPayloadError(
                    "Text blocks require 'text'.", param=f"messages.{index}.content.{content_index}.text"
                )
            pending_text.append({"type": "input_text", "text": text})
            continue
        if block_type == "tool_result":
            flush_text()
            tool_use_id = _required_string(block, "tool_use_id")
            responses_tool_use_id = _responses_identifier(tool_use_id, kind="call_id")
            if tool_use_id in tool_search_history:
                selected_tools = tool_search_history[tool_use_id]
                if selected_tools is None:
                    continue
                is_error = _optional_bool(
                    block.get("is_error"),
                    f"messages.{index}.content.{content_index}.is_error",
                )
                converted.append(
                    {
                        "type": "tool_search_output",
                        "call_id": responses_tool_use_id,
                        "tools": selected_tools,
                        "execution": "client",
                        "status": "incomplete" if is_error else "completed",
                    }
                )
            else:
                converted.append(
                    {
                        "type": "function_call_output",
                        "call_id": responses_tool_use_id,
                        "output": _tool_result_output(
                            block.get("content"),
                            param=f"messages.{index}.content.{content_index}.content",
                        ),
                    }
                )
            continue
        if block_type == "image":
            pending_text.append(_image_input(block, param=f"messages.{index}.content.{content_index}"))
            continue
        if block_type == "document":
            pending_text.append(_document_input(block, param=f"messages.{index}.content.{content_index}"))
            continue
        raise ClientPayloadError(
            f"Unsupported user content block type '{block_type}'.",
            param=f"messages.{index}.content.{content_index}.type",
        )
    flush_text()
    return converted


def _image_input(block: Mapping[str, JsonValue], *, param: str) -> dict[str, JsonValue]:
    source = _required_mapping(block.get("source"), f"{param}.source")
    source_type = _required_string(source, "type")
    if source_type == "base64":
        media_type = _attachment_media_type(
            source,
            allowed=_SUPPORTED_IMAGE_MEDIA_TYPES,
            param=f"{param}.source.media_type",
        )
        data = _validated_base64_attachment(source, param=f"{param}.source.data")
        return {"type": "input_image", "image_url": f"data:{media_type};base64,{data}"}
    if source_type == "url":
        url = _safe_attachment_url(source.get("url"), param=f"{param}.source.url")
        return {"type": "input_image", "image_url": url}
    raise ClientPayloadError(
        "Image source type must be 'base64' or 'url'.",
        param=f"{param}.source.type",
    )


def _document_input(block: Mapping[str, JsonValue], *, param: str) -> dict[str, JsonValue]:
    source = _required_mapping(block.get("source"), f"{param}.source")
    source_type = _required_string(source, "type")
    if source_type == "base64":
        media_type = _attachment_media_type(
            source,
            allowed=_SUPPORTED_DOCUMENT_MEDIA_TYPES,
            param=f"{param}.source.media_type",
        )
        filename = _document_filename(
            block.get("title"),
            media_type=media_type,
            param=f"{param}.title",
        )
        data = _decoded_base64_attachment(source, param=f"{param}.source.data")
        extracted = _extract_document_text(
            data,
            media_type=media_type,
            param=f"{param}.source.data",
        )
        return {
            "type": "input_text",
            "text": f"[Document: {filename}; media_type={media_type}]\n{extracted}\n[End document: {filename}]",
        }
    if source_type == "url":
        _safe_attachment_url(source.get("url"), param=f"{param}.source.url")
        raise ClientPayloadError(
            "Document URL sources are not supported by this transport; provide a base64 document.",
            param=f"{param}.source.type",
        )
    raise ClientPayloadError(
        "Document source type must be 'base64' or 'url'.",
        param=f"{param}.source.type",
    )


def _attachment_media_type(
    source: Mapping[str, JsonValue],
    *,
    allowed: frozenset[str],
    param: str,
) -> str:
    value = source.get("media_type")
    if not isinstance(value, str) or value.lower() not in allowed:
        supported = ", ".join(sorted(allowed))
        raise ClientPayloadError(f"Unsupported attachment media type. Supported types: {supported}.", param=param)
    return value.lower()


def _validated_base64_attachment(source: Mapping[str, JsonValue], *, param: str) -> str:
    _decoded_base64_attachment(source, param=param)
    data = source.get("data")
    assert isinstance(data, str)
    return data


def _decoded_base64_attachment(source: Mapping[str, JsonValue], *, param: str) -> bytes:
    data = source.get("data")
    if not isinstance(data, str) or not data:
        raise ClientPayloadError("Attachment source requires non-empty base64 'data'.", param=param)
    try:
        decoded = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ClientPayloadError("Attachment data must be valid base64.", param=param) from exc
    if not decoded:
        raise ClientPayloadError("Attachment data must not be empty.", param=param)
    if len(decoded) > _MAX_INLINE_ATTACHMENT_BYTES:
        raise ClientPayloadError(
            f"Inline attachments must not exceed {_MAX_INLINE_ATTACHMENT_BYTES // (1024 * 1024)} MiB.",
            param=param,
        )
    return decoded


def _extract_document_text(data: bytes, *, media_type: str, param: str) -> str:
    if media_type in {"text/plain", "text/csv"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ClientPayloadError(
                "Plain-text and CSV documents must use UTF-8 encoding.",
                param=param,
            ) from exc
        return _bounded_document_text(text, param=param)
    if media_type != "application/pdf":
        raise ClientPayloadError("Unsupported document media type.", param=param)
    return _extract_pdf_text(data, param=param)


def _extract_pdf_text(data: bytes, *, param: str) -> str:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ClientPayloadError(
                "Encrypted PDF documents are not supported.",
                param=param,
            )
        page_count = len(reader.pages)
        if page_count > _MAX_PDF_PAGES:
            raise ClientPayloadError(
                f"PDF documents may contain at most {_MAX_PDF_PAGES} pages.",
                param=param,
            )
        page_text: list[str] = []
        extracted_any = False
        extracted_chars = 0
        for page_number, page in enumerate(reader.pages, start=1):
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > _MAX_PDF_PAGE_CONTENT_BYTES:
                raise ClientPayloadError(
                    f"PDF page {page_number} exceeds the safe content-stream limit.",
                    param=param,
                )
            text = page.extract_text() or ""
            stripped = text.strip()
            if stripped:
                extracted_any = True
                extracted_chars += len(stripped)
                if extracted_chars > _MAX_EXTRACTED_DOCUMENT_CHARS:
                    raise ClientPayloadError(
                        f"Extracted document text must not exceed {_MAX_EXTRACTED_DOCUMENT_CHARS} characters.",
                        param=param,
                    )
                page_text.append(f"[Page {page_number}]\n{stripped}")
            else:
                page_text.append(f"[Page {page_number}]\n[No extractable text]")
    except ClientPayloadError:
        raise
    except (PdfReadError, OSError, TypeError, ValueError) as exc:
        raise ClientPayloadError("PDF document could not be read safely.", param=param) from exc
    if not extracted_any:
        raise ClientPayloadError(
            "PDF document contains no extractable text; scanned or image-only PDFs require OCR before upload.",
            param=param,
        )
    return "\n\n".join(page_text)


def _bounded_document_text(text: str, *, param: str) -> str:
    if not text.strip():
        raise ClientPayloadError("Document contains no text.", param=param)
    if len(text) > _MAX_EXTRACTED_DOCUMENT_CHARS:
        raise ClientPayloadError(
            f"Extracted document text must not exceed {_MAX_EXTRACTED_DOCUMENT_CHARS} characters.",
            param=param,
        )
    return text


def _safe_attachment_url(value: JsonValue, *, param: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClientPayloadError("Attachment URL must be a non-empty HTTPS URL.", param=param)
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ClientPayloadError("Attachment URL must be a non-empty HTTPS URL.", param=param)
    return url


def _document_filename(value: JsonValue, *, media_type: str, param: str) -> str:
    if value is None:
        extension = {"application/pdf": "pdf", "text/csv": "csv"}.get(media_type, "txt")
        return f"document.{extension}"
    if not isinstance(value, str) or not value.strip():
        raise ClientPayloadError("Document title must be a non-empty string.", param=param)
    return value.strip()[:255]


def _tool_result_output(value: JsonValue, *, param: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not is_json_list(value):
        raise ClientPayloadError("tool_result content must be a string or array of text blocks.")
    text_parts: list[str] = []
    has_tool_reference = False
    for index, part_value in enumerate(value):
        part = _required_mapping(part_value, f"{param}.{index}")
        part_type = part.get("type")
        if part_type == "text" and isinstance(part.get("text"), str):
            text_parts.append(cast(str, part.get("text")))
            continue
        if part_type == "tool_reference":
            _tool_reference_name(part, param=f"{param}.{index}")
            has_tool_reference = True
            continue
        if part_type == "text":
            raise ClientPayloadError("Only text tool_result blocks are supported.")
        raise ClientPayloadError("Only text and tool_reference tool_result blocks are supported.")
    if has_tool_reference:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "".join(text_parts)


def _tool_search_history(
    messages: list[JsonValue],
    *,
    converted_tools: list[JsonValue],
    hosted_tool_aliases: frozenset[str],
    tool_names_to_responses: Mapping[str, str],
) -> dict[str, list[JsonValue] | None]:
    tool_use_names: dict[str, str] = {}
    for message_index, message_value in enumerate(messages):
        message = _required_mapping(message_value, f"messages.{message_index}")
        if message.get("role") != "assistant":
            continue
        content = _content_blocks(message.get("content"), param=f"messages.{message_index}.content")
        for content_index, block_value in enumerate(content):
            block = _required_mapping(block_value, f"messages.{message_index}.content.{content_index}")
            if block.get("type") != "tool_use":
                continue
            tool_use_id = _required_string(block, "id")
            tool_use_names[tool_use_id] = _required_string(block, "name")

    functions_by_name: dict[str, JsonValue] = {}
    for tool_value in converted_tools:
        if not is_json_mapping(tool_value) or tool_value.get("type") != "function":
            continue
        name = tool_value.get("name")
        if isinstance(name, str) and name:
            functions_by_name.setdefault(name, tool_value)

    history: dict[str, list[JsonValue] | None] = {}
    for message_index, message_value in enumerate(messages):
        message = _required_mapping(message_value, f"messages.{message_index}")
        if message.get("role") != "user":
            continue
        content = _content_blocks(message.get("content"), param=f"messages.{message_index}.content")
        for content_index, block_value in enumerate(content):
            block = _required_mapping(block_value, f"messages.{message_index}.content.{content_index}")
            if block.get("type") != "tool_result":
                continue
            tool_use_id = _required_string(block, "tool_use_id")
            if tool_use_names.get(tool_use_id) != _CLAUDE_TOOL_SEARCH_NAME:
                continue
            param = f"messages.{message_index}.content.{content_index}.content"
            reference_names = _reference_only_tool_names(block.get("content"), param=param)
            if reference_names is None:
                continue
            selected_tools: list[JsonValue] = []
            seen_names: set[str] = set()
            for reference_name in reference_names:
                if reference_name in seen_names:
                    continue
                seen_names.add(reference_name)
                if reference_name in hosted_tool_aliases:
                    continue
                responses_name = tool_names_to_responses.get(reference_name, reference_name)
                selected_tool = functions_by_name.get(responses_name)
                if selected_tool is None:
                    raise ClientPayloadError(
                        f"Tool reference '{reference_name}' not found in available tools.",
                        param=param,
                    )
                selected_tools.append(selected_tool)
            history[tool_use_id] = selected_tools or None
    return history


def _reference_only_tool_names(value: JsonValue, *, param: str) -> list[str] | None:
    if not is_json_list(value) or not value:
        return None
    names: list[str] = []
    for index, part_value in enumerate(value):
        part = _required_mapping(part_value, f"{param}.{index}")
        if part.get("type") != "tool_reference":
            return None
        names.append(_tool_reference_name(part, param=f"{param}.{index}"))
    return names


def _tool_reference_name(part: Mapping[str, JsonValue], *, param: str) -> str:
    value = part.get("tool_name")
    if not isinstance(value, str) or not value.strip():
        raise ClientPayloadError("tool_reference blocks require non-empty 'tool_name'.", param=f"{param}.tool_name")
    return value.strip()


def _tools_to_responses(
    value: JsonValue,
    *,
    claude_desktop: bool,
    route_workspace_web_fetch: bool,
) -> tuple[list[JsonValue], frozenset[str], dict[str, str], dict[str, str]]:
    if not is_json_list(value):
        raise ClientPayloadError("'tools' must be an array.", param="tools")
    converted: list[JsonValue] = []
    hosted_web_tool: dict[str, JsonValue] | None = None
    hosted_web_tool_index: int | None = None
    hosted_web_tool_source: str | None = None
    hosted_web_aliases: set[str] = set()
    tool_names_to_responses: dict[str, str] = {}
    tool_name_aliases: dict[str, str] = {}
    for index, tool_value in enumerate(value):
        tool = _required_mapping(tool_value, f"tools.{index}")
        converted_web_tool: dict[str, JsonValue] | None = _web_server_tool_to_responses(
            tool,
            index=index,
            claude_desktop=claude_desktop,
        )
        web_tool_source = "server" if converted_web_tool is not None else None
        if converted_web_tool is not None:
            server_tool_name = tool.get("name")
            if isinstance(server_tool_name, str):
                hosted_web_aliases.add(server_tool_name)
        workspace_alias = (
            claude_desktop and route_workspace_web_fetch and tool.get("name") == _CLAUDE_WORKSPACE_WEB_FETCH_NAME
        )
        if workspace_alias:
            input_schema = tool.get("input_schema")
            if not is_json_mapping(input_schema):
                raise ClientPayloadError(
                    "Tool definitions require object 'input_schema'.",
                    param=f"tools.{index}.input_schema",
                )
            converted_web_tool = {"type": "web_search"}
            web_tool_source = "workspace_alias"
            hosted_web_aliases.add(_CLAUDE_WORKSPACE_WEB_FETCH_NAME)
        if converted_web_tool is not None:
            if hosted_web_tool is None:
                hosted_web_tool = converted_web_tool
                hosted_web_tool_index = len(converted)
                hosted_web_tool_source = web_tool_source
                converted.append(converted_web_tool)
            elif web_tool_source == "workspace_alias":
                pass
            elif hosted_web_tool_source == "workspace_alias":
                assert hosted_web_tool_index is not None
                hosted_web_tool = converted_web_tool
                hosted_web_tool_source = web_tool_source
                converted[hosted_web_tool_index] = converted_web_tool
            elif converted_web_tool != hosted_web_tool:
                raise ClientPayloadError(
                    "Anthropic web server tools contain conflicting hosted-tool controls.",
                    param=f"tools.{index}",
                )
            continue
        name = _required_string(tool, "name")
        if name in tool_names_to_responses:
            raise ClientPayloadError(
                f"Duplicate tool name '{name}'.",
                param=f"tools.{index}.name",
            )
        responses_name = _responses_identifier(name, kind="tool_name")
        previous_name = tool_name_aliases.get(responses_name)
        if previous_name is not None and previous_name != name:
            raise ClientPayloadError(
                "Tool names map to an ambiguous Responses identifier.",
                param=f"tools.{index}.name",
            )
        tool_names_to_responses[name] = responses_name
        tool_name_aliases[responses_name] = name
        input_schema = tool.get("input_schema")
        if not is_json_mapping(input_schema):
            raise ClientPayloadError(
                "Tool definitions require object 'input_schema'.", param=f"tools.{index}.input_schema"
            )
        converted_tool: dict[str, JsonValue] = {
            "type": "function",
            "name": responses_name,
            "parameters": input_schema,
        }
        description = tool.get("description")
        if isinstance(description, str):
            converted_tool["description"] = description
        converted.append(converted_tool)
    return converted, frozenset(hosted_web_aliases), tool_names_to_responses, tool_name_aliases


def _latest_user_prompt_targets_public_web(messages: list[JsonValue]) -> bool:
    """Route only when the latest human prompt names public-only targets.

    Anthropic represents client tool results as ``role=user`` messages too.
    Those result-only messages are skipped so the originating human prompt
    still controls the route, while an actual later human prompt overrides
    every URL in older conversation history.
    """

    for message_value in reversed(messages):
        if not is_json_mapping(message_value) or message_value.get("role") != "user":
            continue
        content = message_value.get("content")
        prompt_text: list[str] = []
        if isinstance(content, str):
            prompt_text.append(content)
        elif is_json_list(content):
            for block_value in content:
                if not is_json_mapping(block_value) or block_value.get("type") != "text":
                    continue
                text = block_value.get("text")
                if isinstance(text, str):
                    prompt_text.append(text)
        if not prompt_text:
            continue
        targets = [
            match.group(0).rstrip(".,;:!?)]}") for text in prompt_text for match in _PUBLIC_HTTP_URL_RE.finditer(text)
        ]
        return bool(targets) and all(_is_public_http_url(target) for target in targets)
    return False


def _is_public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return False
    normalized_host = hostname.rstrip(".").lower()
    if normalized_host == "localhost" or normalized_host.endswith(_LOCAL_WEB_HOST_SUFFIXES):
        return False
    try:
        return ipaddress.ip_address(normalized_host).is_global
    except ValueError:
        return "." in normalized_host


def _web_server_tool_to_responses(
    tool: Mapping[str, JsonValue],
    *,
    index: int,
    claude_desktop: bool,
) -> dict[str, JsonValue] | None:
    tool_type = tool.get("type")
    if not isinstance(tool_type, str):
        return None

    family: str | None = None
    for candidate in _SUPPORTED_WEB_SERVER_TOOLS:
        if tool_type.startswith(f"{candidate}_"):
            family = candidate
            break
    if family is None:
        return None
    if tool_type not in _SUPPORTED_WEB_SERVER_TOOLS[family]:
        raise ClientPayloadError(
            f"Unsupported Anthropic web server-tool type '{tool_type}'.",
            param=f"tools.{index}.type",
        )

    name = _required_string(tool, "name")
    if name != family:
        raise ClientPayloadError(
            f"Anthropic server-tool type '{tool_type}' must use name '{family}'.",
            param=f"tools.{index}.name",
        )

    unknown_fields = set(tool) - _WEB_SERVER_TOOL_FIELDS
    if unknown_fields:
        field = sorted(unknown_fields)[0]
        raise ClientPayloadError(
            f"Unsupported Anthropic web server-tool field '{field}'.",
            param=f"tools.{index}.{field}",
        )
    if "blocked_domains" in tool and not claude_desktop:
        raise ClientPayloadError(
            "Anthropic web server-tool 'blocked_domains' cannot be enforced by the mapped upstream.",
            param=f"tools.{index}.blocked_domains",
        )

    converted: dict[str, JsonValue] = {"type": "web_search"}
    allowed_domains = tool.get("allowed_domains")
    if allowed_domains is not None:
        converted["filters"] = {
            "allowed_domains": _web_allowed_domains(
                allowed_domains,
                param=f"tools.{index}.allowed_domains",
            )
        }
    user_location = tool.get("user_location")
    if user_location is not None:
        converted["user_location"] = _web_user_location(
            user_location,
            param=f"tools.{index}.user_location",
        )
    return converted


def _web_allowed_domains(value: JsonValue, *, param: str) -> list[JsonValue]:
    if not is_json_list(value) or not value:
        raise ClientPayloadError("'allowed_domains' must be a non-empty array of non-empty strings.", param=param)
    domains: list[JsonValue] = []
    for domain in value:
        if not isinstance(domain, str) or not domain.strip():
            raise ClientPayloadError(
                "'allowed_domains' must contain only non-empty strings.",
                param=param,
            )
        domains.append(domain.strip())
    return domains


def _web_user_location(value: JsonValue, *, param: str) -> dict[str, JsonValue]:
    if not is_json_mapping(value):
        raise ClientPayloadError("'user_location' must be an object.", param=param)
    unknown_fields = set(value) - _WEB_USER_LOCATION_FIELDS
    if unknown_fields:
        field = sorted(unknown_fields)[0]
        raise ClientPayloadError(
            f"Unsupported 'user_location' field '{field}'.",
            param=f"{param}.{field}",
        )
    if value.get("type") != "approximate":
        raise ClientPayloadError("'user_location.type' must be 'approximate'.", param=f"{param}.type")
    location: dict[str, JsonValue] = {"type": "approximate"}
    for field in ("city", "region", "country", "timezone"):
        field_value = value.get(field)
        if field_value is None:
            continue
        if not isinstance(field_value, str) or not field_value.strip():
            raise ClientPayloadError(
                f"'user_location.{field}' must be a non-empty string.",
                param=f"{param}.{field}",
            )
        location[field] = field_value.strip()
    return location


def _tool_choice_to_responses(
    value: JsonValue,
    *,
    hosted_web_aliases: frozenset[str] = frozenset(),
    tool_names_to_responses: Mapping[str, str] | None = None,
) -> tuple[JsonValue | None, bool | None]:
    if value is None:
        return None, None
    if not is_json_mapping(value):
        raise ClientPayloadError("'tool_choice' must be an object.", param="tool_choice")
    choice_type = _required_string(value, "type")
    parallel = value.get("disable_parallel_tool_use")
    disable_parallel = _optional_bool(parallel, "tool_choice.disable_parallel_tool_use")
    if choice_type == "auto":
        return "auto", False if disable_parallel else None
    if choice_type == "any":
        return "required", False if disable_parallel else None
    if choice_type == "tool":
        name = _required_string(value, "name")
        if name in _SUPPORTED_WEB_SERVER_TOOLS or name in hosted_web_aliases:
            return {"type": "web_search"}, False if disable_parallel else None
        responses_name = (tool_names_to_responses or {}).get(name) or _responses_identifier(name, kind="tool_name")
        return {"type": "function", "name": responses_name}, False if disable_parallel else None
    if choice_type == "none":
        return "none", False if disable_parallel else None
    raise ClientPayloadError("Unsupported tool_choice type.", param="tool_choice.type")


def _anthropic_reasoning_block(item: Mapping[str, JsonValue]) -> dict[str, JsonValue] | None:
    thinking = _reasoning_summary_text(item)
    signature = _optional_string(item.get("encrypted_content"))
    if not thinking and signature is None:
        return None
    _log_reasoning_translation(
        direction="response",
        outcome="emitted",
        summary_chars=len(thinking),
        signature_chars=len(signature or ""),
    )
    block: dict[str, JsonValue] = {"type": "thinking", "thinking": thinking}
    if signature is not None:
        block["signature"] = signature
    return block


def _reasoning_summary_text(item: Mapping[str, JsonValue]) -> str:
    summary = item.get("summary")
    if not is_json_list(summary):
        return ""
    parts: list[str] = []
    for part_value in summary:
        if not is_json_mapping(part_value) or part_value.get("type") != "summary_text":
            continue
        text = part_value.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n\n".join(parts)


def _log_reasoning_translation(
    *,
    direction: str,
    outcome: str,
    summary_chars: int,
    signature_chars: int,
) -> None:
    logger.info(
        "anthropic_protocol_reasoning direction=%s outcome=%s summary_chars=%d signature_chars=%d",
        direction,
        outcome,
        summary_chars,
        signature_chars,
    )


def _tool_use_block(
    item: Mapping[str, JsonValue],
    *,
    tool_name_aliases: Mapping[str, str] | None = None,
) -> dict[str, JsonValue]:
    arguments = item.get("arguments")
    parsed_input: JsonValue = {}
    if isinstance(arguments, str) and arguments:
        try:
            decoded = json.loads(arguments)
        except json.JSONDecodeError:
            decoded = {}
        if is_json_mapping(decoded):
            parsed_input = decoded
    call_id = item.get("call_id")
    name = item.get("name")
    upstream_name = name if isinstance(name, str) and name else "unknown_tool"
    return {
        "type": "tool_use",
        "id": call_id if isinstance(call_id, str) and call_id else "toolu_unknown",
        "name": (tool_name_aliases or {}).get(upstream_name, upstream_name),
        "input": parsed_input,
    }


def _response_text(part: Mapping[str, JsonValue]) -> str | None:
    part_type = part.get("type")
    if part_type not in {"output_text", "text"}:
        return None
    text = part.get("text")
    return text if isinstance(text, str) else None


def _stop_reason(response: Mapping[str, JsonValue], *, saw_tool_use: bool) -> str:
    if saw_tool_use:
        return "tool_use"
    incomplete = response.get("incomplete_details")
    if is_json_mapping(incomplete) and incomplete.get("reason") == "max_output_tokens":
        return "max_tokens"
    return "end_turn"


def _anthropic_usage(usage: Mapping[str, JsonValue]) -> dict[str, int]:
    result = {
        "input_tokens": _integer(usage.get("input_tokens")),
        "output_tokens": _integer(usage.get("output_tokens")),
    }
    input_details_value = usage.get("input_tokens_details")
    input_details = input_details_value if is_json_mapping(input_details_value) else {}
    cached_tokens = _integer(input_details.get("cached_tokens"))
    cache_write_tokens = _integer(usage.get("cache_write_tokens"))
    if cache_write_tokens == 0:
        cache_write_tokens = _integer(input_details.get("cache_write_tokens"))
    if cached_tokens:
        result["cache_read_input_tokens"] = cached_tokens
    if cache_write_tokens:
        result["cache_creation_input_tokens"] = cache_write_tokens
    return result


def _integer(value: JsonValue | None) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _integer_or_none(value: JsonValue | None) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_string(value: JsonValue | None) -> str | None:
    return value if isinstance(value, str) and value else None
