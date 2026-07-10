# harden-codex-desktop-api-parity-pass

## Why

The latest Codex Desktop protocol exposed several gaps in the CodexNeo path: the explicit restart action stops only the child `codex.exe` app-server, the model catalogue drops `model_messages`, continuation-only Responses requests fail local validation, and unsupported Responses controls can be accepted without taking effect. Bootstrap catalogue tests also lag behind the GPT-5.6 entries already shipped by the runtime.

## What Changes

- Restart the installed Codex Desktop package by closing its `ChatGPT.exe` shell and, if required, force-stopping only remaining processes owned by the `OpenAI.Codex` WindowsApps package before relaunch.
- Preserve all JSON-compatible upstream model catalogue fields, including `model_messages` and future fields unknown to codex-lb.
- Accept Responses requests that continue by `previous_response_id` or `conversation` without new input.
- Reject unsupported persistence, background, and generation controls with a stable OpenAI-style `unsupported_parameter` error instead of silently discarding them.
- Bring bootstrap catalogue expectations and contract-diff regression coverage in line with the existing GPT-5.6 runtime entries.

## Non-goals

- Full OpenAI Responses API parity, including background response retrieval, cancellation, deletion, or input-item endpoints.
- Restarting Codex Desktop or the portable Electron app during implementation or verification.
- Changing the already-completed Responses Lite `additional_tools` fix.

## Capabilities

### Modified Capabilities

- `codexneo-windows-integration`
- `model-catalog-compat`
- `responses-api-compat`
