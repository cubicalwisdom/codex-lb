## MODIFIED Requirements

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

## ADDED Requirements

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

`GET /v1/models` MUST return the same catalog payload as `GET /backend-api/codex/models` when `client_version` is non-empty, including native `models` entries and OpenAI-compatible `object`/`data` fields. Requests without that parameter or with an empty value MUST retain the unchanged OpenAI-compatible list shape. API-key model filtering and visibility rules MUST apply in both negotiated and ordinary shapes.

#### Scenario: Codex client negotiates native metadata through `/v1`

- **WHEN** a client requests `/v1/models?client_version=0.144.1`
- **THEN** the response equals `/backend-api/codex/models` and contains `models`, `object`, and `data`
- **AND** a bare or empty-parameter request still contains `object: list` and `data`
