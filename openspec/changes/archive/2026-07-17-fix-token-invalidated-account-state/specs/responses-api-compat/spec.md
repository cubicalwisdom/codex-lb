## ADDED Requirements

### Requirement: Token-invalidated compact auth failures require re-authentication and fail over

When a `/backend-api/codex/responses/compact` request receives an upstream
`401 token_invalidated` response for the selected account, the proxy MUST
attempt one forced token refresh and retry the compact request on that same
account. If the refreshed retry also returns `401`, the proxy MUST mark the
account `reauth_required`, exclude it from the current compact request, and try
another eligible account when one is available.

#### Scenario: Refreshed compact token invalidation uses another account

- **GIVEN** at least two accounts are eligible for a compact request
- **AND** the selected account returns `401 token_invalidated` for compact before and after a forced refresh
- **WHEN** another eligible account can complete the compact request
- **THEN** the downstream compact response succeeds from the second account
- **AND** the selected account is marked `reauth_required`
- **AND** the selected account is excluded from further attempts for that compact request

### Requirement: Token-invalidated pre-visible auth failures require re-authentication and fail over

Before any downstream-visible output is emitted, a repeated upstream
`401 token_invalidated` response after forced refresh MUST mark the selected
account `reauth_required`, exclude that account from the current request, and
try another eligible account when replay is safe. The proxy MUST preserve the
existing no-replay rule for unsafe continuations and after visible output.

#### Scenario: Pre-visible token invalidation uses another account

- **GIVEN** at least two accounts are eligible for a pre-visible proxy request
- **AND** the selected account returns `401 token_invalidated` before and after a forced refresh
- **WHEN** another eligible account can complete the request
- **THEN** the downstream request succeeds from another account
- **AND** the selected account is marked `reauth_required`

#### Scenario: Non-replayable pre-visible auth failure still records the account

- **GIVEN** a pre-visible HTTP bridge continuation cannot be replayed safely
- **AND** the selected account returns `401 token_invalidated`
- **WHEN** the proxy forwards the terminal auth error instead of replaying
- **THEN** the selected account is marked `reauth_required`
- **AND** the unsafe continuation is not replayed
