# add-responses-lifecycle-parity

## Why

Codex-LB can execute synchronous and streaming `POST /v1/responses` calls, but OpenAI SDK clients cannot use the surrounding Responses lifecycle. Stored and background responses, retrieve/cancel/delete, input-item listing, input-token counting, and Conversations currently return route-level errors or are rejected before execution.

## What Changes

- Add API-key-scoped durable storage for Responses and Conversations resources.
- Support `store=true` and locally managed `background=true` without forwarding unsupported persistence flags to the ChatGPT-backed upstream.
- Add retrieve, cancel, delete, and input-item routes for locally stored responses.
- Add Conversations CRUD and item CRUD/list routes and expand conversation context before upstream execution.
- Add a deterministic local input-token count compatibility route for text/tool payloads, with explicit errors for opaque file/image inputs that cannot be counted locally.
- Preserve explicit `unsupported_parameter` responses for generation controls that the ChatGPT-backed upstream cannot honor.

## Non-goals

- Claiming hosted-tool, sampling-control, prompt-cache-retention, or billing-token parity where the private upstream does not expose an equivalent contract.
- Adding unrelated OpenAI platform APIs such as audio, video, batches, embeddings, fine-tuning, or vector stores.
- Restarting Codex Desktop or the portable Electron app during implementation or verification.

## Capabilities

### Modified Capabilities

- `responses-api-compat`
- `database-migrations`
