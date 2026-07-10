# Design

## Responses Lite wire normalization

Responses Lite is selected from the normalized body when `input` contains an `additional_tools` item. HTTP transports synthesize `x-openai-internal-codex-responses-lite: true`; WebSocket transports synthesize `client_metadata.ws_request_header_x_openai_internal_codex_responses_lite = "true"`. The upstream Lite validator requires `parallel_tool_calls` to be exactly `false`, even though the general GPT-5.6 catalog advertises parallel-tool capability and Codex may send `true`.

Normalize at the final wire-payload boundaries rather than weakening model metadata:

1. In the core HTTP/WebSocket transport, identify Lite from the body or canonical WebSocket marker and overwrite only the outbound mapping with `parallel_tool_calls=false`.
2. In the shared HTTP-bridge/WebSocket request-frame builder, apply the same rule after canonical `client_metadata` is attached. This also covers trusted marker-only incremental continuations whose body no longer repeats `additional_tools`.
3. Reapply the rule in both fresh WebSocket retry serializers. Recovery serializes the validated request again, so relying only on the initial frame normalizer would restore the client's original `parallel_tool_calls=true` on a full-resend retry.
4. Update compact serialization to remove `tools` and `tool_choice` but explicitly set `parallel_tool_calls=false`. The upstream compact endpoint now rejects a missing value, so the branch's older remove-the-field contract is stale.

This keeps client-plane configuration intact, leaves non-Lite requests untouched, and prevents retries/replays from reintroducing the incompatible client value.

## Dual-shape model catalog

Move `CodexModelsResponse` below `ModelListItem`, then add `object: "list"` and `data: list[ModelListItem]`. Extract the existing OpenAI model-item conversion into one helper used by bare `/v1/models` and the Codex builder.

Native `data` timestamps come from stable upstream model metadata (`created`, `created_at`, or `createdAt`, falling back to `0`) so separate calls to negotiated `/v1/models` and `/backend-api/codex/models` remain byte-equivalent across wall-clock second boundaries. Current local filtering remains authoritative: models admitted to the native list also enter `data` unless Codex visibility rewriting marks them hidden.

## Verification boundaries

- Wire-level regressions capture direct HTTP, core WebSocket, HTTP bridge, native WebSocket, and compact payloads.
- Catalog integration regressions assert all three top-level fields, deterministic endpoint equality, supported-in-API-false compatibility, and API-key filtering.
- Portable verification uses hash comparison against both runtime code roots plus targeted import/compile checks. The current Electron-owned backend is checked for health, catalog shape, request-log evidence, and account cleanliness, but is not killed and replaced out of band: Electron does not respawn a terminated child, and a detached replacement would no longer stop with the tray app. The mirrored fix activates on the operator's next full Codex-LB restart.
- No real account snapshots or Codex Desktop processes are modified by the test suite.
