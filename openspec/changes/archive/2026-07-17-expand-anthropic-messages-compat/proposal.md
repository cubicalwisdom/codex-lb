## Why

The first Anthropic Messages facade made Claude Desktop text-and-tool conversations work through the active portable codex-lb runtime. It intentionally excluded attachments, cache controls, message batches, context management, and explicit overload recovery. Those features are now required for a complete local Anthropic-compatible endpoint.

## What Changes

- Accept and safely translate supported Anthropic image and document blocks to the existing Responses image/file input shapes.
- Preserve cache-control intent with deterministic Responses prompt-cache affinity while reporting only cache usage supplied by the upstream response.
- Add an Anthropic-compatible durable Message Batches API with create, get, list, cancel, delete, and JSONL-results routes.
- Add context-budget preflight, supported compaction-block round-tripping, Claude Desktop-only automatic near-limit compaction, and explicit observability of compaction/over-limit outcomes.
- Add bounded local recovery for account-capacity and transient upstream failures without increasing the active account concurrency cap by default.

## Impact

- Extends the existing `/v1/messages` family only; existing OpenAI-compatible clients and normal `/v1/models` discovery remain unchanged.
- Adds persistent batch resources and a migration, plus resumable local batch execution.
- Reuses the canonical Responses execution, account selection, quota settlement, file ownership, and cache-affinity mechanisms.
- Requires new focused integration coverage and a portable mirror refresh before the live endpoint is restarted.
