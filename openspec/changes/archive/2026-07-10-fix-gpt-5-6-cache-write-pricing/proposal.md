## Why

GPT-5.6 request costs are currently understated when the upstream reports prompt-cache writes because `cache_write_tokens` is accepted only as untyped extra data and is neither persisted nor priced. The generic `gpt-5.6` model alias also falls through to the legacy `gpt-5` wildcard, producing the wrong Sol estimate.

Codex subscription Fast consumption and OpenAI API Priority pricing are different accounting systems. Applying both a subscription-credit multiplier and Priority API rates would double-count the Fast premium, while OpenAI does not currently publish a GPT-5.6 subscription-Fast multiplier.

## What Changes

- Parse `input_tokens_details.cache_write_tokens` as a typed usage field.
- Persist cache-write tokens on request logs and expose them in request-log API/UI cost detail.
- Price GPT-5.6 cache writes at the published Standard short-context rates for Sol, Terra, and Luna.
- Resolve the official generic `gpt-5.6` alias to `gpt-5.6-sol` before the legacy `gpt-5*` wildcard.
- Keep literal token counts and use one API-equivalent dollar-pricing path for GPT-5.6 Fast requests; do not stack an undocumented subscription-Fast multiplier on API Priority pricing.
- Add the request-log schema migration and portable-runtime mirror required for the active Windows distribution.

## Non-Goals

- GPT-5.6 long-context pricing.
- GPT-5.6 Flex pricing.
- GPT-5.6 API Priority rate-table entries.
- Deriving subscription-credit consumption from raw request tokens.
- Repricing historical rows that did not store cache-write tokens.

## Capabilities

### Modified Capabilities

- `responses-api-compat`: Typed cache-write usage details are retained for accounting.
- `api-keys`: GPT-5.6 alias resolution and cache-write cost calculation are accurate without Fast double-counting.
- `database-migrations`: Request logs gain nullable cache-write token storage.
- `frontend-architecture`: Request-log token and cost detail identifies cache writes separately.

## Impact

- OpenAI response usage models and proxy request finalization paths.
- Shared usage pricing and request-log cost reconstruction.
- Request-log ORM/repository/API schema and Alembic graph.
- Recent-request detail in the dashboard.
- Portable backend source and migration mirrors.
