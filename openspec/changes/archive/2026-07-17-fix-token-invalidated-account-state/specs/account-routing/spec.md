## ADDED Requirements

### Requirement: Re-authentication-required accounts are not selectable

When an account credential/session is invalidated but the upstream account is
not known to be disabled, the system MUST mark the account `reauth_required`.
The selector MUST remove `reauth_required` accounts from every routing strategy
and hard-affinity fallback until the account is re-authenticated. Operator
pickers that configure single-account routing or account-scoped routing MUST
only offer accounts that are not hard-blocked by paused, reauth-required, or
deactivated status.

#### Scenario: Token invalidated account leaves the pool

- **GIVEN** account A is `reauth_required`
- **AND** account B is active
- **WHEN** a proxy request selects an account
- **THEN** account B is selected
- **AND** account A is not considered an eligible candidate

#### Scenario: Hard-blocked account cannot be newly selected for scoped routing

- **GIVEN** account A is paused, reauth-required, or deactivated
- **WHEN** an operator opens a scoped account-routing picker
- **THEN** account A is not offered as a new selectable account

#### Scenario: Re-authentication-required account cannot be paused into resumable state

- **GIVEN** account A is `reauth_required`
- **WHEN** an operator attempts to pause account A
- **THEN** the request is rejected
- **AND** account A remains `reauth_required`
