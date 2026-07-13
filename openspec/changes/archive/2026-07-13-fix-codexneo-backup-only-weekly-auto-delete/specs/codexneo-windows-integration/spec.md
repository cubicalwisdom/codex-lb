## ADDED Requirements

### Requirement: Exact-zero weekly auto-delete SHALL include Backup-only snapshots

When the persisted weekly-quota auto-delete preference is enabled, CodexNeo SHALL evaluate managed Codex Home and app-owned Backup snapshots for the same canonical account identity. It SHALL remove an eligible account from the canonical routing pool and every matching managed location only when a current weekly-duration usage sample proves exactly 0% remaining and the account is quota-exceeded. It SHALL retain aggregate usage statistics and audit history.

#### Scenario: Eligible account exists only in Backup

- **GIVEN** an account has no managed Codex Home snapshot
- **AND** it has an app-owned Backup snapshot
- **AND** its latest weekly-duration usage sample confirms exactly 0% remaining
- **AND** its account status is `quota_exceeded`
- **WHEN** the weekly-quota auto-delete rule runs
- **THEN** the account's canonical routing-pool credential and matching Backup snapshot/registry entry SHALL be removed
- **AND** its aggregate usage and audit history SHALL remain retained

#### Scenario: Unknown or nonzero weekly usage is retained

- **GIVEN** an account has only an app-owned Backup snapshot
- **AND** its weekly usage is unknown or above 0% remaining
- **WHEN** the weekly-quota auto-delete rule runs
- **THEN** the account and its Backup snapshot SHALL remain unchanged
