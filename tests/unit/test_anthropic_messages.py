from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request

from app.core.anthropic import messages as anthropic_messages
from app.core.auth import dependencies as auth_dependencies
from app.core.exceptions import ProxyAuthError
from app.core.openai.exceptions import ClientPayloadError
from app.core.types import JsonValue
from app.core.utils.sse import parse_sse_data_json
from app.modules.api_keys.service import ApiKeyData

pytestmark = pytest.mark.unit


def _sse(payload: dict[str, JsonValue]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _stream(*blocks: str) -> AsyncIterator[str]:
    for block in blocks:
        yield block


def _request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/messages",
            "query_string": b"",
            "headers": [(key.encode("ascii"), value.encode("ascii")) for key, value in headers.items()],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def _base64_pdf(text: str | None) -> str:
    stream = b"" if text is None else f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n").encode("ascii")
    )
    return base64.b64encode(pdf).decode("ascii")


def test_messages_request_translates_system_tools_and_tool_results() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 4096,
            "system": [{"type": "text", "text": "Follow the repository rules."}],
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read a file",
                    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                }
            ],
            "tool_choice": {"type": "any", "disable_parallel_tool_use": True},
            "messages": [
                {"role": "user", "content": "Inspect app.py"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I will inspect it."},
                        {"type": "tool_use", "id": "toolu_read", "name": "read_file", "input": {"path": "app.py"}},
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_read", "content": "print('ok')"}],
                },
            ],
        },
        api_key=None,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert request.client_model == "gpt-5.6-terra"
    assert payload["instructions"] == "Follow the repository rules."
    assert payload["tool_choice"] == "required"
    assert payload["parallel_tool_calls"] is False
    assert payload["tools"] == [
        {
            "type": "function",
            "name": "read_file",
            "description": "Read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        }
    ]
    assert payload["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "Inspect app.py"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "I will inspect it."}]},
        {
            "type": "function_call",
            "call_id": "toolu_read",
            "name": "read_file",
            "arguments": '{"path":"app.py"}',
        },
        {"type": "function_call_output", "call_id": "toolu_read", "output": "print('ok')"},
    ]


def test_messages_request_maps_long_tool_names_and_call_ids_consistently() -> None:
    shared_name_prefix = "mcp__workspace__" + "a" * 70
    first_name = f"{shared_name_prefix}_first"
    second_name = f"{shared_name_prefix}_second"
    shared_call_prefix = "toolu_" + "b" * 70
    first_call_id = f"{shared_call_prefix}_first"
    second_call_id = f"{shared_call_prefix}_second"

    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 4096,
            "tools": [
                {"name": first_name, "input_schema": {"type": "object", "properties": {}}},
                {"name": second_name, "input_schema": {"type": "object", "properties": {}}},
            ],
            "tool_choice": {"type": "tool", "name": first_name},
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": first_call_id, "name": first_name, "input": {}},
                        {"type": "tool_use", "id": second_call_id, "name": second_name, "input": {}},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": first_call_id, "content": "first"},
                        {"type": "tool_result", "tool_use_id": second_call_id, "content": "second"},
                    ],
                },
            ],
        },
        api_key=None,
    )

    payload = request.responses.model_dump_for_forwarding()
    tool_names = [tool["name"] for tool in payload["tools"]]
    call_items = [item for item in payload["input"] if item.get("type") == "function_call"]
    output_items = [item for item in payload["input"] if item.get("type") == "function_call_output"]

    assert all(len(cast(str, name).encode("utf-8")) <= 64 for name in tool_names)
    assert tool_names[0] != tool_names[1]
    assert payload["tool_choice"] == {"type": "function", "name": tool_names[0]}
    assert [item["name"] for item in call_items] == tool_names
    assert all(len(cast(str, item["call_id"]).encode("utf-8")) <= 64 for item in call_items)
    assert call_items[0]["call_id"] != call_items[1]["call_id"]
    assert [item["call_id"] for item in output_items] == [item["call_id"] for item in call_items]
    assert request.tool_name_aliases == {tool_names[0]: first_name, tool_names[1]: second_name}


def test_messages_request_preserves_identifiers_at_exact_byte_limit() -> None:
    tool_name = "t" * 64
    call_id = "c" * 64
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [{"name": tool_name, "input_schema": {"type": "object", "properties": {}}}],
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": call_id, "name": tool_name, "input": {}}],
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": call_id, "content": "done"}],
                },
            ],
        },
        api_key=None,
    )

    payload = request.responses.model_dump_for_forwarding()
    call = next(item for item in payload["input"] if item.get("type") == "function_call")
    result = next(item for item in payload["input"] if item.get("type") == "function_call_output")
    assert payload["tools"][0]["name"] == tool_name
    assert call["name"] == tool_name
    assert call["call_id"] == call_id
    assert result["call_id"] == call_id


def test_messages_request_rejects_duplicate_tool_names_before_upstream() -> None:
    with pytest.raises(ClientPayloadError, match="Duplicate tool name"):
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 1024,
                "tools": [
                    {"name": "duplicate_tool", "input_schema": {"type": "object", "properties": {}}},
                    {"name": "duplicate_tool", "input_schema": {"type": "object", "properties": {}}},
                ],
                "messages": [{"role": "user", "content": "hi"}],
            },
            api_key=None,
        )


def test_messages_request_maps_tool_reference_history_to_native_tool_search_items() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 4096,
            "tools": [
                {
                    "name": "ToolSearch",
                    "description": "Load deferred tools",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
                {
                    "name": "mcp__workspace__web_fetch",
                    "description": "Fetch a page",
                    "input_schema": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                    "defer_loading": True,
                },
                {
                    "name": "mcp__workspace__web_search",
                    "description": "Search the web",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                    "defer_loading": True,
                },
            ],
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_tool_search",
                            "name": "ToolSearch",
                            "input": {"query": "select:mcp__workspace__web_fetch"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_tool_search",
                            "content": [
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"},
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_search"},
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"},
                            ],
                        }
                    ],
                },
                {"role": "user", "content": "/schedule"},
            ],
        },
        api_key=None,
        claude_desktop=True,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert payload["input"] == [
        {
            "type": "tool_search_call",
            "call_id": "call_tool_search",
            "arguments": {"query": "select:mcp__workspace__web_fetch"},
            "execution": "client",
            "status": "completed",
        },
        {
            "type": "tool_search_output",
            "call_id": "call_tool_search",
            "tools": [
                {
                    "type": "function",
                    "name": "mcp__workspace__web_fetch",
                    "description": "Fetch a page",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                },
                {
                    "type": "function",
                    "name": "mcp__workspace__web_search",
                    "description": "Search the web",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            ],
            "execution": "client",
            "status": "completed",
        },
        {"role": "user", "content": [{"type": "input_text", "text": "/schedule"}]},
    ]


def test_messages_request_preserves_tool_reference_for_an_ordinary_tool_result() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [
                {
                    "name": "custom_catalog",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "call_catalog", "name": "custom_catalog", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_catalog",
                            "content": [
                                {"type": "text", "text": "Found:"},
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"},
                            ],
                        }
                    ],
                },
            ],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_catalog",
        "output": (
            '[{"text":"Found:","type":"text"},{"tool_name":"mcp__workspace__web_fetch","type":"tool_reference"}]'
        ),
    }


def test_messages_request_preserves_ordered_text_and_image_tool_result() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [{"name": "take_screenshot", "input_schema": {"type": "object", "properties": {}}}],
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "call_screenshot", "name": "take_screenshot", "input": {}}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_screenshot",
                            "content": [
                                {"type": "text", "text": "Before image"},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": "aW1hZ2UtYnl0ZXM=",
                                    },
                                },
                                {"type": "text", "text": "After image"},
                            ],
                        }
                    ],
                },
            ],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_screenshot",
        "output": [
            {"type": "input_text", "text": "Before image"},
            {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2UtYnl0ZXM="},
            {"type": "input_text", "text": "After image"},
        ],
    }


def test_messages_request_extracts_tool_result_documents_and_preserves_search_results() -> None:
    search_result = {
        "type": "search_result",
        "source": "kb://runbook/capacity",
        "title": "Capacity runbook",
        "content": [{"type": "text", "text": "Use bounded retries."}],
        "citations": {"enabled": True},
        "cache_control": {"type": "ephemeral"},
    }
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [
                {"name": "read_document", "input_schema": {"type": "object", "properties": {}}},
                {"name": "search_knowledge", "input_schema": {"type": "object", "properties": {}}},
            ],
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "call_document", "name": "read_document", "input": {}},
                        {"type": "tool_use", "id": "call_search", "name": "search_knowledge", "input": {}},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_document",
                            "content": [
                                {
                                    "type": "document",
                                    "title": "notes.txt",
                                    "source": {
                                        "type": "text",
                                        "media_type": "text/plain",
                                        "data": "inline document text",
                                    },
                                }
                            ],
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_search",
                            "content": [search_result],
                        },
                    ],
                },
            ],
        },
        api_key=None,
    )

    outputs = [
        item
        for item in request.responses.model_dump_for_forwarding()["input"]
        if item.get("type") == "function_call_output"
    ]
    assert outputs == [
        {
            "type": "function_call_output",
            "call_id": "call_document",
            "output": (
                "[Document: notes.txt; media_type=text/plain]\n"
                "inline document text\n"
                "[End document: notes.txt]"
            ),
        },
        {
            "type": "function_call_output",
            "call_id": "call_search",
            "output": json.dumps(search_result, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        },
    ]


def test_messages_request_extracts_pdf_inside_tool_result() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [{"name": "read_pdf", "input_schema": {"type": "object", "properties": {}}}],
            "messages": [
                {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "call_pdf", "name": "read_pdf", "input": {}}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_pdf",
                            "content": [
                                {
                                    "type": "document",
                                    "title": "result.pdf",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf",
                                        "data": _base64_pdf("Tool PDF"),
                                    },
                                }
                            ],
                        }
                    ],
                },
            ],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["input"][-1]["output"] == (
        "[Document: result.pdf; media_type=application/pdf]\n"
        "[Page 1]\nTool PDF\n"
        "[End document: result.pdf]"
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            [{"type": "search_result", "source": "https://example.com", "title": "Example", "content": []}],
            "search_result content must be a non-empty array",
        ),
        ([{"type": "audio", "source": {"type": "base64", "data": "YQ=="}}], "Unsupported tool_result"),
    ],
)
def test_messages_request_rejects_malformed_or_unknown_structured_tool_result(
    content: list[JsonValue],
    message: str,
) -> None:
    with pytest.raises(ClientPayloadError, match=message) as exc_info:
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 1024,
                "tools": [{"name": "structured_tool", "input_schema": {"type": "object", "properties": {}}}],
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "id": "call_structured", "name": "structured_tool", "input": {}}
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": "call_structured", "content": content}
                        ],
                    },
                ],
            },
            api_key=None,
        )

    assert exc_info.value.param is not None
    assert exc_info.value.param.startswith("messages.1.content.0.content.0")


def test_messages_request_rejects_unknown_native_tool_reference() -> None:
    with pytest.raises(ClientPayloadError, match="Tool reference 'missing_tool' not found"):
        anthropic_messages.to_responses_request(
            {
                "model": "claude-opus-4-8",
                "max_tokens": 1024,
                "tools": [
                    {
                        "name": "ToolSearch",
                        "input_schema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    }
                ],
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "call_tool_search",
                                "name": "ToolSearch",
                                "input": {"query": "missing_tool"},
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "call_tool_search",
                                "content": [{"type": "tool_reference", "tool_name": "missing_tool"}],
                            }
                        ],
                    },
                ],
            },
            api_key=None,
            claude_desktop=True,
        )


@pytest.mark.parametrize(
    ("tool_type", "tool_name"),
    [
        ("web_search_20250305", "web_search"),
        ("web_search_20260209", "web_search"),
        ("web_search_20260318", "web_search"),
        ("web_fetch_20250910", "web_fetch"),
        ("web_fetch_20260209", "web_fetch"),
        ("web_fetch_20260309", "web_fetch"),
        ("web_fetch_20260318", "web_fetch"),
    ],
)
def test_messages_request_maps_supported_web_server_tool(tool_type: str, tool_name: str) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [{"type": tool_type, "name": tool_name}],
            "messages": [{"role": "user", "content": "Use the web."}],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [{"type": "web_search"}]


def test_messages_request_deduplicates_web_tools_and_preserves_client_function() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [
                {"type": "web_search_20260318", "name": "web_search", "max_uses": 3},
                {
                    "name": "read_file",
                    "description": "Read a file",
                    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
                {"type": "web_fetch_20260318", "name": "web_fetch", "max_uses": 5},
            ],
            "messages": [{"role": "user", "content": "Find and read the documentation."}],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [
        {"type": "web_search"},
        {
            "type": "function",
            "name": "read_file",
            "description": "Read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        },
    ]


def test_messages_request_preserves_web_server_tool_controls() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [
                {
                    "type": "web_search_20260318",
                    "name": "web_search",
                    "allowed_domains": ["python.org", "docs.python.org"],
                    "user_location": {
                        "type": "approximate",
                        "city": "Kolkata",
                        "region": "West Bengal",
                        "country": "IN",
                        "timezone": "Asia/Kolkata",
                    },
                    "max_uses": 3,
                    "allowed_callers": ["direct"],
                    "response_inclusion": "full",
                }
            ],
            "messages": [{"role": "user", "content": "Search Python documentation."}],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [
        {
            "type": "web_search",
            "filters": {"allowed_domains": ["python.org", "docs.python.org"]},
            "user_location": {
                "type": "approximate",
                "city": "Kolkata",
                "region": "West Bengal",
                "country": "IN",
                "timezone": "Asia/Kolkata",
            },
        }
    ]


def test_claude_desktop_omits_unsupported_blocked_domains() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-sonnet-5",
            "max_tokens": 1024,
            "tools": [
                {
                    "type": "web_search_20260318",
                    "name": "web_search",
                    "blocked_domains": ["example.com"],
                }
            ],
            "messages": [{"role": "user", "content": "Search the web."}],
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [{"type": "web_search"}]


def _workspace_web_fetch_tool(*, defer_loading: bool = False) -> dict[str, JsonValue]:
    tool: dict[str, JsonValue] = {
        "name": "mcp__workspace__web_fetch",
        "description": "Fetch a URL through the Cowork host workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout_ms": {"type": "integer"},
            },
            "required": ["url"],
        },
    }
    if defer_loading:
        tool["defer_loading"] = True
    return tool


@pytest.mark.parametrize("defer_loading", [False, True])
def test_claude_desktop_routes_workspace_web_fetch_for_public_url(defer_loading: bool) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "tools": [_workspace_web_fetch_tool(defer_loading=defer_loading)],
            "tool_choice": {"type": "tool", "name": "mcp__workspace__web_fetch"},
            "messages": [
                {
                    "role": "user",
                    "content": "Fetch https://claude.com/docs and summarize the documentation.",
                }
            ],
        },
        api_key=None,
        claude_desktop=True,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["tool_choice"] == {"type": "web_search"}


@pytest.mark.parametrize("defer_loading", [False, True])
def test_claude_desktop_accepts_hosted_workspace_alias_in_tool_search_history(defer_loading: bool) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "tools": [
                {
                    "name": "ToolSearch",
                    "description": "Load deferred tools",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
                _workspace_web_fetch_tool(defer_loading=defer_loading),
            ],
            "tool_choice": {"type": "tool", "name": "mcp__workspace__web_fetch"},
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_tool_search",
                            "name": "ToolSearch",
                            "input": {"query": "select:mcp__workspace__web_fetch"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_tool_search",
                            "content": [{"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"}],
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": "Fetch https://example.com and return only its page title.",
                },
            ],
        },
        api_key=None,
        claude_desktop=True,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert payload["tools"] == [
        {
            "type": "function",
            "name": "ToolSearch",
            "description": "Load deferred tools",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        },
        {"type": "web_search"},
    ]
    assert payload["tool_choice"] == {"type": "web_search"}
    assert payload["input"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Fetch https://example.com and return only its page title.",
                }
            ],
        }
    ]


def test_claude_desktop_filters_hosted_alias_from_mixed_tool_search_history() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "tools": [
                {
                    "name": "ToolSearch",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
                _workspace_web_fetch_tool(),
                {
                    "name": "read_schedule",
                    "description": "Read the local schedule",
                    "input_schema": {
                        "type": "object",
                        "properties": {"date": {"type": "string"}},
                    },
                    "defer_loading": True,
                },
            ],
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_tool_search",
                            "name": "ToolSearch",
                            "input": {"query": "select:mcp__workspace__web_fetch,read_schedule"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_tool_search",
                            "content": [
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"},
                                {"type": "tool_reference", "tool_name": "read_schedule"},
                            ],
                        }
                    ],
                },
                {"role": "user", "content": "Check https://example.com before reading the schedule."},
            ],
        },
        api_key=None,
        claude_desktop=True,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert [item.get("type", item.get("role")) for item in payload["input"]] == [
        "tool_search_call",
        "tool_search_output",
        "user",
    ]
    assert payload["input"][1]["tools"] == [
        {
            "type": "function",
            "name": "read_schedule",
            "description": "Read the local schedule",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string"}},
            },
        }
    ]


def test_claude_desktop_deduplicates_workspace_fetch_alias_with_official_controls() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "tools": [
                _workspace_web_fetch_tool(),
                {
                    "type": "web_fetch_20260318",
                    "name": "web_fetch",
                    "allowed_domains": ["claude.com"],
                },
            ],
            "messages": [{"role": "user", "content": "Read https://claude.com/docs."}],
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [
        {"type": "web_search", "filters": {"allowed_domains": ["claude.com"]}}
    ]


@pytest.mark.parametrize(
    ("claude_desktop", "message", "defer_loading"),
    [
        (False, "Fetch https://claude.com/docs.", False),
        (True, "Fetch http://127.0.0.1:8080/docs.", False),
        (True, "Fetch the documentation URL when one becomes available.", False),
        (True, "Fetch http://127.0.0.1:8080/docs.", True),
    ],
)
def test_workspace_web_fetch_remains_client_tool_outside_public_desktop_case(
    claude_desktop: bool,
    message: str,
    defer_loading: bool,
) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8" if claude_desktop else "gpt-5.6-sol",
            "max_tokens": 1024,
            "tools": [_workspace_web_fetch_tool(defer_loading=defer_loading)],
            "messages": [{"role": "user", "content": message}],
        },
        api_key=None,
        claude_desktop=claude_desktop,
    )

    assert request.responses.model_dump_for_forwarding()["tools"] == [
        {
            "type": "function",
            "name": "mcp__workspace__web_fetch",
            "description": "Fetch a URL through the Cowork host workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout_ms": {"type": "integer"},
                },
                "required": ["url"],
            },
        }
    ]


@pytest.mark.parametrize(
    "messages",
    [
        [
            {"role": "user", "content": "Earlier, inspect https://example.com."},
            {"role": "assistant", "content": "I can do that."},
            {"role": "user", "content": "Now fetch http://127.0.0.1:8080/health instead."},
        ],
        [
            {
                "role": "user",
                "content": "Compare https://example.com with http://127.0.0.1:8080/health.",
            }
        ],
    ],
)
def test_workspace_web_fetch_keeps_client_tool_when_latest_targets_include_local_url(
    messages: list[JsonValue],
) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "tools": [_workspace_web_fetch_tool(defer_loading=True)],
            "messages": messages,
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.responses.model_dump_for_forwarding()["tools"][0]["type"] == "function"


@pytest.mark.parametrize("tool_name", ["web_search", "web_fetch"])
def test_messages_request_maps_forced_web_tool_choice(tool_name: str) -> None:
    tool_type = "web_search_20260318" if tool_name == "web_search" else "web_fetch_20260318"
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "tools": [{"type": tool_type, "name": tool_name}],
            "tool_choice": {"type": "tool", "name": tool_name, "disable_parallel_tool_use": True},
            "messages": [{"role": "user", "content": "Use the requested web tool."}],
        },
        api_key=None,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert payload["tool_choice"] == {"type": "web_search"}
    assert payload["parallel_tool_calls"] is False


@pytest.mark.parametrize(
    ("tools", "message", "param"),
    [
        (
            [{"type": "web_search_20990101", "name": "web_search"}],
            "Unsupported Anthropic web server-tool type",
            "tools.0.type",
        ),
        (
            [{"type": "web_search_20260318", "name": "web_fetch"}],
            "must use name 'web_search'",
            "tools.0.name",
        ),
        (
            [{"type": "web_fetch_20260318", "name": "web_fetch", "blocked_domains": ["example.com"]}],
            "blocked_domains",
            "tools.0.blocked_domains",
        ),
        (
            [{"type": "web_search_20260318", "name": "web_search", "allowed_domains": [1]}],
            "non-empty strings",
            "tools.0.allowed_domains",
        ),
        (
            [
                {"type": "web_search_20260318", "name": "web_search", "allowed_domains": ["python.org"]},
                {"type": "web_fetch_20260318", "name": "web_fetch", "allowed_domains": ["openai.com"]},
            ],
            "conflicting hosted-tool controls",
            "tools.1",
        ),
    ],
)
def test_messages_request_rejects_unsafe_web_server_tool(
    tools: list[JsonValue],
    message: str,
    param: str,
) -> None:
    with pytest.raises(ClientPayloadError, match=message) as exc_info:
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 1024,
                "tools": tools,
                "messages": [{"role": "user", "content": "Use the web."}],
            },
            api_key=None,
        )

    assert exc_info.value.param == param


def test_messages_request_translates_base64_image_and_extracts_pdf_document() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Read these attachments."},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "aW1hZ2UtYnl0ZXM=",
                            },
                        },
                        {
                            "type": "document",
                            "title": "notes.pdf",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": _base64_pdf("Hello PDF"),
                            },
                        },
                    ],
                }
            ],
        },
        api_key=None,
    )

    assert request.responses.model_dump_for_forwarding()["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Read these attachments."},
                {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2UtYnl0ZXM="},
                {
                    "type": "input_text",
                    "text": (
                        "[Document: notes.pdf; media_type=application/pdf]\n"
                        "[Page 1]\nHello PDF\n"
                        "[End document: notes.pdf]"
                    ),
                },
            ],
        }
    ]


@pytest.mark.parametrize(
    ("media_type", "title", "raw", "expected"),
    [
        ("text/plain", "notes.txt", "hello UTF-8 \u2713".encode(), "hello UTF-8 \u2713"),
        ("text/csv", "rows.csv", b"name,value\na,1\n", "name,value\na,1\n"),
    ],
)
def test_messages_request_extracts_utf8_text_documents(
    media_type: str,
    title: str,
    raw: bytes,
    expected: str,
) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 128,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "title": title,
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(raw).decode("ascii"),
                            },
                        }
                    ],
                }
            ],
        },
        api_key=None,
    )

    content = request.responses.model_dump_for_forwarding()["input"][0]["content"]
    assert content == [
        {
            "type": "input_text",
            "text": f"[Document: {title}; media_type={media_type}]\n{expected}\n[End document: {title}]",
        }
    ]


def test_messages_request_rejects_scanned_pdf_without_extractable_text() -> None:
    with pytest.raises(ClientPayloadError, match="no extractable text"):
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 128,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": _base64_pdf(None),
                                },
                            }
                        ],
                    }
                ],
            },
            api_key=None,
        )


def test_messages_request_rejects_document_url_before_upstream() -> None:
    with pytest.raises(ClientPayloadError, match="provide a base64 document"):
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 128,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {"type": "url", "url": "https://example.com/file.pdf"},
                            }
                        ],
                    }
                ],
            },
            api_key=None,
        )


def test_messages_request_rejects_invalid_attachment_base64() -> None:
    with pytest.raises(ValueError, match="valid base64"):
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": "not base64!",
                                },
                            }
                        ],
                    }
                ],
            },
            api_key=None,
        )


def test_messages_request_uses_stable_cache_affinity_for_marked_prefix() -> None:
    common_payload: dict[str, JsonValue] = {
        "model": "gpt-5.6-terra",
        "max_tokens": 1024,
        "system": [{"type": "text", "text": "Project rules", "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": "Variable question"}],
    }
    first = anthropic_messages.to_responses_request(common_payload, api_key=None)
    second = anthropic_messages.to_responses_request(
        {**common_payload, "messages": [{"role": "user", "content": "Another question"}]},
        api_key=None,
    )

    assert first.responses.prompt_cache_key is not None
    assert first.responses.prompt_cache_key == second.responses.prompt_cache_key
    assert first.responses.prompt_cache_key.startswith("anthropic-cache-")


def test_messages_request_preserves_context_management_as_an_auto_compaction_signal() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 4096,
            "context_management": {
                "edits": [{"type": "clear_tool_uses_20250919", "trigger": {"type": "input_tokens", "value": 1000}}]
            },
            "messages": [{"role": "user", "content": "Keep the thread within context."}],
        },
        api_key=None,
    )

    assert request.max_output_tokens == 4096
    assert request.context_management_requested is True


def test_claude_model_label_requires_explicit_key_mapping() -> None:
    payload = {"model": "claude-sonnet-4-6", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hi"}]}
    with pytest.raises(ValueError, match="enforced model"):
        anthropic_messages.to_responses_request(payload, api_key=None)

    api_key = cast(ApiKeyData, SimpleNamespace(enforced_model="gpt-5.6-terra"))
    request = anthropic_messages.to_responses_request(payload, api_key=api_key)
    assert request.client_model == "claude-sonnet-4-6"
    assert request.responses.model == "gpt-5.6-terra"


@pytest.mark.parametrize(
    ("client_model", "effective_model"),
    [
        ("opus", "gpt-5.6-sol"),
        ("claude-opus-4-8", "gpt-5.6-sol"),
        ("sonnet", "gpt-5.6-terra"),
        ("claude-sonnet-5", "gpt-5.6-terra"),
    ],
)
def test_claude_desktop_model_profile_routes_opus_and_sonnet(
    client_model: str,
    effective_model: str,
) -> None:
    request = anthropic_messages.to_responses_request(
        {"model": client_model, "max_tokens": 1024, "messages": [{"role": "user", "content": "Hi"}]},
        api_key=None,
        claude_desktop=True,
    )

    assert request.client_model == client_model
    assert request.responses.model == effective_model
    assert request.responses.reasoning is not None
    assert request.responses.reasoning.effort == "high"


def test_claude_desktop_requests_encrypted_reasoning_continuity() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Think carefully."}],
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.responses.reasoning is not None
    assert request.responses.reasoning.summary == "auto"
    assert request.responses.include == ["reasoning.encrypted_content"]


def test_assistant_thinking_signature_replays_as_opaque_reasoning_item() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "SENTINEL_VISIBLE_SUMMARY_MUST_NOT_REPLAY",
                            "signature": "SENTINEL_OPAQUE_ENCRYPTED_REASONING",
                        },
                        {"type": "text", "text": "Prior answer."},
                    ],
                },
                {"role": "user", "content": "Continue."},
            ],
        },
        api_key=None,
    )

    payload = request.responses.model_dump_for_forwarding()
    assert payload["input"][0] == {
        "type": "reasoning",
        "encrypted_content": "SENTINEL_OPAQUE_ENCRYPTED_REASONING",
        "summary": [],
        "content": None,
    }
    assert "SENTINEL_VISIBLE_SUMMARY_MUST_NOT_REPLAY" not in json.dumps(payload["input"])


@pytest.mark.parametrize(
    "block",
    [
        {"type": "thinking", "thinking": "summary"},
        {"type": "thinking", "thinking": "summary", "signature": ""},
        {"type": "thinking", "thinking": 7, "signature": "opaque"},
    ],
)
def test_assistant_thinking_rejects_malformed_state(block: dict[str, JsonValue]) -> None:
    with pytest.raises(ClientPayloadError, match="thinking blocks require"):
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 1024,
                "messages": [{"role": "assistant", "content": [block]}],
            },
            api_key=None,
        )


def test_claude_desktop_sonnet_uses_codexneo_fallback_effort() -> None:
    request = anthropic_messages.to_responses_request(
        {"model": "claude-sonnet-5", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hi"}]},
        api_key=None,
        claude_desktop=True,
        claude_desktop_sonnet_reasoning_effort="xhigh",
    )

    assert request.responses.model == "gpt-5.6-terra"
    assert request.responses.reasoning is not None
    assert request.responses.reasoning.effort == "xhigh"


def test_claude_desktop_sonnet_explicit_effort_overrides_codexneo_fallback() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-sonnet-5",
            "max_tokens": 1024,
            "output_config": {"effort": "medium"},
            "messages": [{"role": "user", "content": "Hi"}],
        },
        api_key=None,
        claude_desktop=True,
        claude_desktop_sonnet_reasoning_effort="max",
    )

    assert request.responses.reasoning is not None
    assert request.responses.reasoning.effort == "medium"


def test_claude_desktop_token_count_reuses_messages_model_and_input_validation() -> None:
    request = anthropic_messages.to_responses_token_count_request(
        {
            "model": "claude-opus-4-8",
            "system": "Be concise.",
            "messages": [{"role": "user", "content": "Count these tokens."}],
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.client_model == "claude-opus-4-8"
    assert request.responses.model == "gpt-5.6-sol"
    assert request.responses.instructions == "Be concise."
    assert request.responses.input == [
        {"role": "user", "content": [{"type": "input_text", "text": "Count these tokens."}]}
    ]


@pytest.mark.parametrize(
    ("desktop_effort", "expected_effort"),
    [
        ("low", "low"),
        ("medium", "medium"),
        ("high", "high"),
        ("extra", "xhigh"),
        ("xhigh", "xhigh"),
        ("max", "max"),
    ],
)
def test_claude_desktop_output_config_effort_maps_to_responses_reasoning(
    desktop_effort: str,
    expected_effort: str,
) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "output_config": {"effort": desktop_effort},
            "messages": [{"role": "user", "content": "Hi"}],
        },
        api_key=None,
        claude_desktop=True,
    )

    assert request.responses.reasoning is not None
    assert request.responses.reasoning.effort == expected_effort


def test_non_desktop_messages_do_not_apply_desktop_effort_defaults() -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "output_config": {"effort": "max"},
            "messages": [{"role": "user", "content": "Hi"}],
        },
        api_key=None,
    )

    assert request.responses.reasoning is None


@pytest.mark.parametrize("role", ["system", "developer"])
def test_claude_desktop_accepts_beta_instruction_roles(role: str) -> None:
    request = anthropic_messages.to_responses_request(
        {
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "messages": [
                {"role": role, "content": "Use concise answers."},
                {"role": "user", "content": "Hi"},
            ],
        },
        api_key=None,
        claude_desktop=True,
    )

    forwarded = request.responses.model_dump_for_forwarding()
    assert forwarded["instructions"] == "Use concise answers."
    assert forwarded["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]},
    ]


def test_non_desktop_messages_reject_beta_instruction_roles() -> None:
    with pytest.raises(ValueError, match="Messages role must be 'user' or 'assistant'"):
        anthropic_messages.to_responses_request(
            {
                "model": "gpt-5.6-terra",
                "max_tokens": 1024,
                "messages": [{"role": "developer", "content": "Use concise answers."}],
            },
            api_key=None,
        )


def test_completed_responses_payload_becomes_anthropic_message() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_123",
            "status": "completed",
            "usage": {"input_tokens": 12, "output_tokens": 7},
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "I found it."}]},
                {"type": "function_call", "call_id": "toolu_patch", "name": "apply_patch", "arguments": '{"path":"x"}'},
            ],
        },
        client_model="claude-sonnet-4-6",
    )

    assert message == {
        "id": "resp_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "I found it."},
            {"type": "tool_use", "id": "toolu_patch", "name": "apply_patch", "input": {"path": "x"}},
        ],
        "model": "claude-sonnet-4-6",
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }


def test_completed_responses_payload_restores_original_tool_name() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_alias",
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "toolu_alias",
                    "name": "mcp__short_0123456789abcdef",
                    "arguments": "{}",
                }
            ],
        },
        client_model="claude-sonnet-5",
        tool_name_aliases={"mcp__short_0123456789abcdef": "mcp__workspace__sentinel_original_tool"},
    )

    assert message["content"] == [
        {
            "type": "tool_use",
            "id": "toolu_alias",
            "name": "mcp__workspace__sentinel_original_tool",
            "input": {},
        }
    ]


def test_completed_responses_payload_preserves_reasoning_summary_and_signature() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_reasoning",
            "status": "completed",
            "output": [
                {
                    "id": "rs_reasoning",
                    "type": "reasoning",
                    "encrypted_content": "SENTINEL_ENCRYPTED_REASONING_OUTPUT",
                    "summary": [
                        {"type": "summary_text", "text": "First summary."},
                        {"type": "summary_text", "text": "Second summary."},
                    ],
                },
                {"type": "message", "content": [{"type": "output_text", "text": "Final answer."}]},
            ],
        },
        client_model="claude-opus-4-8",
    )

    assert message["content"] == [
        {
            "type": "thinking",
            "thinking": "First summary.\n\nSecond summary.",
            "signature": "SENTINEL_ENCRYPTED_REASONING_OUTPUT",
        },
        {"type": "text", "text": "Final answer."},
    ]


def test_completed_responses_payload_preserves_signature_only_reasoning() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_signature_only",
            "status": "completed",
            "output": [
                {
                    "id": "rs_signature_only",
                    "type": "reasoning",
                    "encrypted_content": "SENTINEL_SIGNATURE_ONLY",
                    "summary": [],
                }
            ],
        },
        client_model="claude-opus-4-8",
    )

    assert message["content"] == [{"type": "thinking", "thinking": "", "signature": "SENTINEL_SIGNATURE_ONLY"}]


def test_completed_responses_payload_keeps_text_fallback_for_incomplete_web_search_data() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_web",
            "status": "completed",
            "usage": {"input_tokens": 8, "output_tokens": 5},
            "output": [
                {
                    "id": "ws_web",
                    "type": "web_search_call",
                    "status": "completed",
                    "action": {"type": "search", "queries": ["Python documentation"]},
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Python documentation is at python.org."}],
                },
            ],
        },
        client_model="claude-sonnet-5",
    )

    assert message["content"] == [{"type": "text", "text": "Python documentation is at python.org."}]
    assert message["stop_reason"] == "end_turn"
    assert message["usage"] == {"input_tokens": 8, "output_tokens": 5}


def test_completed_responses_payload_translates_exact_web_results_and_citations() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_web_exact",
            "status": "completed",
            "usage": {"input_tokens": 8, "output_tokens": 5},
            "output": [
                {
                    "id": "srvtoolu_web",
                    "type": "web_search_call",
                    "status": "completed",
                    "action": {"type": "search", "query": "Python documentation"},
                    "results": [
                        {
                            "type": "web_search_result",
                            "url": "https://docs.python.org/3/",
                            "title": "Python documentation",
                            "encrypted_content": "enc_result_1",
                            "page_age": "2026-07-01",
                        }
                    ],
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Use the Python documentation.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://docs.python.org/3/",
                                    "title": "Python documentation",
                                    "encrypted_index": "enc_index_1",
                                    "cited_text": "Python documentation",
                                },
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/public-only",
                                    "title": "Public only",
                                    "start_index": 0,
                                    "end_index": 3,
                                },
                            ],
                        }
                    ],
                },
            ],
        },
        client_model="claude-sonnet-5",
    )

    assert message["content"] == [
        {
            "type": "server_tool_use",
            "id": "srvtoolu_web",
            "name": "web_search",
            "input": {"query": "Python documentation"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": "srvtoolu_web",
            "content": [
                {
                    "type": "web_search_result",
                    "url": "https://docs.python.org/3/",
                    "title": "Python documentation",
                    "encrypted_content": "enc_result_1",
                    "page_age": "2026-07-01",
                }
            ],
        },
        {
            "type": "text",
            "text": "Use the Python documentation.",
            "citations": [
                {
                    "type": "web_search_result_location",
                    "url": "https://docs.python.org/3/",
                    "title": "Python documentation",
                    "encrypted_index": "enc_index_1",
                    "cited_text": "Python documentation",
                }
            ],
        },
    ]


def test_completed_responses_payload_reports_only_upstream_cache_usage() -> None:
    message = anthropic_messages.message_from_responses(
        {
            "id": "resp_cached",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 4,
                "cache_write_tokens": 80,
                "input_tokens_details": {"cached_tokens": 60},
            },
            "output": [],
        },
        client_model="gpt-5.6-terra",
    )

    assert message["usage"] == {
        "input_tokens": 100,
        "output_tokens": 4,
        "cache_creation_input_tokens": 80,
        "cache_read_input_tokens": 60,
    }


@pytest.mark.asyncio
async def test_text_stream_is_converted_once_and_terminated() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_text"}}),
        _sse(
            {
                "type": "response.content_part.added",
                "output_index": 0,
                "content_index": 0,
                "item_id": "msg_text",
                "part": {"type": "output_text", "text": ""},
            }
        ),
        _sse(
            {
                "type": "response.output_text.delta",
                "output_index": 0,
                "content_index": 0,
                "item_id": "msg_text",
                "delta": "hello",
            }
        ),
        _sse({"type": "response.content_part.done", "output_index": 0, "content_index": 0, "item_id": "msg_text"}),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {"type": "message", "content": [{"type": "output_text", "text": "hello"}]},
            }
        ),
        _sse(
            {
                "type": "response.completed",
                "response": {"id": "resp_text", "usage": {"input_tokens": 2, "output_tokens": 3}},
            }
        ),
    ]

    events = [
        parse_sse_data_json(event)
        async for event in anthropic_messages.iter_messages_events(_stream(*blocks), client_model="gpt-5.6-terra")
    ]
    parsed = [event for event in events if event is not None]
    assert [event["type"] for event in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert parsed[2]["delta"] == {"type": "text_delta", "text": "hello"}
    assert parsed[4]["delta"]["stop_reason"] == "end_turn"


@pytest.mark.asyncio
async def test_web_search_stream_ignores_hosted_lifecycle_and_returns_text() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_web_stream"}}),
        _sse(
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {"id": "ws_stream", "type": "web_search_call", "status": "in_progress"},
            }
        ),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "ws_stream",
                    "type": "web_search_call",
                    "status": "completed",
                    "action": {"type": "open_page", "url": "https://www.python.org/"},
                },
            }
        ),
        _sse(
            {
                "type": "response.output_text.delta",
                "output_index": 1,
                "content_index": 0,
                "item_id": "msg_web_stream",
                "delta": "Python",
            }
        ),
        _sse(
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_web_stream",
                    "usage": {"input_tokens": 4, "output_tokens": 2},
                },
            }
        ),
    ]

    events = [
        parse_sse_data_json(event)
        async for event in anthropic_messages.iter_messages_events(
            _stream(*blocks),
            client_model="claude-sonnet-5",
        )
    ]
    parsed = [event for event in events if event is not None]
    assert [event["type"] for event in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert parsed[2]["delta"] == {"type": "text_delta", "text": "Python"}
    assert parsed[4]["usage"] == {"output_tokens": 2}


@pytest.mark.asyncio
async def test_web_search_stream_translates_exact_results_and_citations() -> None:
    citation = {
        "type": "url_citation",
        "url": "https://docs.python.org/3/",
        "title": "Python documentation",
        "encrypted_index": "enc_index_stream",
        "cited_text": "Python documentation",
    }
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_web_exact_stream"}}),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "srvtoolu_stream",
                    "type": "web_search_call",
                    "status": "completed",
                    "action": {"type": "search", "query": "Python documentation"},
                    "results": [
                        {
                            "url": "https://docs.python.org/3/",
                            "title": "Python documentation",
                            "encrypted_content": "enc_result_stream",
                        }
                    ],
                },
            }
        ),
        _sse(
            {
                "type": "response.content_part.added",
                "output_index": 1,
                "content_index": 0,
                "item_id": "msg_web_exact_stream",
                "part": {"type": "output_text", "text": ""},
            }
        ),
        _sse(
            {
                "type": "response.output_text.delta",
                "output_index": 1,
                "content_index": 0,
                "item_id": "msg_web_exact_stream",
                "delta": "Python",
            }
        ),
        _sse(
            {
                "type": "response.content_part.done",
                "output_index": 1,
                "content_index": 0,
                "item_id": "msg_web_exact_stream",
                "part": {"type": "output_text", "text": "Python", "annotations": [citation]},
            }
        ),
        _sse(
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_web_exact_stream",
                    "usage": {"input_tokens": 4, "output_tokens": 2},
                },
            }
        ),
    ]

    parsed = [
        event
        for event in [
            parse_sse_data_json(event)
            async for event in anthropic_messages.iter_messages_events(
                _stream(*blocks),
                client_model="claude-sonnet-5",
            )
        ]
        if event is not None
    ]
    assert [event["type"] for event in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_stop",
        "content_block_start",
        "content_block_stop",
        "content_block_start",
        "content_block_delta",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert parsed[1]["content_block"]["type"] == "server_tool_use"
    assert parsed[3]["content_block"]["type"] == "web_search_tool_result"
    assert parsed[7]["delta"] == {
        "type": "citations_delta",
        "citation": {
            "type": "web_search_result_location",
            "url": "https://docs.python.org/3/",
            "title": "Python documentation",
            "encrypted_index": "enc_index_stream",
            "cited_text": "Python documentation",
        },
    }


@pytest.mark.asyncio
async def test_final_only_multi_part_text_stream_keeps_each_content_block() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_parts"}}),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "msg_parts",
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "first"},
                        {"type": "output_text", "text": "second"},
                    ],
                },
            }
        ),
        _sse({"type": "response.completed", "response": {"id": "resp_parts"}}),
    ]

    events = [
        parse_sse_data_json(event)
        async for event in anthropic_messages.iter_messages_events(_stream(*blocks), client_model="gpt-5.6-terra")
    ]
    parsed = [event for event in events if event is not None]
    assert [event["type"] for event in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert [parsed[2]["delta"]["text"], parsed[5]["delta"]["text"]] == ["first", "second"]


@pytest.mark.asyncio
async def test_tool_stream_uses_input_json_deltas() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_tool"}}),
        _sse(
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {"id": "fc_tool", "type": "function_call", "call_id": "toolu_run", "name": "run_command"},
            }
        ),
        _sse(
            {
                "type": "response.function_call_arguments.delta",
                "output_index": 0,
                "item_id": "fc_tool",
                "delta": '{"command":"pwd"}',
            }
        ),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "fc_tool",
                    "type": "function_call",
                    "call_id": "toolu_run",
                    "name": "run_command",
                    "arguments": '{"command":"pwd"}',
                },
            }
        ),
        _sse({"type": "response.completed", "response": {"id": "resp_tool", "usage": {"output_tokens": 4}}}),
    ]

    events = [
        parse_sse_data_json(event)
        async for event in anthropic_messages.iter_messages_events(_stream(*blocks), client_model="gpt-5.6-terra")
    ]
    parsed = [event for event in events if event is not None]
    assert [event["type"] for event in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert parsed[1]["content_block"] == {"type": "tool_use", "id": "toolu_run", "name": "run_command", "input": {}}
    assert parsed[2]["delta"] == {"type": "input_json_delta", "partial_json": '{"command":"pwd"}'}
    assert parsed[4]["delta"]["stop_reason"] == "tool_use"


@pytest.mark.asyncio
async def test_tool_stream_restores_original_tool_name() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_tool_alias"}}),
        _sse(
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": "fc_alias",
                    "type": "function_call",
                    "call_id": "toolu_alias",
                    "name": "mcp__short_0123456789abcdef",
                },
            }
        ),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "fc_alias",
                    "type": "function_call",
                    "call_id": "toolu_alias",
                    "name": "mcp__short_0123456789abcdef",
                    "arguments": "{}",
                },
            }
        ),
        _sse({"type": "response.completed", "response": {"id": "resp_tool_alias"}}),
    ]

    parsed = [
        event
        for event in [
            parse_sse_data_json(event)
            async for event in anthropic_messages.iter_messages_events(
                _stream(*blocks),
                client_model="claude-sonnet-5",
                tool_name_aliases={"mcp__short_0123456789abcdef": "mcp__workspace__sentinel_original_tool"},
            )
        ]
        if event is not None
    ]

    assert parsed[1]["content_block"]["name"] == "mcp__workspace__sentinel_original_tool"


@pytest.mark.asyncio
async def test_reasoning_stream_preserves_summary_and_final_signature_order() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_reasoning_stream"}}),
        _sse(
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": "rs_stream",
                    "type": "reasoning",
                    "encrypted_content": "SENTINEL_INITIAL_SIGNATURE",
                    "summary": [],
                },
            }
        ),
        _sse(
            {
                "type": "response.reasoning_summary_part.added",
                "output_index": 0,
                "item_id": "rs_stream",
            }
        ),
        _sse(
            {
                "type": "response.reasoning_summary_text.delta",
                "output_index": 0,
                "item_id": "rs_stream",
                "delta": "Careful summary.",
            }
        ),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "rs_stream",
                    "type": "reasoning",
                    "encrypted_content": "SENTINEL_FINAL_SIGNATURE",
                    "summary": [{"type": "summary_text", "text": "Careful summary."}],
                },
            }
        ),
        _sse({"type": "response.completed", "response": {"id": "resp_reasoning_stream"}}),
    ]

    parsed = [
        event
        for event in [
            parse_sse_data_json(event)
            async for event in anthropic_messages.iter_messages_events(_stream(*blocks), client_model="claude-opus-4-8")
        ]
        if event is not None
    ]

    assert [event["type"] for event in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert parsed[1]["content_block"] == {"type": "thinking", "thinking": ""}
    assert parsed[2]["delta"] == {"type": "thinking_delta", "thinking": "Careful summary."}
    assert parsed[3]["delta"] == {"type": "signature_delta", "signature": "SENTINEL_FINAL_SIGNATURE"}


@pytest.mark.asyncio
async def test_signature_only_reasoning_stream_keeps_opaque_state() -> None:
    blocks = [
        _sse({"type": "response.created", "response": {"id": "resp_signature_stream"}}),
        _sse(
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {"id": "rs_signature", "type": "reasoning", "summary": []},
            }
        ),
        _sse(
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": {
                    "id": "rs_signature",
                    "type": "reasoning",
                    "encrypted_content": "SENTINEL_SIGNATURE_ONLY_STREAM",
                    "summary": [],
                },
            }
        ),
        _sse({"type": "response.completed", "response": {"id": "resp_signature_stream"}}),
    ]

    parsed = [
        event
        for event in [
            parse_sse_data_json(event)
            async for event in anthropic_messages.iter_messages_events(_stream(*blocks), client_model="claude-opus-4-8")
        ]
        if event is not None
    ]

    assert parsed[1]["content_block"] == {"type": "thinking", "thinking": ""}
    assert parsed[2]["delta"] == {
        "type": "signature_delta",
        "signature": "SENTINEL_SIGNATURE_ONLY_STREAM",
    }
    assert parsed[3]["type"] == "content_block_stop"


@pytest.mark.asyncio
async def test_anthropic_auth_accepts_x_api_key_and_rejects_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str | None] = []

    async def fake_validate(authorization: str | None, *, request: Request | None = None) -> None:
        del request
        observed.append(authorization)
        return None

    monkeypatch.setattr(auth_dependencies, "validate_proxy_api_key_authorization", fake_validate)
    assert await auth_dependencies.validate_anthropic_api_key(_request({"x-api-key": "sk-clb-test"})) is None
    assert observed == ["Bearer sk-clb-test"]

    with pytest.raises(ProxyAuthError, match="do not match"):
        await auth_dependencies.validate_anthropic_api_key(
            _request({"x-api-key": "one", "authorization": "Bearer two"})
        )


@pytest.mark.asyncio
async def test_claude_desktop_credential_is_local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str | None] = []

    async def fake_validate(authorization: str | None, *, request: Request | None = None) -> None:
        del request
        observed.append(authorization)
        return None

    monkeypatch.setattr(auth_dependencies, "validate_proxy_api_key_authorization", fake_validate)
    local_request = _request({"x-api-key": "claudedesktop"})
    assert auth_dependencies.is_local_claude_desktop_request(local_request) is True
    assert await auth_dependencies.validate_anthropic_api_key(local_request) is None
    assert observed == []

    remote_request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/messages",
            "query_string": b"",
            "headers": [(b"x-api-key", b"claudedesktop"), (b"host", b"example.test")],
            "client": ("203.0.113.10", 12345),
            "server": ("example.test", 80),
        }
    )
    assert auth_dependencies.is_local_claude_desktop_request(remote_request) is False
    assert await auth_dependencies.validate_anthropic_api_key(remote_request) is None
    assert observed == ["Bearer claudedesktop"]
