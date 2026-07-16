from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from fastapi.responses import JSONResponse, StreamingResponse

import app.modules.proxy.api as proxy_api_module
from app.dependencies import ProxyContext, get_proxy_context
from app.modules.anthropic_batches import service as anthropic_batches
from app.modules.responses_lifecycle.service import ANONYMOUS_API_KEY_SCOPE

pytestmark = pytest.mark.integration


async def _openai_stream() -> AsyncIterator[str]:
    yield 'data: {"type":"response.created","response":{"id":"resp_route"}}\n\n'
    yield (
        'data: {"type":"response.output_text.delta","output_index":0,"content_index":0,'
        '"item_id":"msg_route","delta":"hello"}\n\n'
    )
    yield (
        'data: {"type":"response.completed","response":{"id":"resp_route",'
        '"usage":{"input_tokens":2,"output_tokens":3}}}\n\n'
    )


async def _stream(*blocks: str) -> AsyncIterator[str]:
    for block in blocks:
        yield block


@pytest.mark.asyncio
async def test_messages_route_returns_anthropic_non_streaming_message(async_client, app_instance, monkeypatch) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())

    async def fake_collect(*args, **kwargs):
        del args, kwargs
        return JSONResponse(
            {
                "id": "resp_route",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "sk-clb-local"},
        json={"model": "gpt-5.6-terra", "max_tokens": 1024, "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "resp_route",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "hello"}],
        "model": "gpt-5.6-terra",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 2, "output_tokens": 3},
    }


@pytest.mark.asyncio
async def test_claude_desktop_messages_route_maps_web_search_and_web_fetch(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, dict[str, object]] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_web_route",
                "status": "completed",
                "usage": {"input_tokens": 8, "output_tokens": 5},
                "output": [
                    {
                        "id": "ws_route",
                        "type": "web_search_call",
                        "status": "completed",
                        "action": {"type": "search", "queries": ["Python documentation"]},
                    },
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Python documentation is at python.org."}],
                    },
                ],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-sonnet-5",
            "max_tokens": 1024,
            "tools": [
                {"type": "web_search_20260318", "name": "web_search", "max_uses": 3},
                {"type": "web_fetch_20260318", "name": "web_fetch", "max_uses": 5},
            ],
            "messages": [{"role": "user", "content": "Find and read the Python documentation."}],
        },
    )

    assert response.status_code == 200
    assert observed["request"]["tools"] == [{"type": "web_search"}]
    assert response.json()["content"] == [{"type": "text", "text": "Python documentation is at python.org."}]


@pytest.mark.asyncio
async def test_claude_desktop_route_uses_hosted_tool_for_public_workspace_web_fetch(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, dict[str, object]] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_workspace_web_fetch",
                "status": "completed",
                "usage": {"input_tokens": 12, "output_tokens": 4},
                "output": [
                    {
                        "id": "ws_open_page",
                        "type": "web_search_call",
                        "status": "completed",
                        "action": {"type": "open_page", "url": "https://claude.com/docs"},
                    },
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Claude documentation loaded."}],
                    },
                ],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "tools": [
                {
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
            ],
            "messages": [
                {
                    "role": "user",
                    "content": "Fetch https://claude.com/docs and summarize it.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert observed["request"]["tools"] == [{"type": "web_search"}]
    assert response.json()["content"] == [{"type": "text", "text": "Claude documentation loaded."}]


@pytest.mark.asyncio
async def test_claude_desktop_route_accepts_hosted_workspace_alias_in_tool_search_history(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, dict[str, object]] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_workspace_web_fetch_history",
                "status": "completed",
                "usage": {"input_tokens": 12, "output_tokens": 4},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Example Domain"}],
                    }
                ],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 128,
            "tools": [
                {
                    "name": "ToolSearch",
                    "description": "Load deferred tools",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
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
                },
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
                            "content": [
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"}
                            ],
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": "Fetch https://example.com and return only its page title.",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert observed["request"]["tools"] == [
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
    assert observed["request"]["tool_choice"] == {"type": "web_search"}
    assert [item.get("type", item.get("role")) for item in observed["request"]["input"]] == ["user"]
    assert response.json()["content"] == [{"type": "text", "text": "Example Domain"}]


@pytest.mark.asyncio
async def test_claude_desktop_tool_reference_history_reaches_responses(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, dict[str, object]] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_tool_reference_history",
                "status": "completed",
                "usage": {"input_tokens": 8, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "Recovered."}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
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
                {
                    "name": "mcp__workspace__web_fetch",
                    "description": "Fetch a page",
                    "input_schema": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
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
                                {"type": "tool_reference", "tool_name": "mcp__workspace__web_fetch"}
                            ],
                        }
                    ],
                },
                {"role": "user", "content": "/setup-cowork"},
            ],
        },
    )

    assert response.status_code == 200
    assert [item["type"] if "type" in item else item["role"] for item in observed["request"]["input"]] == [
        "tool_search_call",
        "tool_search_output",
        "user",
    ]
    assert response.json()["content"] == [{"type": "text", "text": "Recovered."}]


@pytest.mark.asyncio
async def test_claude_desktop_web_server_tools_are_accepted_by_count_tokens(async_client) -> None:
    response = await async_client.post(
        "/v1/messages/count_tokens?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-sonnet-5",
            "tools": [{"type": "web_search_20260318", "name": "web_search", "max_uses": 3}],
            "messages": [{"role": "user", "content": "Search for the Python documentation."}],
        },
    )

    assert response.status_code == 200
    assert response.json()["input_tokens"] > 0
    assert response.headers["x-codex-lb-token-count"] == "local-compatible"


@pytest.mark.asyncio
async def test_claude_desktop_web_fetch_is_accepted_by_message_batch(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, dict[str, object]] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_web_batch",
                "status": "completed",
                "usage": {"input_tokens": 5, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "Fetched."}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    created = await async_client.post(
        "/v1/messages/batches?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "requests": [
                {
                    "custom_id": "web-fetch-batch",
                    "params": {
                        "model": "claude-sonnet-5",
                        "max_tokens": 1024,
                        "tools": [{"type": "web_fetch_20260318", "name": "web_fetch", "max_uses": 2}],
                        "messages": [{"role": "user", "content": "Read https://www.python.org/."}],
                    },
                }
            ]
        },
    )

    assert created.status_code == 200
    batch_id = created.json()["id"]
    terminal = None
    for _ in range(30):
        retrieved = await async_client.get(
            f"/v1/messages/batches/{batch_id}",
            headers={"x-api-key": "claudedesktop"},
        )
        if retrieved.json()["processing_status"] == "ended":
            terminal = retrieved
            break
        await asyncio.sleep(0.01)

    assert terminal is not None
    assert observed["request"]["tools"] == [{"type": "web_search"}]
    assert terminal.json()["request_counts"]["succeeded"] == 1


@pytest.mark.asyncio
async def test_claude_desktop_blocked_domains_are_omitted_for_upstream(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, dict[str, object]] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_blocked_domains_compat",
                "status": "completed",
                "usage": {"input_tokens": 8, "output_tokens": 5},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Search completed."}],
                    }
                ],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
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
    )

    assert response.status_code == 200
    assert observed["request"]["tools"] == [{"type": "web_search"}]
    assert response.json()["content"] == [{"type": "text", "text": "Search completed."}]


@pytest.mark.asyncio
async def test_messages_batch_persists_and_returns_jsonl_results(async_client, app_instance, monkeypatch) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())

    async def fake_collect(*args, **kwargs):
        del args, kwargs
        return JSONResponse(
            {
                "id": "resp_batch_one",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "batched"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    created = await async_client.post(
        "/v1/messages/batches",
        headers={"x-api-key": "sk-clb-local"},
        json={
            "requests": [
                {
                    "custom_id": "batch-one",
                    "params": {
                        "model": "gpt-5.6-terra",
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                }
            ]
        },
    )

    assert created.status_code == 200
    batch_id = created.json()["id"]
    assert created.json()["type"] == "message_batch"

    terminal = None
    for _ in range(30):
        retrieved = await async_client.get(f"/v1/messages/batches/{batch_id}", headers={"x-api-key": "sk-clb-local"})
        if retrieved.json()["processing_status"] == "ended":
            terminal = retrieved.json()
            break
        await asyncio.sleep(0.01)
    assert terminal is not None
    assert terminal["request_counts"] == {
        "processing": 0,
        "succeeded": 1,
        "errored": 0,
        "canceled": 0,
        "expired": 0,
    }

    results = await async_client.get(
        f"/v1/messages/batches/{batch_id}/results",
        headers={"x-api-key": "sk-clb-local"},
    )
    assert results.status_code == 200
    assert results.headers["content-type"].startswith("application/jsonl")
    assert [json.loads(line) for line in results.text.splitlines()] == [
        {
            "custom_id": "batch-one",
            "result": {
                "type": "succeeded",
                "message": {
                    "id": "resp_batch_one",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "batched"}],
                    "model": "gpt-5.6-terra",
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 2, "output_tokens": 3},
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_messages_batch_cancel_makes_in_flight_item_terminal(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    started = asyncio.Event()

    async def blocked_collect(*args, **kwargs):
        del args, kwargs
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("canceled batch work must not resume")

    monkeypatch.setattr(proxy_api_module, "_collect_responses", blocked_collect)
    created = await async_client.post(
        "/v1/messages/batches",
        headers={"x-api-key": "claudedesktop"},
        json={
            "requests": [
                {
                    "custom_id": "cancel-in-flight",
                    "params": {
                        "model": "claude-sonnet-5",
                        "max_tokens": 16,
                        "messages": [{"role": "user", "content": "wait"}],
                    },
                }
            ]
        },
    )

    assert created.status_code == 200
    batch_id = created.json()["id"]
    await asyncio.wait_for(started.wait(), timeout=1)
    canceled = await async_client.post(
        f"/v1/messages/batches/{batch_id}/cancel",
        headers={"x-api-key": "claudedesktop"},
    )

    assert canceled.status_code == 200
    assert canceled.json()["processing_status"] == "ended"
    assert canceled.json()["request_counts"] == {
        "processing": 0,
        "succeeded": 0,
        "errored": 0,
        "canceled": 1,
        "expired": 0,
    }
    results = await async_client.get(
        f"/v1/messages/batches/{batch_id}/results",
        headers={"x-api-key": "claudedesktop"},
    )
    assert [json.loads(line) for line in results.text.splitlines()] == [
        {"custom_id": "cancel-in-flight", "result": {"type": "canceled"}}
    ]


@pytest.mark.asyncio
async def test_messages_batch_requeues_stranded_item_and_resumes_on_authenticated_poll(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())

    batch = await anthropic_batches.create_batch(
        api_key_scope=ANONYMOUS_API_KEY_SCOPE,
        requests=[
            anthropic_batches.BatchCreateItem(
                custom_id="restart-resume",
                params={
                    "model": "claude-sonnet-5",
                    "max_tokens": 16,
                    "messages": [{"role": "user", "content": "resume"}],
                },
            )
        ],
    )
    claimed = await anthropic_batches.claim_next_item(batch.id, ANONYMOUS_API_KEY_SCOPE)
    assert claimed is not None
    assert claimed.status == "in_progress"
    assert await anthropic_batches.requeue_stranded_batches() == 1

    async def fake_collect(*args, **kwargs):
        del args, kwargs
        return JSONResponse(
            {
                "id": "resp_restart_resume",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "resumed"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    retrieved = await async_client.get(
        f"/v1/messages/batches/{batch.id}",
        headers={"x-api-key": "claudedesktop"},
    )
    assert retrieved.status_code == 200

    terminal = None
    for _ in range(30):
        polled = await async_client.get(
            f"/v1/messages/batches/{batch.id}",
            headers={"x-api-key": "claudedesktop"},
        )
        if polled.json()["processing_status"] == "ended":
            terminal = polled.json()
            break
        await asyncio.sleep(0.01)
    assert terminal is not None
    assert terminal["request_counts"] == {
        "processing": 0,
        "succeeded": 1,
        "errored": 0,
        "canceled": 0,
        "expired": 0,
    }
    results = await async_client.get(
        f"/v1/messages/batches/{batch.id}/results",
        headers={"x-api-key": "claudedesktop"},
    )
    assert [json.loads(line) for line in results.text.splitlines()] == [
        {
            "custom_id": "restart-resume",
            "result": {
                "type": "succeeded",
                "message": {
                    "id": "resp_restart_resume",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "resumed"}],
                    "model": "claude-sonnet-5",
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 2, "output_tokens": 3},
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_messages_context_management_compacts_near_limit_history(async_client, app_instance, monkeypatch) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, object] = {}

    async def fake_compact(*args, **kwargs):
        del args, kwargs
        observed["compacted"] = True
        return JSONResponse(
            {
                "object": "response.compact",
                "id": "compact_1",
                "output": [{"type": "compaction", "encrypted_content": "compact"}],
            }
        )

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["input"] = args[1].input
        return JSONResponse(
            {
                "id": "resp_compacted",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "continued"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_compact_responses", fake_compact)
    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "sk-clb-local"},
        json={
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]},
            "messages": [
                {"role": "user", "content": "x" * 1_000_000},
                {"role": "assistant", "content": "prior answer"},
                {"role": "user", "content": "What should happen now?"},
            ],
        },
    )

    assert response.status_code == 200
    assert observed["compacted"] is True
    assert observed["input"] == [
        {"type": "compaction", "encrypted_content": "compact"},
        {"role": "user", "content": [{"type": "input_text", "text": "What should happen now?"}]},
    ]
    assert response.headers["x-codex-lb-context-compacted"] == "true"


@pytest.mark.asyncio
async def test_claude_desktop_automatically_compacts_near_limit_history(
    async_client,
    app_instance,
    monkeypatch,
    caplog,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, object] = {}

    async def fake_compact(*args, **kwargs):
        del kwargs
        observed["compact_input"] = args[1].input
        return JSONResponse(
            {
                "object": "response.compact",
                "id": "compact_desktop",
                "output": [{"type": "compaction", "encrypted_content": "desktop-compact"}],
            }
        )

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["final_input"] = args[1].input
        return JSONResponse(
            {
                "id": "resp_desktop_compacted",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "continued"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_ANTHROPIC_MAPPED_CONTEXT_GUARD_TOKENS", 64)
    monkeypatch.setattr(proxy_api_module, "_compact_responses", fake_compact)
    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    caplog.set_level("INFO", logger=proxy_api_module.__name__)

    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": "historic question"},
                {"role": "assistant", "content": "historic answer"},
                {"role": "user", "content": "Newest user turn must remain verbatim."},
            ],
        },
    )

    assert response.status_code == 200
    assert observed["compact_input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "historic question"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "historic answer"}]},
    ]
    assert observed["final_input"] == [
        {"type": "compaction", "encrypted_content": "desktop-compact"},
        {"role": "user", "content": [{"type": "input_text", "text": "Newest user turn must remain verbatim."}]},
    ]
    assert response.headers["x-codex-lb-context-compacted"] == "true"
    assert any(
        "anthropic_context_compacted trigger=claude_desktop_auto" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_claude_desktop_compacts_system_instructions_above_upstream_field_limit(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, object] = {}
    oversized_system = "S" * 1_048_577

    async def fake_compact(*args, **kwargs):
        del kwargs
        compact_payload = args[1]
        observed["compact_instructions"] = compact_payload.instructions
        observed["compact_input"] = compact_payload.input
        if isinstance(compact_payload.instructions, str) and len(compact_payload.instructions) > 1_048_576:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": "Invalid 'instructions': string too long.",
                        "type": "invalid_request_error",
                        "code": "string_above_max_length",
                    }
                },
            )
        return JSONResponse(
            {
                "object": "response.compact",
                "id": "compact_large_instructions",
                "output": [{"type": "compaction", "encrypted_content": "large-instructions-compact"}],
            }
        )

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["final_instructions"] = args[1].instructions
        observed["final_input"] = args[1].input
        return JSONResponse(
            {
                "id": "resp_large_instructions",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "continued"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_compact_responses", fake_compact)
    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)

    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "system": oversized_system,
            "messages": [
                {"role": "user", "content": "historic question"},
                {"role": "assistant", "content": "historic answer"},
                {"role": "user", "content": "Newest user turn must remain verbatim."},
            ],
        },
    )

    assert response.status_code == 200, (response.json(), observed)
    assert observed["compact_instructions"] in {None, ""}
    compact_input = observed["compact_input"]
    assert isinstance(compact_input, list)
    system_item = compact_input[0]
    assert isinstance(system_item, dict)
    assert system_item["role"] == "system"
    system_content = system_item["content"]
    assert isinstance(system_content, list)
    assert "".join(part["text"] for part in system_content) == oversized_system
    assert all(len(part["text"]) <= 524_288 for part in system_content)
    assert observed["final_instructions"] in {None, ""}
    assert observed["final_input"] == [
        {"type": "compaction", "encrypted_content": "large-instructions-compact"},
        {"role": "user", "content": [{"type": "input_text", "text": "Newest user turn must remain verbatim."}]},
    ]
    assert response.headers["x-codex-lb-context-compacted"] == "true"


@pytest.mark.asyncio
async def test_non_desktop_near_limit_history_still_requires_explicit_compaction_opt_in(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())

    async def unexpected_upstream(*args, **kwargs):
        del args, kwargs
        pytest.fail("near-limit non-Desktop request must not reach compact or normal upstream execution")

    monkeypatch.setattr(proxy_api_module, "_ANTHROPIC_MAPPED_CONTEXT_GUARD_TOKENS", 64)
    monkeypatch.setattr(proxy_api_module, "_compact_responses", unexpected_upstream)
    monkeypatch.setattr(proxy_api_module, "_collect_responses", unexpected_upstream)

    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "sk-clb-local"},
        json={
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": "historic question"},
                {"role": "assistant", "content": "historic answer"},
                {"role": "user", "content": "new question"},
            ],
        },
    )

    assert response.status_code == 400
    assert "Enable context_management.edits" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_claude_desktop_oversized_single_turn_is_not_compacted(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())

    async def unexpected_upstream(*args, **kwargs):
        del args, kwargs
        pytest.fail("an uncompactionable single turn must not reach upstream execution")

    monkeypatch.setattr(proxy_api_module, "_ANTHROPIC_MAPPED_CONTEXT_GUARD_TOKENS", 64)
    monkeypatch.setattr(proxy_api_module, "_compact_responses", unexpected_upstream)
    monkeypatch.setattr(proxy_api_module, "_collect_responses", unexpected_upstream)

    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "one oversized turn"}],
        },
    )

    assert response.status_code == 400
    assert "has no prior turn that can be compacted" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_claude_desktop_compact_failure_does_not_forward_oversized_request(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed = {"compact_calls": 0}

    async def fake_compact(*args, **kwargs):
        del args, kwargs
        observed["compact_calls"] += 1
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": "compact unavailable",
                    "type": "server_error",
                    "code": "upstream_unavailable",
                }
            },
        )

    async def unexpected_collect(*args, **kwargs):
        del args, kwargs
        pytest.fail("the original oversized request must not be forwarded after compact failure")

    monkeypatch.setattr(proxy_api_module, "_ANTHROPIC_MAPPED_CONTEXT_GUARD_TOKENS", 64)
    monkeypatch.setattr(proxy_api_module, "_compact_responses", fake_compact)
    monkeypatch.setattr(proxy_api_module, "_collect_responses", unexpected_collect)

    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": "historic question"},
                {"role": "assistant", "content": "historic answer"},
                {"role": "user", "content": "new question"},
            ],
        },
    )

    assert response.status_code == 503
    assert observed == {"compact_calls": 1}
    assert "x-codex-lb-context-compacted" not in response.headers


@pytest.mark.asyncio
async def test_claude_desktop_route_maps_opus_to_sol(async_client, app_instance, monkeypatch) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, str] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["effective_model"] = args[1].model
        return JSONResponse(
            {
                "id": "resp_opus",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "claudedesktop"},
        json={"model": "claude-opus-4-8", "max_tokens": 1024, "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert observed == {"effective_model": "gpt-5.6-sol"}
    assert response.json()["model"] == "claude-opus-4-8"


@pytest.mark.asyncio
async def test_claude_desktop_count_tokens_route_uses_local_messages_normalization(async_client) -> None:
    response = await async_client.post(
        "/v1/messages/count_tokens?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "system": "Be concise.",
            "messages": [{"role": "user", "content": "Count these tokens."}],
        },
    )

    assert response.status_code == 200
    assert response.json()["input_tokens"] > 0
    assert response.headers["x-codex-lb-token-count"] == "local-compatible"


@pytest.mark.asyncio
async def test_claude_desktop_route_uses_persisted_sonnet_fallback_effort(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, object] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_sonnet",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    monkeypatch.setattr(proxy_api_module, "get_configured_claude_desktop_sonnet_reasoning_effort", lambda: "xhigh")
    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "claudedesktop"},
        json={"model": "claude-sonnet-5", "max_tokens": 1024, "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert observed["request"] == {
        "model": "gpt-5.6-terra",
        "instructions": "",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        "reasoning": {"effort": "xhigh"},
        "store": False,
        "stream": False,
        "include": [],
    }
    assert response.json()["model"] == "claude-sonnet-5"


@pytest.mark.asyncio
async def test_claude_desktop_route_accepts_beta_developer_messages(async_client, app_instance, monkeypatch) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, object] = {}

    async def fake_collect(*args, **kwargs):
        del kwargs
        observed["request"] = args[1].model_dump_for_forwarding()
        return JSONResponse(
            {
                "id": "resp_desktop_beta",
                "status": "completed",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}],
            }
        )

    monkeypatch.setattr(proxy_api_module, "_collect_responses", fake_collect)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "output_config": {"effort": "max"},
            "messages": [
                {"role": "developer", "content": "Use concise answers."},
                {"role": "user", "content": "hi"},
            ],
        },
    )

    assert response.status_code == 200
    assert observed["request"] == {
        "model": "gpt-5.6-sol",
        "instructions": "Use concise answers.",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        "reasoning": {"effort": "max"},
        "store": False,
        "stream": False,
        "include": [],
    }


@pytest.mark.asyncio
async def test_claude_desktop_key_scopes_the_v1_models_catalog(async_client) -> None:
    desktop_response = await async_client.get("/v1/models", headers={"x-api-key": "claudedesktop"})
    ordinary_response = await async_client.get("/v1/models")

    assert desktop_response.status_code == 200
    assert [(item["id"], item["owned_by"]) for item in desktop_response.json()["data"]] == [
        ("claude-opus-4-8", "anthropic"),
        ("claude-sonnet-5", "anthropic"),
    ]
    assert ordinary_response.status_code == 200
    ordinary_ids = {item["id"] for item in ordinary_response.json()["data"]}
    assert "claude-opus-4-8" not in ordinary_ids
    assert "claude-sonnet-5" not in ordinary_ids


@pytest.mark.asyncio
async def test_claude_desktop_model_discovery_remains_available_when_api_keys_are_required(async_client) -> None:
    enabled = await async_client.put(
        "/api/settings",
        json={
            "stickyThreadsEnabled": False,
            "preferEarlierResetAccounts": False,
            "totpRequiredOnLogin": False,
            "apiKeyAuthEnabled": True,
        },
    )
    assert enabled.status_code == 200

    desktop_response = await async_client.get("/v1/models", headers={"x-api-key": "claudedesktop"})
    ordinary_response = await async_client.get("/v1/models")

    assert desktop_response.status_code == 200
    assert [item["id"] for item in desktop_response.json()["data"]] == [
        "claude-opus-4-8",
        "claude-sonnet-5",
    ]
    assert ordinary_response.status_code == 401


@pytest.mark.asyncio
async def test_messages_route_streams_anthropic_events(async_client, app_instance, monkeypatch) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())

    async def fake_stream(*args, **kwargs):
        del args, kwargs
        return StreamingResponse(_openai_stream(), media_type="text/event-stream")

    monkeypatch.setattr(proxy_api_module, "_stream_responses", fake_stream)
    response = await async_client.post(
        "/v1/messages",
        json={
            "model": "gpt-5.6-terra",
            "max_tokens": 1024,
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 200
    assert "event: message_start" in response.text
    assert '"type":"text_delta","text":"hello"' in response.text
    assert "event: message_stop" in response.text


@pytest.mark.asyncio
async def test_claude_desktop_stream_bypasses_bridge_and_closes_recoverable_terminal_loss(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    observed: dict[str, object] = {}

    async def fake_stream(*args, **kwargs):
        del args
        observed["prefer_http_bridge"] = kwargs["prefer_http_bridge"]
        return StreamingResponse(
            _stream(
                'data: {"type":"response.created","response":{"id":"resp_desktop"}}\n\n',
                (
                    'data: {"type":"response.output_text.delta","output_index":0,"content_index":0,'
                    '"item_id":"msg_desktop","delta":"done"}\n\n'
                ),
                (
                    'data: {"type":"response.failed","response":{"error":{"code":"stream_incomplete",'
                    '"message":"terminal frame lost"}}}\n\n'
                ),
            ),
            media_type="text/event-stream",
        )

    monkeypatch.setattr(proxy_api_module, "_stream_responses", fake_stream)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-opus-4-8",
            "max_tokens": 1024,
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 200
    assert observed == {"prefer_http_bridge": False}
    assert '"text":"done"' in response.text
    assert "event: message_stop" in response.text
    assert "terminal frame lost" not in response.text


@pytest.mark.asyncio
async def test_claude_desktop_retries_no_account_startup_before_returning_error(
    async_client,
    app_instance,
    monkeypatch,
) -> None:
    app_instance.dependency_overrides[get_proxy_context] = lambda: ProxyContext(service=object())
    calls = 0

    async def fake_stream(*args, **kwargs):
        nonlocal calls
        del args, kwargs
        calls += 1
        if calls == 1:
            return JSONResponse({"error": {"code": "no_accounts", "message": "No available accounts"}}, status_code=503)
        return StreamingResponse(_openai_stream(), media_type="text/event-stream")

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(proxy_api_module, "_stream_responses", fake_stream)
    monkeypatch.setattr(proxy_api_module.asyncio, "sleep", fake_sleep)
    response = await async_client.post(
        "/v1/messages?beta=true",
        headers={"x-api-key": "claudedesktop"},
        json={
            "model": "claude-sonnet-5",
            "max_tokens": 1024,
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 200
    assert calls == 2
    assert "event: message_stop" in response.text


@pytest.mark.asyncio
async def test_messages_route_returns_anthropic_error_for_conflicting_credentials(async_client) -> None:
    response = await async_client.post(
        "/v1/messages",
        headers={"x-api-key": "one", "authorization": "Bearer two"},
        json={"model": "gpt-5.6-terra", "max_tokens": 1024, "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 401
    assert response.json() == {
        "type": "error",
        "error": {"type": "authentication_error", "message": "x-api-key and Authorization credentials do not match"},
    }
