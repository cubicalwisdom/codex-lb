# model-catalog-compat Specification

## Purpose
TBD - created by archiving change populate-bootstrap-model-metadata. Update Purpose after archive.
## Requirements
### Requirement: Bootstrap model catalog is available before refresh

Before the first successful upstream model-registry refresh, the system MUST serve a conservative static catalog of known Codex model slugs from both `GET /v1/models` and `GET /backend-api/codex/models`. This static catalog is a bundled fallback for startup/offline paths; refreshed upstream model-registry data remains the authoritative source once available. The bootstrap catalog MUST include `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex`, `gpt-5.3-codex-spark`, `gpt-5.2`, and `codex-auto-review`, and MUST NOT invent unverified variant slugs such as `gpt-5.5-pro` or a bare `gpt-5.6`. `gpt-5.3-codex` and `gpt-5.3-codex-spark` remain available for older pinned clients even though upstream removed them from the bundled rust-v0.144.x catalog, because the upstream backend still serves them.

#### Scenario: OpenAI-compatible models endpoint serves bootstrap slugs

- **GIVEN** the model registry has no refreshed upstream snapshot
- **WHEN** a client calls `GET /v1/models`
- **THEN** the response contains exactly the bootstrap model slugs
- **AND** the response includes `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`
- **AND** the response does not include `gpt-5.5-pro` or bare `gpt-5.6`

#### Scenario: Codex-native models endpoint serves GPT-5.6 bootstrap metadata

- **GIVEN** the model registry has no refreshed upstream snapshot
- **WHEN** a client calls `GET /backend-api/codex/models`
- **THEN** the GPT-5.6 Sol, Terra, and Luna entries include representative upstream context-window, visibility, speed-tier, and reasoning metadata
- **AND** Sol and Terra advertise `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`
- **AND** Luna advertises `low`, `medium`, `high`, `xhigh`, and `max`

### Requirement: Refreshed upstream model data remains authoritative

The system MUST treat a refreshed upstream model-registry snapshot as
authoritative over the static bootstrap catalog. Once that snapshot exists,
model catalog endpoints and model-behavior lookups MUST use the refreshed
snapshot instead of the static bootstrap catalog. Before refresh, websocket
preference lookup and account plan filtering MUST use bootstrap model metadata
when the requested slug matches a bootstrap entry.

#### Scenario: Refreshed snapshot replaces bootstrap catalog

- **GIVEN** the model registry has a refreshed upstream snapshot
- **WHEN** a client calls `GET /v1/models` or `GET /backend-api/codex/models`
- **THEN** the response is built from the refreshed snapshot
- **AND** bootstrap-only entries are not added to the response

#### Scenario: Bootstrap websocket preference is honored before refresh

- **GIVEN** the model registry has no refreshed upstream snapshot
- **WHEN** websocket preference is checked for a bootstrap model marked as websocket-preferred
- **THEN** the lookup returns that bootstrap preference

#### Scenario: Bootstrap plan metadata filters accounts before refresh

- **GIVEN** the model registry has no refreshed upstream snapshot
- **AND** a bootstrap model excludes a plan from its plan-availability metadata
- **WHEN** account selection is requested for that bootstrap model
- **THEN** accounts on excluded plans are not selected for that model

### Requirement: OpenAI-compatible model metadata uses backend context windows

When serving `GET /v1/models`, the system SHALL expose `metadata.context_window` as the upstream backend `context_window` budget by default. The system MUST NOT promote raw `max_context_window` values or hard-coded full-context guesses into `metadata.context_window`. Explicit operator context-window overrides remain the highest-priority reported-context value.

#### Scenario: GPT-5 Codex models are reported with the backend context window on /v1/models

- **WHEN** the upstream model catalog contains `gpt-5.5`, `gpt-5.4-mini`, `gpt-5.3-codex`, or `gpt-5.4` with `context_window=272000`
- **THEN** `GET /v1/models` returns each entry with `metadata.context_window=272000`

#### Scenario: raw max_context_window does not inflate /v1/models context_window

- **WHEN** the upstream model catalog contains a model with `context_window=272000` and `max_context_window=900000`
- **THEN** `GET /v1/models` returns that entry with `metadata.context_window=272000`

### Requirement: OpenAI-compatible model metadata preserves the backend input budget explicitly

When serving `GET /v1/models`, the system SHALL expose the upstream backend input/context budget in `metadata.input_context_window`. For models whose reported `metadata.context_window` is not operator-overridden, `metadata.context_window` and `metadata.input_context_window` SHOULD be equal. The system SHOULD expose `metadata.max_output_tokens` for known GPT-5 Codex models when that output-budget value is known; that value MUST NOT be used to inflate `metadata.context_window`.

#### Scenario: /v1/models exposes the 272k backend input budget explicitly

- **WHEN** the upstream model catalog contains a known GPT-5 Codex model with `context_window=272000`
- **THEN** `GET /v1/models` returns that model with `metadata.input_context_window=272000`
- **AND** `metadata.context_window=272000`

#### Scenario: Explicit reported-context overrides do not hide the backend input budget

- **WHEN** an operator override sets a model's reported `metadata.context_window` to `515000`
- **AND** the upstream model catalog contains that model with `context_window=272000`
- **THEN** `GET /v1/models` returns that model with `metadata.context_window=515000`
- **AND** `metadata.input_context_window=272000`

#### Scenario: /v1/models exposes max output budget for known GPT-5 Codex models

- **WHEN** `GET /v1/models` returns `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, or `gpt-5.3-codex`
- **THEN** the entry's metadata includes `max_output_tokens=128000`

### Requirement: Codex-native model catalog keeps backend catalog fields

When serving `GET /backend-api/codex/models`, the system MUST keep Codex-native model catalog semantics unchanged: the top-level `context_window` field remains the backend compact/input budget unless an explicit operator override applies, and upstream raw fields such as `max_context_window` remain available when upstream provides them. The `/v1/models` compatibility metadata MUST NOT mutate the native Codex endpoint.

#### Scenario: Native Codex route preserves compact budget

- **WHEN** the upstream model catalog contains `gpt-5.5` with `context_window=272000`
- **THEN** `GET /backend-api/codex/models` returns `gpt-5.5.context_window=272000`
- **AND** it does not replace that field with `400000`

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

### Requirement: GPT-5.6 bootstrap metadata matches the upstream bundled catalog

The GPT-5.6 bootstrap entries MUST match the metadata codex-lb serves from the Codex rust-v0.144.1 bundled catalog. Each entry MUST carry `context_window` and `max_context_window` of `372000`; `minimal_client_version: "0.144.0"`; `tool_mode: "code_mode_only"`; `use_responses_lite: true`; `apply_patch_tool_type: "freeform"`; `web_search_tool_type: "text_and_image"`; `supports_image_detail_original: true`; `truncation_policy: {"mode": "tokens", "limit": 10000}`; `comp_hash: "3000"`; `reasoning_summary_format: "experimental"`; `default_reasoning_summary: "none"`; `include_skills_usage_instructions: false`; `experimental_supported_tools: []`; `supports_search_tool: true`; `additional_speed_tiers: ["fast"]`; the `priority`/Fast service tier; `shell_type: "shell_command"`; `prefer_websockets: true`; and the upstream plan set including `edu_plus`, `edu_pro`, `enterprise_cbp_automation`, and `sci`. `multi_agent_version` MUST be `v2` for Sol and Terra and `v1` for Luna. Only Sol MUST carry the upstream non-null `availability_nux` message. Sol MUST default to `low` reasoning, while Terra and Luna MUST default to `medium`.

The large upstream `base_instructions` prompt and personality-templated `model_messages` object MUST NOT be bundled in the fallback; the first successful live registry refresh supplies them. Live refreshed data MUST remain authoritative and preserve `model_messages` plus unknown JSON-compatible fields losslessly.

#### Scenario: GPT-5.6 entries expose tool and multi-agent metadata

- **GIVEN** the model registry has no refreshed upstream snapshot
- **WHEN** a client calls `GET /backend-api/codex/models`
- **THEN** all three GPT-5.6 entries carry `tool_mode: "code_mode_only"`, `use_responses_lite: true`, `experimental_supported_tools: []`, and `minimal_client_version: "0.144.0"`
- **AND** `multi_agent_version` is `v2` for Sol and Terra and `v1` for Luna

#### Scenario: GPT-5.6 entries expose reasoning-summary and plan metadata

- **GIVEN** the model registry has no refreshed upstream snapshot
- **WHEN** a client calls `GET /backend-api/codex/models`
- **THEN** every GPT-5.6 entry carries `default_reasoning_summary: "none"`, `reasoning_summary_format: "experimental"`, and `comp_hash: "3000"`
- **AND** every GPT-5.6 entry's plans include `edu_plus`, `edu_pro`, `enterprise_cbp_automation`, and `sci`
- **AND** only Sol carries a non-null `availability_nux` message

### Requirement: Fallback client version covers the bootstrap catalog

The configured fallback Codex client version MUST be greater than or equal to the highest `minimal_client_version` in the bootstrap catalog, so a degraded-startup registry refresh still requests the newest bootstrap models.

#### Scenario: Degraded-startup refresh still requests GPT-5.6

- **GIVEN** live Codex release lookup fails and no version is cached
- **WHEN** model refresh requests the upstream catalog with the fallback client version
- **THEN** that version is at least `0.144.0`

### Requirement: Dashboard model metadata exposes supported reasoning efforts

`GET /api/models` MUST expose the supported and default reasoning efforts advertised by each public catalog entry, including `max` and `ultra` when upstream advertises them.

#### Scenario: Dashboard model list exposes GPT-5.6 reasoning efforts

- **GIVEN** Sol advertises `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`
- **WHEN** a client calls `GET /api/models`
- **THEN** Sol's `supportedReasoningEfforts` includes `max` and `ultra`
- **AND** `defaultReasoningEffort` reflects the catalog default

### Requirement: `/v1/models` negotiates the Codex catalog

`GET /v1/models` MUST return the same catalog payload as `GET /backend-api/codex/models` when `client_version` is non-empty, including native `models` entries, `object: "list"`, and OpenAI-compatible `data` entries. Each visible native model admitted by the local compatibility contract MUST have a corresponding `data` item with the same model id; when Codex visibility rewriting is enabled, hidden native entries MUST be absent from `data`. Stable model metadata MUST determine `data[].created` so separate native and negotiated requests remain equal across wall-clock boundaries. Requests without that parameter or with an empty value MUST retain the unchanged OpenAI-compatible list shape. API-key model filtering and visibility rules MUST apply in both negotiated and ordinary shapes.

#### Scenario: Codex client negotiates native metadata through `/v1`

- **WHEN** a client requests `/v1/models?client_version=0.144.1`
- **THEN** the response equals `/backend-api/codex/models`
- **AND** it contains `models`, `object: "list"`, and `data`
- **AND** every visible admitted native slug has a corresponding `data[].id`
- **AND** a bare or empty-parameter request still contains `object: "list"` and `data` without `models`

#### Scenario: API-key visibility applies to both catalog halves

- **GIVEN** an API key restricts the negotiated catalog to a subset of models
- **WHEN** it requests `/v1/models?client_version=0.144.1`
- **THEN** `models` follows the existing Codex filter or list/hide visibility contract
- **AND** `data` contains only the effectively visible allowed model ids
