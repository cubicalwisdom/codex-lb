# Usage Refresh Policy Delta

## ADDED Requirements

### Requirement: User-paused accounts survive auth sync

The system SHALL preserve an operator-paused account state when an auth import, Codex Home sync, or startup discovery sync refreshes the same account's token material.

#### Scenario: Auth sync updates tokens without unpausing

- **GIVEN** an account is `paused` by an operator in the Accounts tab
- **WHEN** the same upstream account is re-imported or refreshed from Codex Home auth material with an otherwise active auth snapshot
- **THEN** the stored account remains `paused`
- **AND** the account's token and refresh metadata MAY be updated
- **AND** only an explicit Reactivate/Resume action SHALL clear the paused state
