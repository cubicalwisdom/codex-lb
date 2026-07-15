from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest
from pydantic import ValidationError

from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.requests import (
    ResponsesCompactRequest,
    ResponsesRequest,
    _input_image_file_reference,
    extract_input_file_ids,
    extract_input_image_file_references,
)
from app.core.openai.v1_requests import V1ResponsesCompactRequest, V1ResponsesRequest
from app.core.types import JsonValue


def _responses_lite_input_items() -> tuple[list[JsonValue], list[JsonValue]]:
    additional_tools_before: JsonValue = {
        "type": "additional_tools",
        "role": "developer",
        "tools": [
            {
                "type": "custom",
                "name": "exec",
                "format": {
                    "type": "grammar",
                    "syntax": "lark",
                    "definition": "start: /.+/",
                },
            }
        ],
    }
    developer_message: JsonValue = {
        "type": "message",
        "role": "developer",
        "content": "Use the supplied execution tool.",
    }
    additional_tools_after: JsonValue = {
        "type": "additional_tools",
        "role": "developer",
        "tools": [
            {
                "type": "custom",
                "name": "apply_patch",
                "format": {
                    "type": "grammar",
                    "syntax": "lark",
                    "definition": 'start: "PATCH"',
                },
            }
        ],
    }
    user_message: JsonValue = {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "Show the working directory."}],
    }
    custom_tool_call: JsonValue = {
        "type": "custom_tool_call",
        "call_id": "call_exec_1",
        "name": "exec",
        "input": "pwd",
    }
    custom_tool_call_output: JsonValue = {
        "type": "custom_tool_call_output",
        "call_id": "call_exec_1",
        "output": "H:/workspace",
    }
    return (
        [
            additional_tools_before,
            developer_message,
            additional_tools_after,
            user_message,
            custom_tool_call,
            custom_tool_call_output,
        ],
        deepcopy(
            [
                additional_tools_before,
                developer_message,
                additional_tools_after,
                user_message,
                custom_tool_call,
                custom_tool_call_output,
            ]
        ),
    )


def test_responses_requires_instructions():
    with pytest.raises(ValidationError):
        ResponsesRequest.model_validate({"model": "gpt-5.1", "input": []})


def test_responses_requires_input():
    with pytest.raises(ValidationError):
        ResponsesRequest.model_validate({"model": "gpt-5.1", "instructions": "hi"})


def test_store_true_is_coerced_to_false():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": [], "store": True}
    request = ResponsesRequest.model_validate(payload)
    assert request.store is False


def test_store_omitted_defaults_to_false():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": []}
    request = ResponsesRequest.model_validate(payload)

    assert request.store is False
    assert request.to_payload()["store"] is False


def test_store_false_is_preserved():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": [], "store": False}
    request = ResponsesRequest.model_validate(payload)

    assert request.to_payload()["store"] is False


def test_compact_store_true_is_coerced_to_false():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": [], "store": True}
    request = ResponsesCompactRequest.model_validate(payload)
    assert request.store is False


def test_compact_store_omitted_defaults_to_false():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": []}
    request = ResponsesCompactRequest.model_validate(payload)

    assert request.store is False
    assert "store" not in request.to_payload()


def test_compact_store_false_is_preserved():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": [], "store": False}
    request = ResponsesCompactRequest.model_validate(payload)

    assert request.store is False
    assert "store" not in request.to_payload()


def test_known_unsupported_upstream_fields_are_stripped():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "max_output_tokens": 32000,
        "metadata": {"client": "cursor"},
        "prompt_cache_retention": "4h",
        "safety_identifier": "safe_123",
        "temperature": 0.2,
        "top_p": 0.9,
        "truncation": "auto",
        "user": "cursor-user",
        "custom_field": "kept",
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert "max_output_tokens" not in dumped
    assert "metadata" not in dumped
    assert "prompt_cache_retention" not in dumped
    assert "safety_identifier" not in dumped
    assert "temperature" not in dumped
    assert "top_p" not in dumped
    assert "truncation" not in dumped
    assert "user" not in dumped
    assert dumped["custom_field"] == "kept"


def test_responses_preserves_service_tier():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "service_tier": "priority",
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["service_tier"] == "priority"


def test_responses_normalizes_fast_service_tier_to_priority_for_upstream():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "service_tier": "fast",
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.service_tier == "priority"
    dumped = request.to_payload()
    assert dumped["service_tier"] == "priority"


def test_compact_known_unsupported_upstream_fields_are_stripped():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "metadata": {"client": "cursor"},
        "prompt_cache_retention": "4h",
        "safety_identifier": "safe_123",
        "temperature": 0.2,
        "top_p": 0.9,
        "user": "cursor-user",
    }
    request = ResponsesCompactRequest.model_validate(payload)

    dumped = request.to_payload()
    assert "metadata" not in dumped
    assert "prompt_cache_retention" not in dumped
    assert "safety_identifier" not in dumped
    assert "temperature" not in dumped
    assert "top_p" not in dumped
    assert "user" not in dumped


def test_compact_normalizes_fast_service_tier_to_priority_for_upstream():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "service_tier": "fast",
    }
    request = ResponsesCompactRequest.model_validate(payload)

    assert request.service_tier == "priority"
    dumped = request.to_payload()
    assert dumped["service_tier"] == "priority"


def test_openai_prompt_cache_aliases_are_normalized():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "promptCacheKey": "thread_123",
        "promptCacheRetention": "4h",
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["prompt_cache_key"] == "thread_123"
    assert "prompt_cache_retention" not in dumped
    assert "promptCacheKey" not in dumped
    assert "promptCacheRetention" not in dumped


def test_settings_default_prompt_cache_affinity_ttl_is_1800():
    from app.core.config.settings import Settings

    settings = Settings()

    assert settings.openai_cache_affinity_max_age_seconds == 1800


def test_responses_to_payload_preserves_tool_order_and_object_keys():
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.1",
            "instructions": "hi",
            "input": [],
            "tools": [
                {
                    "type": "function",
                    "name": "zeta",
                    "parameters": {"required": [], "type": "object", "properties": {}},
                    "description": "later",
                },
                {
                    "description": "first",
                    "parameters": {"properties": {}, "required": [], "type": "object"},
                    "type": "function",
                    "name": "alpha",
                },
            ],
        }
    )

    dumped = request.to_payload()
    tools = cast(list[JsonValue], dumped["tools"])
    assert tools[0]["name"] == "zeta"
    assert list(tools[0].keys()) == ["type", "name", "parameters", "description"]


def test_responses_to_payload_omits_unset_tools_and_preserves_reserved_namespace_tool():
    omitted = ResponsesRequest.model_validate({"model": "gpt-5.6", "instructions": "", "input": []})
    reserved_tool: JsonValue = {
        "type": "namespace",
        "name": "collaboration",
        "tools": [{"type": "function", "name": "spawn_agent", "strict": False}],
    }
    explicit = ResponsesRequest.model_validate(
        {"model": "gpt-5.6", "instructions": "", "input": [], "tools": [reserved_tool]}
    )

    assert "tools" not in omitted.to_payload()
    assert explicit.to_payload()["tools"] == [reserved_tool]


def test_openai_compatible_reasoning_aliases_are_normalized():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "reasoningEffort": "high",
        "reasoningSummary": "auto",
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["reasoning"] == {"effort": "high", "summary": "auto"}
    assert "reasoningEffort" not in dumped
    assert "reasoningSummary" not in dumped


def test_openai_compatible_reasoning_effort_preserves_client_plane_ultra():
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.6-sol",
            "instructions": "hi",
            "input": [],
            "reasoningEffort": " ULTRA ",
        }
    )

    dumped = request.to_payload()

    assert dumped["reasoning"] == {"effort": "ultra"}
    assert "reasoningEffort" not in dumped


def test_provider_thinking_aliases_are_normalized():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "thinking": {"type": "enabled", "budget_tokens": 2048},
        "enable_thinking": True,
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["reasoning"] == {"effort": "medium"}
    assert "thinking" not in dumped
    assert "enable_thinking" not in dumped


def test_provider_thinking_mapping_preserves_client_plane_ultra():
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.6-sol",
            "instructions": "hi",
            "input": [],
            "thinking": {"effort": " ULTRA "},
        }
    )

    dumped = request.to_payload()

    assert dumped["reasoning"] == {"effort": "ultra"}
    assert "thinking" not in dumped


def test_provider_thinking_string_alias_accepts_catalog_advertised_efforts():
    for effort in ("low", "medium", "high", "xhigh", "max", "ultra"):
        payload = {
            "model": "gpt-5.6-sol",
            "instructions": "hi",
            "input": [],
            "thinking": effort,
        }
        request = ResponsesRequest.model_validate(payload)

        dumped = request.to_payload()
        assert dumped["reasoning"] == {"effort": effort}
        assert "thinking" not in dumped


def test_explicit_reasoning_wins_over_provider_thinking_aliases():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "reasoning": {"effort": "high"},
        "thinking": {"type": "enabled"},
        "enable_thinking": True,
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["reasoning"] == {"effort": "high"}
    assert "thinking" not in dumped
    assert "enable_thinking" not in dumped


def test_openai_compatible_text_verbosity_alias_is_normalized():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "textVerbosity": "low",
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["text"] == {"verbosity": "low"}
    assert "textVerbosity" not in dumped


def test_openai_compatible_top_level_verbosity_is_normalized():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "verbosity": "medium",
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["text"] == {"verbosity": "medium"}
    assert "verbosity" not in dumped


def test_v1_responses_preserves_service_tier():
    payload = {
        "model": "gpt-5.1",
        "input": "hello",
        "service_tier": "priority",
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    dumped = request.to_payload()
    assert dumped["service_tier"] == "priority"


def test_v1_responses_normalizes_fast_service_tier_to_priority_for_upstream():
    payload = {
        "model": "gpt-5.1",
        "input": "hello",
        "service_tier": "fast",
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.service_tier == "priority"
    dumped = request.to_payload()
    assert dumped["service_tier"] == "priority"


def test_interleaved_reasoning_fields_are_sanitized_from_input():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "role": "user",
                "reasoning_content": "hidden",
                "tool_calls": [{"id": "call_1"}],
                "function_call": {"name": "noop", "arguments": "{}"},
                "content": [
                    {"type": "input_text", "text": "hello"},
                    {"type": "reasoning", "reasoning_content": "drop"},
                    {"type": "input_text", "text": "world", "reasoning_details": {"tokens": 1}},
                ],
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "hello"},
                {"type": "input_text", "text": "world"},
            ],
        }
    ]


def test_interleaved_reasoning_sanitization_preserves_top_level_reasoning():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "reasoning": {"effort": "high", "summary": "auto"},
        "input": [
            {
                "role": "user",
                "reasoning_details": {"tokens": 2},
                "content": [{"type": "input_text", "text": "hello", "reasoning_content": "drop"}],
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["reasoning"] == {"effort": "high", "summary": "auto"}
    assert dumped["input"] == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]


def test_interleaved_reasoning_sanitization_preserves_nested_function_call_arguments():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": {
                    "tool_calls": [{"id": "nested_1"}],
                    "function_call": {"name": "nested_fn"},
                    "reasoning_details": {"tokens": 3},
                },
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    dumped = request.to_payload()
    assert dumped["input"] == payload["input"]


def test_responses_accepts_string_input():
    payload = {"model": "gpt-5.1", "instructions": "hi", "input": "hello"}
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]


@pytest.mark.parametrize(
    ("tool_type", "expected"),
    [
        ("web_search", "web_search"),
        ("web_search_preview", "web_search"),
    ],
)
def test_responses_accepts_builtin_tools(tool_type, expected):
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "tools": [{"type": tool_type}],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.tools == [{"type": expected}]


@pytest.mark.parametrize(
    "tool_payload",
    [
        {"type": "image_generation"},
        {
            "type": "computer_use_preview",
            "display_width": 1024,
            "display_height": 768,
            "environment": "browser",
        },
        {"type": "computer_use", "display_width": 1024, "display_height": 768, "environment": "browser"},
        {"type": "file_search", "vector_store_ids": ["vs_dummy"]},
        {"type": "code_interpreter", "container": {"type": "auto"}},
    ],
)
def test_responses_accepts_builtin_tool_passthrough(tool_payload):
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "tools": [tool_payload],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.tools == [tool_payload]


@pytest.mark.parametrize("tool_choice", [{"type": "web_search"}, {"type": "web_search_preview"}])
def test_responses_normalizes_tool_choice_web_search_preview(tool_choice):
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "tool_choice": tool_choice,
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.tool_choice == {"type": "web_search"}


def test_responses_rejects_invalid_include_value():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "include": ["message.output_text.logprobs", "bad.include.value"],
    }
    with pytest.raises(ValueError, match="Unsupported include value"):
        ResponsesRequest.model_validate(payload)


def test_responses_accepts_known_include_values():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "include": ["reasoning.encrypted_content", "web_search_call.action.sources"],
    }
    request = ResponsesRequest.model_validate(payload)
    assert request.include == ["reasoning.encrypted_content", "web_search_call.action.sources"]


def test_responses_accepts_previous_response_id_without_conversation():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "previous_response_id": "  resp_1  ",
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.previous_response_id == "resp_1"
    assert request.to_payload()["previous_response_id"] == "resp_1"


def test_responses_rejects_conversation_previous_response_id():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "conversation": "conv_1",
        "previous_response_id": "resp_1",
    }
    with pytest.raises(ValueError, match="either 'conversation' or 'previous_response_id'"):
        ResponsesRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("continuity_field", "continuity_value"),
    [("previous_response_id", "resp_1"), ("conversation", "conv_1")],
)
def test_v1_responses_accepts_continuation_without_new_input(continuity_field: str, continuity_value: str):
    request = V1ResponsesRequest.model_validate(
        {"model": "gpt-5.1", continuity_field: continuity_value}
    ).to_responses_request()

    assert request.instructions == ""
    assert request.input == []
    assert getattr(request, continuity_field) == continuity_value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_output_tokens", 1024),
        ("prompt_cache_retention", "24h"),
        ("promptCacheRetention", "24h"),
        ("safety_identifier", "safe_123"),
        ("temperature", 0.2),
        ("top_p", 0.9),
        ("truncation", "auto"),
        ("user", "user_123"),
    ],
)
def test_v1_responses_rejects_controls_that_cannot_be_honored(field: str, value: JsonValue):
    request = V1ResponsesRequest.model_validate({"model": "gpt-5.1", "input": "hi", field: value})

    with pytest.raises(ClientPayloadError) as exc_info:
        request.to_responses_request()

    assert exc_info.value.code == "unsupported_parameter"
    assert exc_info.value.param == field


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("background", True),
        ("store", True),
        ("metadata", {"client": "test"}),
    ],
)
def test_v1_responses_accepts_locally_managed_lifecycle_controls(field: str, value: JsonValue):
    request = V1ResponsesRequest.model_validate(
        {"model": "gpt-5.1", "input": "hi", field: value}
    ).to_responses_request()

    assert request.to_payload().get(field) is None or field == "store"


def test_v1_responses_accepts_false_background_and_store_without_forwarding_background():
    request = V1ResponsesRequest.model_validate(
        {"model": "gpt-5.1", "input": "hi", "background": False, "store": False}
    ).to_responses_request()

    payload = request.to_payload()
    assert "background" not in payload
    assert payload["store"] is False


def test_v1_messages_convert_to_responses_input():
    payload = {
        "model": "gpt-5.1",
        "messages": [{"role": "user", "content": "hi"}],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.instructions == ""
    assert request.input == [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}]


def test_v1_system_message_moves_to_instructions():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
        ],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.instructions == "sys"
    assert request.input == [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}]


def test_responses_input_system_message_moves_to_instructions():
    payload = {
        "model": "gpt-5.1",
        "instructions": "primary",
        "input": [
            {"type": "message", "role": "system", "content": [{"type": "input_text", "text": "sys"}]},
            {"type": "message", "role": "developer", "content": "dev"},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.instructions == "primary\nsys\ndev"
    assert request.input == [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]


def test_responses_preserves_responses_lite_input_shape_untouched():
    input_items, expected_input = _responses_lite_input_items()
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.6-sol",
            "instructions": "primary",
            "input": input_items,
        }
    )

    dumped = request.to_payload()

    assert dumped["instructions"] == "primary"
    assert "tools" not in dumped
    assert dumped["input"] == expected_input


@pytest.mark.parametrize("request_type", [ResponsesRequest, ResponsesCompactRequest])
def test_responses_preserves_non_message_directives_byte_identically(request_type):
    developer_directive = {
        "type": "future_directive",
        "role": "developer",
        "directive": {"mode": "strict", "budget": 3},
        "reasoning_content": "directive-level reasoning",
        "reasoning_details": {"opaque": True},
        "tool_calls": [{"id": "call_1", "name": "future_tool"}],
        "function_call": {"name": "future_tool", "arguments": "{}"},
        "content": [{"type": "reasoning", "text": "opaque directive content"}],
    }
    system_directive = {
        "type": "future_directive",
        "role": "system",
        "directive": {"mode": "audit"},
    }

    request = request_type.model_validate(
        {
            "model": "gpt-5.6-sol",
            "input": [
                developer_directive,
                {"type": "message", "role": "developer", "content": "follow the directive"},
                system_directive,
                {"type": "message", "role": "user", "content": "inspect"},
            ],
        }
    )

    dumped = request.to_payload()

    assert request.instructions == "follow the directive"
    assert request.input == [
        developer_directive,
        system_directive,
        {"type": "message", "role": "user", "content": "inspect"},
    ]
    assert dumped["instructions"] == "follow the directive"
    assert dumped["input"] == request.input


@pytest.mark.parametrize("request_type", [ResponsesRequest, ResponsesCompactRequest])
def test_responses_directive_only_input_defaults_instructions_to_empty(request_type):
    developer_directive = {
        "type": "future_directive",
        "role": "developer",
        "directive": {"mode": "strict"},
    }

    request = request_type.model_validate(
        {
            "model": "gpt-5.6-sol",
            "input": [developer_directive],
        }
    )

    assert request.instructions == ""
    assert request.input == [developer_directive]
    assert request.to_payload()["input"] == [developer_directive]


def test_responses_input_system_message_keeps_user_text_parts():
    payload = {
        "model": "gpt-5.1",
        "instructions": "primary",
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": "sys"}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "hello"},
                    {"type": "input_file", "file_id": "file_123"},
                ],
            },
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.instructions == "primary\nsys"
    assert request.input == [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": "hello"},
                {"type": "input_file", "file_id": "file_123"},
            ],
        }
    ]


def test_responses_input_system_message_preserves_non_text_parts():
    payload = {
        "model": "gpt-5.1",
        "instructions": "primary",
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [
                    {"type": "input_text", "text": "sys"},
                    {"type": "input_file", "file_id": "file_123"},
                    {"type": "input_image", "image_url": "sediment://file_456"},
                ],
            },
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.instructions == "primary\nsys"
    assert request.input == [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_file", "file_id": "file_123"},
                {"type": "input_image", "image_url": "sediment://file_456"},
            ],
        },
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
    ]
    assert extract_input_file_ids(request.input) == {"file_123", "file_456"}
    assert [ref.file_id for ref in extract_input_image_file_references(request.input)] == ["file_456"]


def test_responses_input_developer_message_preserves_single_non_text_part():
    payload = {
        "model": "gpt-5.1",
        "instructions": "primary",
        "input": [
            {
                "type": "message",
                "role": "developer",
                "content": {"type": "input_file", "file_id": "file_123"},
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.instructions == "primary"
    assert request.input == [
        {
            "type": "message",
            "role": "user",
            "content": {"type": "input_file", "file_id": "file_123"},
        }
    ]
    assert extract_input_file_ids(request.input) == {"file_123"}


def test_responses_compact_input_system_message_moves_to_instructions():
    payload = {
        "model": "gpt-5.1",
        "instructions": "primary",
        "input": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "compact me"},
        ],
    }
    request = ResponsesCompactRequest.model_validate(payload)

    assert request.instructions == "primary\nsys"
    assert request.input == [{"role": "user", "content": "compact me"}]


def test_responses_compact_preserves_responses_lite_input_shape_untouched():
    input_items, expected_input = _responses_lite_input_items()
    request = ResponsesCompactRequest.model_validate(
        {
            "model": "gpt-5.6-sol",
            "instructions": "primary",
            "input": input_items,
        }
    )

    dumped = request.to_payload()

    assert dumped["instructions"] == "primary"
    assert "tools" not in dumped
    assert dumped["input"] == expected_input


def test_v1_instructions_merge():
    payload = {
        "model": "gpt-5.1",
        "instructions": "primary",
        "messages": [{"role": "developer", "content": "secondary"}],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.instructions == "primary\nsecondary"


def test_v1_messages_and_input_conflict():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [{"role": "user", "content": "hi"}],
        "messages": [{"role": "user", "content": "hi"}],
    }
    with pytest.raises(ValueError, match="either 'input' or 'messages'"):
        V1ResponsesRequest.model_validate(payload)


def test_v1_input_string_passthrough():
    payload = {"model": "gpt-5.1", "input": "hello"}
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.input == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]


@pytest.mark.parametrize(
    "tool_payload",
    [
        {"type": "image_generation"},
        {
            "type": "computer_use_preview",
            "display_width": 1024,
            "display_height": 768,
            "environment": "browser",
        },
        {"type": "computer_use", "display_width": 1024, "display_height": 768, "environment": "browser"},
        {"type": "file_search", "vector_store_ids": ["vs_dummy"]},
        {"type": "code_interpreter", "container": {"type": "auto"}},
    ],
)
def test_v1_responses_accepts_builtin_tools(tool_payload):
    payload = {"model": "gpt-5.1", "input": [], "tools": [tool_payload]}
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.tools == [tool_payload]


def test_compact_strips_tool_fields():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [],
        "tools": [{"type": "image_generation"}],
        "tool_choice": {"type": "image_generation"},
        "parallel_tool_calls": True,
    }
    request = ResponsesCompactRequest.model_validate(payload)

    dumped = request.to_payload()
    assert "tools" not in dumped
    assert "tool_choice" not in dumped
    assert dumped["parallel_tool_calls"] is False


@pytest.mark.codex_parity_smoke
def test_v1_compact_strips_tool_fields():
    payload = {
        "model": "gpt-5.1",
        "input": "hello",
        "tools": [{"type": "image_generation"}],
        "tool_choice": {"type": "image_generation"},
        "parallel_tool_calls": True,
    }
    request = V1ResponsesCompactRequest.model_validate(payload).to_compact_request()

    dumped = request.to_payload()
    assert "tools" not in dumped
    assert "tool_choice" not in dumped
    assert dumped["parallel_tool_calls"] is False


def test_v1_compact_messages_convert():
    payload = {
        "model": "gpt-5.1",
        "messages": [{"role": "user", "content": "hi"}],
    }
    request = V1ResponsesCompactRequest.model_validate(payload).to_compact_request()

    assert isinstance(request, ResponsesCompactRequest)
    assert request.instructions == ""
    assert request.input == [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}]


def test_v1_compact_input_string_passthrough():
    payload = {"model": "gpt-5.1", "input": "hello"}
    request = V1ResponsesCompactRequest.model_validate(payload).to_compact_request()

    assert request.input == [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}]


def test_v1_compact_reasoning_passthrough():
    payload = {
        "model": "gpt-5.1",
        "input": "hello",
        "reasoning": {"effort": "high"},
    }
    request = V1ResponsesCompactRequest.model_validate(payload).to_compact_request()

    assert request.reasoning is not None
    assert request.reasoning.effort == "high"


def test_v1_compact_store_omitted_defaults_to_false():
    payload = {"model": "gpt-5.1", "input": "hello"}
    request = V1ResponsesCompactRequest.model_validate(payload).to_compact_request()

    assert request.store is False
    assert "store" not in request.to_payload()


def test_v1_compact_store_true_is_rejected_explicitly():
    payload = {"model": "gpt-5.1", "input": "hello", "store": True}
    request = V1ResponsesCompactRequest.model_validate(payload)

    with pytest.raises(ClientPayloadError) as exc_info:
        request.to_compact_request()

    assert exc_info.value.code == "unsupported_parameter"
    assert exc_info.value.param == "store"


def test_responses_normalizes_assistant_input_text_to_output_text():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {"role": "assistant", "content": [{"type": "input_text", "text": "Prior answer"}]},
            {"role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [
        {"role": "assistant", "content": [{"type": "output_text", "text": "Prior answer"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
    ]


def test_v1_assistant_messages_normalize_to_output_text():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {"role": "assistant", "content": "Prior answer"},
            {"role": "user", "content": "Continue"},
        ],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.input == [
        {"role": "assistant", "content": [{"type": "output_text", "text": "Prior answer"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
    ]


def test_responses_normalizes_assistant_object_content_to_array():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [{"role": "assistant", "content": {"type": "input_text", "text": "Prior answer"}}],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"role": "assistant", "content": [{"type": "output_text", "text": "Prior answer"}]}]


def test_responses_normalizes_tool_role_input_item_to_function_call_output():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": [{"type": "input_text", "text": '{"ok":true}'}],
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'}]


def test_responses_normalizes_tool_role_input_item_with_camel_call_id():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "role": "tool",
                "toolCallId": "call_1",
                "content": [{"type": "input_text", "text": '{"ok":true}'}],
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'}]


def test_responses_normalizes_tool_role_input_item_preserves_part_order_without_delimiters():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": [
                    {"type": "input_text", "text": '{"a":'},
                    {"type": "input_text", "text": ""},
                    {"type": "input_text", "text": "1}"},
                ],
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"type": "function_call_output", "call_id": "call_1", "output": '{"a":1}'}]


def test_responses_normalizes_tool_role_input_item_preserves_output_field():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "role": "tool",
                "call_id": "call_1",
                "output": '{"ok":true}',
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'}]


def test_responses_normalizes_tool_role_input_item_uses_content_when_output_is_null():
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {
                "role": "tool",
                "call_id": "call_1",
                "output": None,
                "content": '{"ok":true}',
            }
        ],
    }
    request = ResponsesRequest.model_validate(payload)

    assert request.input == [{"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'}]


def test_v1_tool_messages_normalize_to_function_call_output():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {"role": "assistant", "content": "Running tool."},
            {"role": "tool", "tool_call_id": "call_1", "content": '{"ok":true}'},
            {"role": "user", "content": "Continue"},
        ],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.input == [
        {"role": "assistant", "content": [{"type": "output_text", "text": "Running tool."}]},
        {"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'},
        {"role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
    ]


def test_v1_assistant_tool_calls_normalize_to_function_call():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": '{"q":"abc"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": '{"ok":true}'},
            {"role": "user", "content": "Continue"},
        ],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.input == [
        {"role": "assistant", "content": [{"type": "output_text", "text": ""}]},
        {"type": "function_call", "call_id": "call_1", "name": "lookup", "arguments": '{"q":"abc"}'},
        {"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'},
        {"role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
    ]


def test_v1_tool_message_accepts_tool_call_id_camel_case():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {"role": "tool", "toolCallId": "call_1", "content": '{"ok":true}'},
            {"role": "user", "content": "Continue"},
        ],
    }
    request = V1ResponsesRequest.model_validate(payload).to_responses_request()

    assert request.input == [
        {"type": "function_call_output", "call_id": "call_1", "output": '{"ok":true}'},
        {"role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
    ]


def test_v1_tool_message_requires_tool_call_id():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {"role": "tool", "content": '{"ok":true}'},
            {"role": "user", "content": "Continue"},
        ],
    }
    with pytest.raises(ClientPayloadError, match="tool messages must include 'tool_call_id'"):
        V1ResponsesRequest.model_validate(payload).to_responses_request()


def test_v1_rejects_unknown_message_role():
    payload = {
        "model": "gpt-5.1",
        "messages": [
            {"role": "moderator", "content": "Nope"},
            {"role": "user", "content": "Continue"},
        ],
    }
    with pytest.raises(ClientPayloadError, match="Unsupported message role"):
        V1ResponsesRequest.model_validate(payload).to_responses_request()


def test_responses_accepts_input_file_with_file_id_content_item():
    """Regression: ``input_file`` content items with a ``file_id`` were
    previously rejected. They are now allowed and forwarded verbatim so
    callers can reference uploads registered through the
    ``POST /backend-api/files`` upload protocol."""
    content = [
        {"type": "input_text", "text": "Summarize this file."},
        {"type": "input_file", "file_id": "file_abc"},
    ]
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [{"role": "user", "content": content}],
    }
    request = ResponsesRequest.model_validate(payload)
    assert request.input == [{"role": "user", "content": content}]


def test_responses_compact_accepts_input_file_with_file_id_content_item():
    content = [
        {"type": "input_text", "text": "Summarize this file."},
        {"type": "input_file", "file_id": "file_abc"},
    ]
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [{"role": "user", "content": content}],
    }
    request = ResponsesCompactRequest.model_validate(payload)
    assert request.input == [{"role": "user", "content": content}]


def test_responses_accepts_top_level_input_file_with_file_id():
    """Top-level ``input_file`` items (sibling of role messages) were
    also rejected; they should now be forwarded as-is."""
    payload = {
        "model": "gpt-5.1",
        "instructions": "hi",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
            {"type": "input_file", "file_id": "file_root"},
        ],
    }
    request = ResponsesRequest.model_validate(payload)
    forwarded = request.input
    assert isinstance(forwarded, list)
    assert {"type": "input_file", "file_id": "file_root"} in forwarded


def test_extract_input_file_ids_string_input_returns_empty_set():
    assert extract_input_file_ids("Hello world") == set()


def test_extract_input_file_ids_finds_top_level_and_nested_ids():
    input_value: list[JsonValue] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Summarize."},
                {"type": "input_file", "file_id": "file_a"},
            ],
        },
        {"type": "input_file", "file_id": "file_b"},
        {"type": "input_image", "file_id": "file_c"},
        # Duplicates and missing/blank ids are filtered out.
        {"type": "input_file", "file_id": "file_a"},
        {"type": "input_file", "file_id": ""},
        {"type": "input_file"},
    ]
    assert extract_input_file_ids(input_value) == {"file_a", "file_b", "file_c"}


def test_input_image_file_reference_returns_file_id_from_input_image_file_id():
    assert _input_image_file_reference({"type": "input_image", "file_id": "file_img"}) == "file_img"


def test_input_image_file_reference_returns_file_id_from_sediment_url():
    assert _input_image_file_reference({"type": "input_image", "image_url": "sediment://file_img"}) == "file_img"


def test_input_image_file_reference_ignores_data_url():
    assert _input_image_file_reference({"type": "input_image", "image_url": "data:image/png;base64,AAAA"}) is None


def test_input_image_file_reference_ignores_https_url():
    assert _input_image_file_reference({"type": "input_image", "image_url": "https://example.com/a.png"}) is None


def test_extract_input_image_file_references_collects_multi_message_paths():
    input_value: list[JsonValue] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "ignore"},
                {"type": "input_image", "file_id": "file_a"},
            ],
        },
        {"type": "input_image", "image_url": "sediment://file_b"},
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": [
                {"type": "input_text", "text": "tool image"},
                {"type": "input_image", "file_id": "file_tool"},
            ],
        },
    ]

    references = extract_input_image_file_references(input_value)

    assert [(reference.item_index, reference.content_index, reference.file_id) for reference in references] == [
        (0, 1, "file_a"),
        (1, None, "file_b"),
        (2, None, "file_tool"),
    ]


def test_extract_input_image_file_references_collects_tool_output_paths():
    input_value: list[JsonValue] = [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": [
                {"type": "input_text", "text": "ignore"},
                {"type": "input_image", "file_id": "file_tool"},
                {"type": "input_image", "image_url": "sediment://file_nested"},
            ],
        }
    ]

    references = extract_input_image_file_references(input_value)

    assert [(reference.item_index, reference.content_index, reference.file_id) for reference in references] == [
        (0, None, "file_tool"),
        (0, None, "file_nested"),
    ]
