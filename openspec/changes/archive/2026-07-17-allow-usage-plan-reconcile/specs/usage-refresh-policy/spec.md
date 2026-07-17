## ADDED Requirements

### Requirement: Plan reconciliation for workspace-less accounts is opt-in

Usage refresh MAY reconcile a stored plan type from an upstream payload only
when plan reconciliation is explicitly enabled and the account has no stored
workspace identity. Without that opt-in, plan mismatch remains non-destructive.
An account with stored workspace identity MUST NOT be reconciled from a
workspace-less or mismatched-workspace payload.

#### Scenario: Unknown workspace plan mismatch is non-destructive by default

- **GIVEN** an account has no stored workspace identity
- **WHEN** usage refresh receives a payload whose plan type conflicts with the stored non-unknown plan
- **AND** plan reconciliation is not enabled
- **THEN** no usage rows are written for the account
- **AND** the account status and plan type are not changed

#### Scenario: Legacy account plan mismatch can be reconciled when enabled

- **GIVEN** an account has no stored workspace identity
- **WHEN** usage refresh receives a payload whose only identity mismatch is plan type
- **AND** plan reconciliation is enabled
- **THEN** usage refresh updates the account plan type from the payload
- **AND** fresh usage rows are written for the account

#### Scenario: CodexNeo rows show the reconciled Codex IB plan

- **GIVEN** usage refresh has reconciled a legacy account plan type in Codex IB
- **AND** the matching CodexNeo registry row still has the previous plan value
- **WHEN** CodexNeo loads accounts with Codex IB usage
- **THEN** the returned account row plan uses the current Codex IB plan type
- **AND** the row still exposes the matched Codex IB account id and status fields

#### Scenario: CodexNeo rows show exhausted reconciled quota

- **GIVEN** a matched Codex IB account has an active stored status
- **AND** its latest applicable usage window is exhausted
- **WHEN** CodexNeo loads accounts with Codex IB usage
- **THEN** the returned account row status fields reflect `quota_exceeded`
- **AND** the visible availability and status labels say `Quota exceeded` instead of `Ready` or `Fresh`

#### Scenario: Workspace account is not reconciled from a workspace-less payload

- **GIVEN** an account has stored workspace identity
- **WHEN** usage refresh receives a payload that omits workspace identity and conflicts on plan type
- **AND** plan reconciliation is enabled
- **THEN** no usage rows are written for the account
- **AND** the account plan type and workspace metadata are not changed
