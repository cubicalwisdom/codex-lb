## Context

Responses usage reports total input tokens plus disjoint detail counters such as cache reads (`cached_tokens`) and cache writes (`cache_write_tokens`). The existing calculator removes cache reads from ordinary input but has no cache-write category, so a cache write is charged at the ordinary input rate and then lost from the persisted breakdown.

OpenAI publishes GPT-5.6 Standard short-context cache-write rates at 1.25 times ordinary input: Sol `$6.25/M`, Terra `$3.125/M`, and Luna `$1.25/M`. The generic `gpt-5.6` API alias denotes Sol, but the local wildcard order currently resolves it as legacy `gpt-5`.

Codex Fast for ChatGPT-authenticated accounts consumes subscription credits, whereas `service_tier=priority` on the public API uses a separate API price table. OpenAI currently documents Fast multipliers for older Codex models but does not publish one for GPT-5.6. The upstream account usage windows already remain the source of truth for actual subscription-credit depletion.

## Decisions

### 1. Store literal cache-write tokens as a separate nullable request-log field

The response model, in-memory usage value, request-log settlement path, ORM model, repository, and API schema will carry `cache_write_tokens`. Existing rows remain `NULL` because the missing detail cannot be reconstructed safely.

### 2. Split total input into ordinary, cache-read, and cache-write categories

The calculator will clamp cache reads to total input, then clamp cache writes to the remaining input. Ordinary billable input is the remainder. A model without an explicit cache-write price falls back to its effective ordinary-input rate, preserving prior totals for existing models.

Example: one million GPT-5.6 Sol input tokens containing 200,000 cache reads and 100,000 cache writes are priced as 700,000 ordinary input tokens, 200,000 cached-read tokens, and 100,000 cache-write tokens.

### 3. Add an exact generic GPT-5.6 alias before variant wildcards

`gpt-5.6` resolves to `gpt-5.6-sol`. Explicit Sol, Terra, and Luna variants keep their more specific wildcard mappings.

### 4. Do not manufacture a GPT-5.6 subscription-Fast dollar rate

Token counters remain literal. GPT-5.6 pricing in this change contains only Standard short-context rates, so a Fast/priority-tagged Codex request cannot receive both a subscription multiplier and an API Priority premium. The dashboard's upstream credit windows continue to show actual account depletion.

If OpenAI later publishes a GPT-5.6 Fast credit multiplier, it should be represented as a separate credit-consumption metric rather than mutating token counts or API-equivalent dollar cost.

## Risks / Trade-offs

- Existing request rows cannot be corrected for cache-write cost. They retain their stored totals and a null cache-write count.
- Some upstreams may report inconsistent detail counters. Clamping prevents negative ordinary-input counts or a total detail count above input.
- Fast API-equivalent cost remains Standard for GPT-5.6 in this authenticated-Codex path. This is deliberate until a separate, authoritative subscription-credit factor exists.
