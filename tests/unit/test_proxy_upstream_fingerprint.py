from __future__ import annotations

from app.core.clients.proxy import _build_upstream_headers, _build_upstream_websocket_headers


def test_non_native_http_fingerprint_is_normalized_to_codex_cli() -> None:
    inbound = {
        "User-Agent": "OpenAI/Python 2.24.0",
        "x-openai-client-version": "2.24.0",
        "x-stainless-runtime": "CPython",
        "originator": "sdk",
        "Version": "9.9.9",
    }

    headers = _build_upstream_headers(inbound, "tok", "acct-1")

    lowered = {key.lower() for key in headers}
    assert headers["User-Agent"].startswith("codex_cli_rs/")
    assert headers["originator"] == "codex_cli_rs"
    assert headers["version"]
    assert headers["ChatGPT-Account-Id"] == "acct-1"
    assert "x-openai-client-version" not in lowered
    assert "x-stainless-runtime" not in lowered


def test_non_native_websocket_fingerprint_is_normalized_to_codex_cli() -> None:
    headers = _build_upstream_websocket_headers({"User-Agent": "sdk"}, "tok", "acct-1")

    assert headers["originator"] == "codex_cli_rs"
    assert headers["version"]
    assert headers["ChatGPT-Account-Id"] == "acct-1"
