## ADDED Requirements

### Requirement: Stored API key allowed-model values are normalized

When reading stored `allowed_models`, JSON `null`, blank strings, and non-string
array entries MUST be ignored and MUST NOT become model names.

#### Scenario: Stored null allowed-model entries are ignored

- **GIVEN** an API key row stores `allowed_models` as `[null, "gpt-5.2", 42, ""]`
- **WHEN** the key policy is loaded
- **THEN** the effective allowed model list is `["gpt-5.2"]`
- **AND** `null` is not converted to `"None"`
