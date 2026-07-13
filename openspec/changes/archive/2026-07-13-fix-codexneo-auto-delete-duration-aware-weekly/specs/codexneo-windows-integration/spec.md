## MODIFIED Requirements

### Requirement: Exact-zero weekly auto-delete SHALL include Backup-only snapshots

When the persisted weekly-quota auto-delete preference is enabled, CodexNeo SHALL determine the latest weekly usage by actual window duration rather than its legacy persistence slot. It SHALL evaluate managed Codex Home and app-owned Backup snapshots for the same canonical account identity. It SHALL remove an eligible account from the canonical routing pool and every matching managed location only when the effective weekly-duration usage sample proves exactly 0% remaining and the account is quota-exceeded. It SHALL retain aggregate usage statistics and audit history.

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

#### Scenario: Weekly-only usage is persisted in the primary slot

- **GIVEN** an account has no current secondary usage record
- **AND** its latest primary record has the configured weekly duration and exactly 0% remaining
- **AND** its account status is `quota_exceeded`
- **WHEN** the weekly-quota auto-delete rule runs
- **THEN** it SHALL treat that primary record as the effective weekly value
- **AND** it SHALL remove the eligible account and any matching managed Backup snapshot/registry entry

#### Scenario: Short-window primary data does not qualify as weekly data

- **GIVEN** an account's latest primary record is a genuine short-window usage record
- **AND** no weekly-duration record proves exactly 0% remaining
- **WHEN** the weekly-quota auto-delete rule runs
- **THEN** the account and its managed snapshots SHALL remain unchanged
