## ADDED Requirements

### Requirement: Zero-capacity non-5h primary usage does not keep free accounts rate-limited

Account status derivation MUST ignore a zero-capacity primary usage row whose
window is not the canonical 5-hour window when normalized quota state reports
available monthly quota for a free-plan account.

#### Scenario: Zero-capacity monthly primary does not keep free accounts rate-limited
- **GIVEN** a free-plan account whose persisted status is `rate_limited`
- **AND** its latest primary usage row is a zero-capacity non-5h window (for example a monthly upstream snapshot)
- **AND** its normalized quota state reports available monthly quota
- **WHEN** codex-lb derives account status for account summaries or proxy runtime state
- **THEN** the non-5h primary row is ignored for rate-limit recovery
- **AND** the account is treated as `active`
- **AND** downstream account views keep the monthly-only quota presentation
