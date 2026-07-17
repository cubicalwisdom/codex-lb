# codexneo-api-provider-compatibility Specification

## Purpose
TBD - created by archiving change fix-codexneo-native-api-provider. Update Purpose after archive.
## Requirements
### Requirement: CodexNeo uses the native Codex provider endpoint
The system SHALL default the CodexNeo Codex API provider URL to `http://127.0.0.1:2455/backend-api/codex` and SHALL use that URL for native Codex model discovery and managed `openai_base_url` configuration.

#### Scenario: New settings use the native local endpoint
- **WHEN** no CodexNeo API provider URL has been saved
- **THEN** the settings response and dashboard guidance SHALL use `http://127.0.0.1:2455/backend-api/codex`

#### Scenario: Provider config is set from the default
- **WHEN** an administrator sets the Codex API provider without supplying a different URL
- **THEN** the managed Codex config SHALL contain `openai_base_url = "http://127.0.0.1:2455/backend-api/codex"`

### Requirement: Legacy local provider settings migrate narrowly
The system SHALL map the normalized exact legacy CodexNeo URL `http://127.0.0.1:2455/v1` to `http://127.0.0.1:2455/backend-api/codex` and atomically persist that migration. The system MUST preserve every other serialized setting value and every other valid operator-supplied URL unchanged.

#### Scenario: Exact legacy local value is migrated
- **WHEN** CodexNeo reads settings containing `http://127.0.0.1:2455/v1` with optional surrounding whitespace or trailing slash
- **THEN** the returned and persisted provider URL SHALL be `http://127.0.0.1:2455/backend-api/codex`

#### Scenario: Custom v1 provider remains unchanged
- **WHEN** CodexNeo reads or saves a valid provider URL other than the exact legacy local value, including a custom URL ending in `/v1`
- **THEN** the normalized custom URL SHALL remain unchanged

#### Scenario: Unknown persisted setting survives migration
- **WHEN** a legacy local provider setting is stored beside an unrecognized serialized setting
- **THEN** the migration SHALL replace only the provider URL and SHALL preserve the unrecognized setting unchanged

### Requirement: Provider connectivity test validates the native catalog
The CodexNeo provider test SHALL request `GET <configured-base-url>/models` and SHALL report success only for a successful JSON response containing a top-level `models` list.

#### Scenario: Native model catalog passes
- **WHEN** the configured endpoint returns HTTP success with a JSON object whose `models` field is a list
- **THEN** the provider test SHALL report success

#### Scenario: Generic OpenAI model catalog fails compatibility validation
- **WHEN** the configured endpoint returns HTTP success with an OpenAI-compatible `object` and `data` envelope but no top-level `models` list
- **THEN** the provider test SHALL report failure and explain that the Codex-native model catalog is missing

#### Scenario: Invalid JSON fails compatibility validation
- **WHEN** the configured endpoint returns HTTP success with a body that is not valid JSON
- **THEN** the provider test SHALL report failure without writing provider configuration

#### Scenario: Redirected catalog fails compatibility validation
- **WHEN** the configured endpoint returns an HTTP redirect whose body otherwise contains a top-level `models` list
- **THEN** the provider test SHALL report failure without following the redirect or writing provider configuration
