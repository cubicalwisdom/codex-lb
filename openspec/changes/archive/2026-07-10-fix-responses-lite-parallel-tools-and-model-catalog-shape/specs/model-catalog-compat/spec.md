## MODIFIED Requirements

### Requirement: `/v1/models` negotiates the Codex catalog

`GET /v1/models` MUST return the same catalog payload as `GET /backend-api/codex/models` when `client_version` is non-empty, including native `models` entries, `object: "list"`, and OpenAI-compatible `data` entries. Each visible native model admitted by the local compatibility contract MUST have a corresponding `data` item with the same model id; when Codex visibility rewriting is enabled, hidden native entries MUST be absent from `data`. Stable model metadata MUST determine `data[].created` so separate native and negotiated requests remain equal across wall-clock boundaries. Requests without `client_version` or with an empty value MUST retain the unchanged OpenAI-compatible list shape. API-key model filtering and visibility rules MUST apply in both negotiated and ordinary shapes.

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
