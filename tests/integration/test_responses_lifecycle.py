from __future__ import annotations

import asyncio
import base64
import json

import pytest

import app.modules.proxy.service as proxy_module
from app.modules.responses_lifecycle import service as lifecycle_service

pytestmark = pytest.mark.integration


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    return f"header.{body}.sig"


async def _import_account(async_client, account_id: str = "acc_lifecycle") -> None:
    auth_payload = {
        "email": f"{account_id}@example.com",
        "chatgpt_account_id": account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(auth_payload),
            "accessToken": "access-token",
            "refreshToken": "refresh-token",
            "accountId": account_id,
        }
    }
    response = await async_client.post(
        "/api/accounts/import",
        files={"auth_json": ("auth.json", json.dumps(auth_json), "application/json")},
    )
    assert response.status_code == 200


def _completed_event(response_id: str, text: str = "done") -> str:
    payload = {
        "type": "response.completed",
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": 1_786_000_000,
            "status": "completed",
            "model": "gpt-5.6-sol",
            "output": [
                {
                    "id": f"msg_{response_id}",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
        },
    }
    return f"data: {json.dumps(payload)}\n\n"


@pytest.mark.asyncio
async def test_store_retrieve_input_items_and_delete(async_client, monkeypatch):
    await _import_account(async_client)
    forwarded: dict[str, object] = {}

    async def fake_stream(payload, *_args, **_kwargs):
        forwarded["payload"] = payload.to_payload()
        yield _completed_event("resp_stored")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    created = await async_client.post(
        "/v1/responses",
        json={
            "model": "gpt-5.6-sol",
            "input": "remember this",
            "store": True,
            "metadata": {"owner": "sdk-test"},
        },
    )
    assert created.status_code == 200
    assert created.json()["id"] == "resp_stored"
    assert created.json()["metadata"] == {"owner": "sdk-test"}
    assert "metadata" not in forwarded["payload"]
    assert forwarded["payload"]["store"] is False

    retrieved = await async_client.get("/v1/responses/resp_stored")
    assert retrieved.status_code == 200
    assert retrieved.json() == created.json()

    items = await async_client.get("/v1/responses/resp_stored/input_items", params={"order": "asc"})
    assert items.status_code == 200
    assert items.json()["data"][0]["type"] == "message"
    assert items.json()["data"][0]["content"][0]["text"] == "remember this"

    deleted = await async_client.delete("/v1/responses/resp_stored")
    assert deleted.status_code == 200
    assert deleted.json() == {"id": "resp_stored", "object": "response", "deleted": True}
    assert (await async_client.get("/v1/responses/resp_stored")).status_code == 404


@pytest.mark.asyncio
async def test_streaming_store_persists_after_terminal_event(async_client, monkeypatch):
    await _import_account(async_client)

    async def fake_stream(*_args, **_kwargs):
        yield _completed_event("resp_stream_stored", "streamed")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)
    streamed = await async_client.post(
        "/v1/responses",
        json={"model": "gpt-5.6-sol", "input": "stream", "stream": True, "store": True},
    )
    assert streamed.status_code == 200
    assert "response.completed" in streamed.text

    retrieved = await async_client.get("/v1/responses/resp_stream_stored")
    assert retrieved.status_code == 200
    assert retrieved.json()["output"][0]["content"][0]["text"] == "streamed"


@pytest.mark.asyncio
async def test_background_response_completes_and_keeps_public_id(async_client, monkeypatch):
    await _import_account(async_client)

    async def fake_stream(*_args, **_kwargs):
        await asyncio.sleep(0.02)
        yield _completed_event("resp_upstream_background")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)

    created = await async_client.post(
        "/v1/responses",
        json={"model": "gpt-5.6-sol", "input": "work", "background": True},
    )
    assert created.status_code == 200
    response_id = created.json()["id"]
    assert response_id.startswith("resp_")
    assert created.json()["status"] in {"queued", "in_progress"}

    terminal = None
    for _ in range(100):
        polled = await async_client.get(f"/v1/responses/{response_id}")
        if polled.json()["status"] == "completed":
            terminal = polled.json()
            break
        await asyncio.sleep(0.01)
    assert terminal is not None
    assert terminal["id"] == response_id
    assert terminal["background"] is True


@pytest.mark.asyncio
async def test_background_response_can_be_cancelled(async_client, monkeypatch):
    await _import_account(async_client)
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_stream(*_args, **_kwargs):
        started.set()
        await release.wait()
        yield _completed_event("resp_never")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)
    created = await async_client.post(
        "/v1/responses",
        json={"model": "gpt-5.6-sol", "input": "wait", "background": True},
    )
    response_id = created.json()["id"]
    await asyncio.wait_for(started.wait(), timeout=2)

    cancelled = await async_client.post(f"/v1/responses/{response_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert (await async_client.get(f"/v1/responses/{response_id}")).json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_startup_recovery_marks_stranded_response_failed(async_client):
    del async_client
    response_id = lifecycle_service.new_response_id()
    shell = lifecycle_service.public_response_shell(
        response_id=response_id,
        model="gpt-5.6-sol",
        created_at=1_786_000_000,
        status="in_progress",
        background=True,
        instructions="",
        tools=[],
        tool_choice="auto",
        parallel_tool_calls=True,
        metadata=None,
        previous_response_id=None,
        conversation_id=None,
    )
    await lifecycle_service.create_response(
        response_id=response_id,
        api_key_scope=lifecycle_service.ANONYMOUS_API_KEY_SCOPE,
        status="in_progress",
        background=True,
        request={"model": "gpt-5.6-sol", "input": "stranded"},
        input_items=lifecycle_service.normalize_input_items("stranded"),
        response=shell,
        conversation_id=None,
    )

    assert await lifecycle_service.mark_stranded_responses_failed() == 1
    recovered = await lifecycle_service.get_response(
        response_id,
        lifecycle_service.ANONYMOUS_API_KEY_SCOPE,
    )
    assert recovered.status == "failed"
    assert recovered.response["error"]["code"] == "background_worker_restarted"


@pytest.mark.asyncio
async def test_conversation_crud_items_and_response_expansion(async_client, monkeypatch):
    await _import_account(async_client)
    created = await async_client.post(
        "/v1/conversations",
        json={
            "metadata": {"topic": "parity"},
            "items": [{"type": "message", "role": "user", "content": "first"}],
        },
    )
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    updated = await async_client.post(
        f"/v1/conversations/{conversation_id}",
        json={"metadata": {"topic": "updated"}},
    )
    assert updated.json()["metadata"] == {"topic": "updated"}

    added = await async_client.post(
        f"/v1/conversations/{conversation_id}/items",
        json={"items": [{"type": "message", "role": "user", "content": "second"}]},
    )
    assert added.status_code == 200
    added_item_id = added.json()["data"][0]["id"]
    retrieved_item = await async_client.get(
        f"/v1/conversations/{conversation_id}/items/{added_item_id}"
    )
    assert retrieved_item.status_code == 200

    forwarded: dict[str, object] = {}

    async def fake_stream(payload, *_args, **_kwargs):
        forwarded["input"] = payload.input
        forwarded["conversation"] = payload.conversation
        yield _completed_event("resp_conversation", "third-answer")

    monkeypatch.setattr(proxy_module, "core_stream_responses", fake_stream)
    response = await async_client.post(
        "/v1/responses",
        json={"model": "gpt-5.6-sol", "conversation": conversation_id, "input": "third"},
    )
    assert response.status_code == 200
    assert forwarded["conversation"] is None
    assert [item["content"][0]["text"] for item in forwarded["input"][:3]] == [
        "first",
        "second",
        "third",
    ]

    listed = await async_client.get(
        f"/v1/conversations/{conversation_id}/items",
        params={"order": "asc", "limit": 20},
    )
    assert listed.status_code == 200
    assert [item["content"][0]["text"] for item in listed.json()["data"]] == [
        "first",
        "second",
        "third",
        "third-answer",
    ]

    deleted_item = await async_client.delete(
        f"/v1/conversations/{conversation_id}/items/{added_item_id}"
    )
    assert deleted_item.status_code == 200
    deleted = await async_client.delete(f"/v1/conversations/{conversation_id}")
    assert deleted.json()["object"] == "conversation.deleted"
    assert (await async_client.get(f"/v1/conversations/{conversation_id}")).status_code == 404


@pytest.mark.asyncio
async def test_input_token_count_is_deterministic_and_rejects_opaque_inputs(async_client):
    payload = {"model": "gpt-5.6-sol", "input": "count these words"}
    first = await async_client.post("/v1/responses/input_tokens", json=payload)
    second = await async_client.post("/v1/responses/input_tokens", json=payload)
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["input_tokens"] > 0
    assert first.headers["x-codex-lb-token-count"] == "local-compatible"

    opaque = await async_client.post(
        "/v1/responses/input_tokens",
        json={
            "model": "gpt-5.6-sol",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_file", "file_id": "file_1"}]}],
        },
    )
    assert opaque.status_code == 400
    assert opaque.json()["error"]["code"] == "unsupported_token_count_input"
