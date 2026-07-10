## ADDED Requirements

### Requirement: Refreshed Codex model metadata is lossless

When the model fetcher stores a refreshed upstream model entry, it MUST retain every JSON-compatible field supplied by upstream. `GET /backend-api/codex/models` MUST return upstream extension fields that are not replaced by an explicit local typed value or operator override. The service MUST NOT maintain a denylist that removes `model_messages`.

#### Scenario: Personality messages are supplied upstream

- **WHEN** an upstream model entry contains `model_messages` and an otherwise unknown future capability field
- **THEN** the refreshed registry retains both fields unchanged
- **AND** `GET /backend-api/codex/models` returns both fields unchanged

### Requirement: GPT-5.6 models remain in bootstrap contract coverage

Bootstrap catalogue regression coverage MUST include `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` with the minimal client versions configured by the runtime.

#### Scenario: Registry has not refreshed

- **WHEN** either model catalogue endpoint uses the bootstrap snapshot
- **THEN** all three GPT-5.6 model slugs are present
- **AND** the native entries expose their configured minimal client version
