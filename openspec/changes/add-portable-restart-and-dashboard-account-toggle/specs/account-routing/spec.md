## ADDED Requirements

### Requirement: Dashboard account surfaces SHALL provide valid Pause and Resume transitions

Every Dashboard account presentation SHALL expose Resume for a paused account and Pause for an active, rate-limited, or quota-exceeded account. The actions SHALL use the existing backend state-transition endpoints and SHALL refresh Dashboard state after success. Re-auth-required and deactivated accounts SHALL NOT offer an invalid Pause or Resume transition.

#### Scenario: Operator pauses an account from Dashboard

- **GIVEN** an eligible non-paused account is visible in Dashboard card or list mode
- **WHEN** the operator selects Pause
- **THEN** Dashboard SHALL call the account pause transition
- **AND** SHALL refresh the account state to show Resume after success

#### Scenario: Operator resumes a paused account from Dashboard

- **GIVEN** a paused account is visible in Dashboard card or list mode
- **WHEN** the operator selects Resume
- **THEN** Dashboard SHALL call the account resume transition
- **AND** SHALL refresh the account state to show Pause after success

#### Scenario: Account requires recovery

- **GIVEN** an account is re-auth-required or deactivated
- **WHEN** Dashboard renders its actions
- **THEN** it SHALL NOT offer Pause or Resume for that account
