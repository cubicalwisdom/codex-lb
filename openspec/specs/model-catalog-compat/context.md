# Model Catalog Compatibility Context

## Purpose

The model registry serves a conservative bundled catalog during startup/offline operation and switches to the live upstream catalog after refresh. Native Codex clients need the full catalog shape and compatibility fields; OpenAI-compatible clients need the ordinary `object`/`data` list unless they explicitly negotiate native metadata.

## Decisions

- The GPT-5.6 fallback mirrors Codex rust-v0.144.1 for every field codex-lb serves: Sol, Terra, and Luna use a 372,000-token window and minimum client version 0.144.0.
- The fallback deliberately omits the large upstream `base_instructions` and personality-templated `model_messages`; live refresh supplies them and remains authoritative.
- Unknown JSON-compatible live fields are retained losslessly so new personality or capability data does not require a local allowlist update.
- A non-empty `/v1/models?client_version=...` returns the same native payload as `/backend-api/codex/models`, including `models`, `object: "list"`, and deterministic OpenAI-compatible `data`. Native `data[].created` comes from stable catalog metadata rather than request time so the two endpoints remain equal across separate calls. Bare or empty-parameter `/v1/models` remains OpenAI-compatible. API-key filtering and Codex list/hide visibility apply to both halves; hidden native rows do not leak through `data`.
- `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` are real fallback slugs; a bare `gpt-5.6` is an input/pricing alias, not an invented bootstrap model.

## Constraints and Failure Modes

- The fallback is compatibility metadata, not pricing authority and not permission to enable long-context, Flex, or API Priority rates.
- If live release lookup and the cached client version are unavailable, the configured fallback version must still meet the newest bundled model's minimum version.
- If upstream adds fields, the fetcher preserves them. If upstream changes a known typed field, the refreshed snapshot replaces the fallback value.

## Example

`GET /v1/models` returns the standard OpenAI list. `GET /v1/models?client_version=0.144.1` returns `{ "models": [...], "object": "list", "data": [...] }`, byte-equivalent to `GET /backend-api/codex/models` after the same API-key filtering and visibility rewriting.
