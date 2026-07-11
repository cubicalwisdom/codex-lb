## ADDED Requirements

### Requirement: Focused Codex parity smoke selection

The project MUST register a semantic `codex_parity_smoke` pytest marker and provide a documented `test-codex-parity-smoke` Make target that runs only tests carrying that marker with the repository's standard pytest safety options and strict marker validation. The curated selection MUST cover the approved Responses Lite, compact, HTTP bridge, native WebSocket, and negotiated model-catalog contracts. Marker metadata MUST NOT skip, rewrite, or otherwise change those tests when they run through existing full-suite targets.

The focused target MUST fail when a selected regression fails or when the semantic selection is empty. It MUST NOT invoke frontend builds, packaging, migrations, Docker, Helm, the complete unit/integration suites, or portable-runtime operations. Existing `ci-fast`, `ci`, GitHub required checks, affected-suite expectations, and release gates MUST remain unchanged and MUST NOT delegate their completion evidence to this focused target.

#### Scenario: Developer runs the focused Codex parity loop

- **WHEN** a developer runs `make test-codex-parity-smoke`
- **THEN** pytest selects exactly the tests carrying `codex_parity_smoke`
- **AND** the command returns nonzero if any selected case fails
- **AND** it does not run unrelated broad build or test targets

#### Scenario: Full verification remains authoritative

- **WHEN** a proxy or Codex API behavior change is prepared for final commit or release
- **THEN** the focused runner MAY provide early feedback
- **BUT** the existing full affected suites, static checks, OpenSpec validation, and required CI/release gates remain authoritative
- **AND** no existing test is skipped because it lacks the focused marker

#### Scenario: Empty selection fails safely

- **WHEN** marker drift or configuration error leaves no collected `codex_parity_smoke` tests
- **THEN** the focused target exits nonzero
- **AND** it does not report a successful compatibility check
