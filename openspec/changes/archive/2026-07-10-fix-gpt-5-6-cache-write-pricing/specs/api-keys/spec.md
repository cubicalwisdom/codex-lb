## ADDED Requirements

### Requirement: GPT-5.6 Standard pricing accounts for cache writes

GPT-5.6 Standard short-context pricing MUST separate ordinary input, cache-read input, cache-write input, and output tokens. Cache-write prices per one million tokens MUST be `$6.25` for Sol, `$3.125` for Terra, and `$1.25` for Luna. Long-context, Flex, and API Priority rates are outside this change.

#### Scenario: Sol usage contains reads and writes

- **WHEN** one million `gpt-5.6-sol` input tokens contain 200,000 cache-read tokens and 100,000 cache-write tokens
- **THEN** 700,000 tokens are charged at the ordinary `$5/M` input rate
- **AND** 200,000 tokens are charged at the `$0.50/M` cache-read rate
- **AND** 100,000 tokens are charged at the `$6.25/M` cache-write rate

#### Scenario: Detail counters exceed total input

- **WHEN** cache-read and cache-write detail counters together exceed total input tokens
- **THEN** each category is clamped so their sum does not exceed total input
- **AND** ordinary billable input never becomes negative

### Requirement: Generic GPT-5.6 pricing resolves to Sol

The pricing resolver MUST map the exact official `gpt-5.6` alias to `gpt-5.6-sol` and MUST preserve explicit Sol, Terra, and Luna variant resolution.

#### Scenario: Generic alias is priced

- **WHEN** cost accounting receives model `gpt-5.6`
- **THEN** it uses the `gpt-5.6-sol` Standard price record
- **AND** it does not fall through to legacy `gpt-5` pricing

### Requirement: GPT-5.6 Codex Fast accounting avoids stacked premiums

For ChatGPT-authenticated GPT-5.6 traffic, cost accounting MUST retain literal token counts and MUST NOT combine API Priority prices with a separate Codex subscription-Fast multiplier. Until an authoritative GPT-5.6 subscription-Fast factor is available, API-equivalent dollar cost MUST use the configured GPT-5.6 Standard price record exactly once; upstream account credit windows remain authoritative for subscription consumption.

#### Scenario: Fast alias is estimated without double-counting

- **WHEN** a `gpt-5.6-sol-fast` request is normalized to the upstream priority service tier
- **AND** the request contains one million ordinary input tokens
- **THEN** the API-equivalent input estimate is `$5.00`
- **AND** the stored input token count remains one million
