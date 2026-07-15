from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.message_coercion import coerce_messages
from app.core.openai.requests import (
    ResponsesCompactRequest,
    ResponsesReasoning,
    ResponsesRequest,
    ResponsesTextControls,
    validate_tool_types,
)
from app.core.types import JsonValue

_UNSUPPORTED_RESPONSE_CONTROLS = (
    "max_output_tokens",
    "prompt_cache_retention",
    "safety_identifier",
    "temperature",
    "top_p",
    "truncation",
    "user",
)
_UNSUPPORTED_RESPONSE_CONTROL_ALIASES = ("promptCacheRetention",)


def reject_unsupported_response_controls(
    payload: Mapping[str, JsonValue],
    *,
    allow_local_lifecycle: bool = False,
) -> None:
    for field in ("background", "store"):
        if payload.get(field) is True and not allow_local_lifecycle:
            raise ClientPayloadError(
                f"The ChatGPT-backed Codex upstream does not support {field}=true.",
                param=field,
                code="unsupported_parameter",
                error_type="invalid_request_error",
            )
    if payload.get("metadata") is not None and not allow_local_lifecycle:
        raise ClientPayloadError(
            "The ChatGPT-backed Codex upstream does not support the 'metadata' parameter.",
            param="metadata",
            code="unsupported_parameter",
            error_type="invalid_request_error",
        )
    for field in _UNSUPPORTED_RESPONSE_CONTROLS:
        if field not in payload or payload.get(field) is None:
            continue
        raise ClientPayloadError(
            f"The ChatGPT-backed Codex upstream does not support the '{field}' parameter.",
            param=field,
            code="unsupported_parameter",
            error_type="invalid_request_error",
        )
    for field in _UNSUPPORTED_RESPONSE_CONTROL_ALIASES:
        if field not in payload or payload.get(field) is None:
            continue
        raise ClientPayloadError(
            f"The ChatGPT-backed Codex upstream does not support the '{field}' parameter.",
            param=field,
            code="unsupported_parameter",
            error_type="invalid_request_error",
        )


class V1ResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    messages: list[JsonValue] | None = None
    input: JsonValue | None = None
    instructions: str | None = None
    tools: list[JsonValue] = Field(default_factory=list)
    tool_choice: str | dict[str, JsonValue] | None = None
    parallel_tool_calls: bool | None = None
    reasoning: ResponsesReasoning | None = None
    store: bool | None = None
    background: bool | None = None
    metadata: dict[str, str] | None = None
    stream: bool | None = None
    include: list[str] = Field(default_factory=list)
    service_tier: str | None = None
    conversation: str | None = None
    previous_response_id: str | None = None
    truncation: str | None = None
    prompt_cache_key: str | None = None
    text: ResponsesTextControls | None = None

    @field_validator("input")
    @classmethod
    def _validate_input_type(cls, value: JsonValue | None) -> JsonValue | None:
        if value is None:
            return value
        if isinstance(value, str) or isinstance(value, list):
            return value
        raise ValueError("input must be a string or array")

    @field_validator("tools")
    @classmethod
    def _validate_tools(cls, value: list[JsonValue]) -> list[JsonValue]:
        return validate_tool_types(value, allow_builtin_tools=True)

    @model_validator(mode="after")
    def _validate_input(self) -> "V1ResponsesRequest":
        continuation = self.conversation is not None or self.previous_response_id is not None
        if self.messages is None and self.input is None and not continuation:
            raise ValueError("Provide either 'input' or 'messages'.")
        if self.messages is not None and self.input not in (None, []):
            raise ValueError("Provide either 'input' or 'messages', not both.")
        if self.conversation and self.previous_response_id:
            raise ValueError("Provide either 'conversation' or 'previous_response_id', not both.")
        return self

    @field_validator("conversation", "previous_response_id")
    @classmethod
    def _normalize_continuity_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def to_responses_request(self) -> ResponsesRequest:
        data = self.model_dump(mode="json", exclude_none=True)
        # Carry an omitted tools field through the v1 adapter. Otherwise the
        # default factory turns omission into an explicit ``tools: []``.
        if "tools" not in self.model_fields_set:
            data.pop("tools", None)
        reject_unsupported_response_controls(data, allow_local_lifecycle=True)
        messages = data.pop("messages", None)
        instructions = data.get("instructions")
        instruction_text = instructions if isinstance(instructions, str) else ""
        input_value = data.get("input")
        input_items: list[JsonValue] = input_value if isinstance(input_value, list) else []
        input_text: str | None = input_value if isinstance(input_value, str) else None

        if messages is not None:
            try:
                instruction_text, input_items = coerce_messages(instruction_text, messages)
            except ClientPayloadError:
                raise
            except ValueError as exc:
                raise ClientPayloadError(str(exc), param="messages") from exc

        data["instructions"] = instruction_text
        if messages is None and input_text is not None:
            data["input"] = input_text
        else:
            data["input"] = input_items
        return ResponsesRequest.model_validate(data)


class V1ResponsesCompactRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    messages: list[JsonValue] | None = None
    input: JsonValue | None = None
    instructions: str | None = None
    reasoning: ResponsesReasoning | None = None

    @model_validator(mode="after")
    def _validate_input(self) -> "V1ResponsesCompactRequest":
        if self.messages is None and self.input is None:
            raise ValueError("Provide either 'input' or 'messages'.")
        if self.messages is not None and self.input not in (None, []):
            raise ValueError("Provide either 'input' or 'messages', not both.")
        return self

    @field_validator("input")
    @classmethod
    def _validate_input_type(cls, value: JsonValue | None) -> JsonValue | None:
        if value is None:
            return value
        if isinstance(value, str) or isinstance(value, list):
            return value
        raise ValueError("input must be a string or array")

    def to_compact_request(self) -> ResponsesCompactRequest:
        data = self.model_dump(mode="json", exclude_none=True)
        reject_unsupported_response_controls(data)
        messages = data.pop("messages", None)
        instructions = data.get("instructions")
        instruction_text = instructions if isinstance(instructions, str) else ""
        input_value = data.get("input")
        input_items: list[JsonValue] = input_value if isinstance(input_value, list) else []
        input_text: str | None = input_value if isinstance(input_value, str) else None

        if messages is not None:
            try:
                instruction_text, input_items = coerce_messages(instruction_text, messages)
            except ClientPayloadError:
                raise
            except ValueError as exc:
                raise ClientPayloadError(str(exc), param="messages") from exc

        data["instructions"] = instruction_text
        if messages is None and input_text is not None:
            data["input"] = input_text
        else:
            data["input"] = input_items
        return ResponsesCompactRequest.model_validate(data)
