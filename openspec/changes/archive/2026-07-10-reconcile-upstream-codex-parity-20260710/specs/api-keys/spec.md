## ADDED Requirements

### Requirement: API-key reasoning policies accept GPT-5.6 max and ultra

API-key creation and update MUST accept `max` and `ultra` reasoning efforts in addition to existing values. An enforced `ultra` request MUST be represented to the user as `ultra` and normalized to the upstream `max` wire value where required by GPT-5.6.

#### Scenario: API key enforces ultra reasoning

- **WHEN** an operator creates or updates an API key with reasoning effort `ultra`
- **THEN** validation succeeds and the policy is stored
- **AND** a compatible GPT-5.6 request forwards `max` upstream without losing the configured display value
