## Why

GPT-5.6 Sol uses Codex Responses Lite, where the custom `exec` tool bundle is carried in an `input` item with `type = "additional_tools"` and `role = "developer"` instead of the ordinary top-level `tools` field. The current Responses instruction normalizer treats every developer item as a text instruction and silently drops this content-less protocol item, so upstream receives no shell/filesystem tools.

## What Changes

- Preserve the complete Responses Lite input envelope unchanged. When `additional_tools` is present, its following developer instruction message and all later tool-call history remain inside `input` in their original order instead of being lifted into top-level `instructions`.
- Lock the behavior at the request-model, HTTP forwarding, HTTP-to-WebSocket bridge, and native WebSocket forwarding boundaries, including `custom_tool_call_output` ordering.
- Treat the marker as a native Codex transport signal: upstream HTTP/compact requests receive `x-openai-internal-codex-responses-lite: true`, while upstream WebSocket `response.create` messages receive `client_metadata.ws_request_header_x_openai_internal_codex_responses_lite = "true"` and the handshake omits the HTTP-only marker.
- Mirror the verified request-normalization source into the active Electron portable runtime and restart that runtime for live verification.

## Non-goals

- Do not disable `use_responses_lite` or install a local model-catalog workaround.
- Do not synthesize top-level `tools` from `additional_tools`.
- Do not change GPT-5.6 aliases, pricing, reasoning levels, service tiers, or model metadata in this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: native Codex Responses Lite tool declarations and marker metadata remain intact across supported HTTP and WebSocket proxy transports.

## Impact

- Code: Responses request normalization, proxy header/transport helpers, WebSocket response-create metadata, and their active portable mirrors.
- Tests: `tests/unit/test_openai_requests.py`, the HTTP Responses forwarding integration surface, and `tests/integration/test_proxy_websocket_responses.py`.
- Specs: `openspec/specs/responses-api-compat/spec.md` and context.
