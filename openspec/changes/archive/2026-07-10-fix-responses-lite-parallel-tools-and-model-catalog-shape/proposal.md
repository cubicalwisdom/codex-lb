# Fix Responses Lite parallel-tool forwarding and model catalog shape

## Why

Complete two Codex compatibility contracts that are already partially implemented on the portable branch:

- force upstream `parallel_tool_calls` to `false` whenever codex-lb selects Responses Lite;
- return the documented dual-shape Codex catalog (`models`, `object`, and `data`) from the native model builder and negotiated `/v1/models` path.

The restarted portable runtime recorded twelve upstream HTTP 400 responses with `unsupported_value` because a Responses Lite request still carried `parallel_tool_calls=true`. This is most visible when Codex runs a remote/sub-agent compaction task, which retries and shows the same error repeatedly.

The negotiated catalog route now returns native `models`, but the shared native builder lacks the OpenAI-compatible `object` and `data` fields required by the stable model-catalog specification and upstream PR #1163.

## What Changes

- Normalize full Responses Lite HTTP, HTTP-bridge, and WebSocket wire payloads to `parallel_tool_calls=false`, including trusted marker-only WebSocket continuations.
- Set `parallel_tool_calls=false` explicitly on compact payloads instead of removing the now-required field.
- Leave non-Lite requests unchanged and retain the compact endpoint's existing unsupported-field stripping.
- Populate native and negotiated model responses with deterministic OpenAI-compatible `data` entries while preserving current API-key visibility/filtering behavior.
- Mirror the verified source into both portable Python roots, verify the currently running backend remains healthy and account-clean, record that one full Codex-LB restart is required to load the new code, update stable documentation, and commit the accumulated parity work requested by the operator. The backend is not replaced with a detached process because that would break the Electron tray's child-process ownership.

## Out of scope

- Restarting Codex Desktop.
- Changing GPT-5.6 model metadata to claim that parallel tool calls are globally unsupported.
- Changing bare or empty-parameter `/v1/models` behavior.
- Implementing the deferred Electron double-window startup race.
