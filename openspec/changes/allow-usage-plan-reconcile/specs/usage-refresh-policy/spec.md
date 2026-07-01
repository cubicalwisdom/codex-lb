## MODIFIED Requirements

### Requirement: Usage refresh is account-slot scoped

Usage refresh MUST write usage and change account status only for the credential slot being refreshed. It MUST NOT apply a payload that proves a different workspace identity to the target account.

#### Scenario: Mismatched workspace payload is ignored

- **GIVEN** an account has stored workspace identity
- **WHEN** usage refresh receives a payload for a different workspace
- **THEN** no usage rows are written for the account
- **AND** the account status, plan type, workspace metadata, and seat type are not changed

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
