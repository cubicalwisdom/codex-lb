# usage-refresh-policy Specification

## Purpose
Define how background usage refresh reacts to auth-like failures without permanently hammering bad accounts.
## Requirements
### Requirement: Usage refresh cools down repeated auth-like failures

Background usage refresh MUST apply a cooldown to accounts that repeatedly fail usage refresh with ambiguous `401` or `403` responses. Accounts in that cooldown window MUST be skipped until the cooldown expires or a later successful refresh clears it.

#### Scenario: Ambiguous usage 401 enters cooldown
- **WHEN** usage refresh receives a `401` that does not match a permanent deactivation signal
- **THEN** the account is not deactivated immediately
- **AND** subsequent refresh cycles skip the account until the cooldown window expires

#### Scenario: Successful refresh clears cooldown
- **WHEN** a later usage refresh succeeds for an account that had been cooled down
- **THEN** the cooldown is cleared
- **AND** normal refresh cadence resumes

### Requirement: Usage refresh deactivates on clear deactivation signals

The system MUST deactivate accounts when usage refresh receives a permanent
account deactivation signal. At minimum, `402`, `404`, and `401` responses
whose message explicitly indicates that the OpenAI account has been deactivated
MUST be treated as deactivation signals. Credential/session invalidation codes
such as `token_invalidated` and `token_expired` MUST be marked
`reauth_required` instead of `deactivated`.

#### Scenario: Usage 401 deactivation message deactivates the account

- **WHEN** usage refresh receives HTTP `401`
- **AND** the upstream message states that the OpenAI account has been deactivated
- **THEN** the account is marked `deactivated`
- **AND** later usage refresh cycles skip that account

#### Scenario: Usage 401 token invalidated requires re-authentication

- **WHEN** usage refresh receives HTTP `401`
- **AND** the upstream error code is `token_invalidated`
- **THEN** the account is marked `reauth_required`
- **AND** later usage refresh cycles skip that account until re-authentication

### Requirement: Usage capacity recognizes upstream ChatGPT plan types

The system MUST recognize account plan types returned by upstream ChatGPT auth and usage payloads when calculating absolute usage capacity. `prolite` MUST be treated as a supported account plan with Plus x5 capacity values (`1125.0` primary and `37800.0` secondary), while preserving the stored plan type value for display and request-log context.

#### Scenario: Pro Lite account contributes aggregate remaining credits

- **GIVEN** an active account whose stored `plan_type` is `prolite`
- **AND** its latest primary and secondary usage rows report `used_percent` below 100
- **WHEN** the system builds usage window summaries or per-account remaining credit values
- **THEN** the account contributes `1125.0` primary capacity and `37800.0` secondary capacity
- **AND** the computed remaining credits are non-zero according to the reported usage percent

### Requirement: Pro Lite accounts are eligible for Pro-gated models

The system MUST treat stored `prolite` account plan types as Pro-equivalent when evaluating model registry plan eligibility, while preserving the stored `prolite` value for display and request-log context.

#### Scenario: Pro Lite account can be selected for a Pro-gated model

- **GIVEN** an active account whose stored `plan_type` is `prolite`
- **AND** its latest primary and secondary usage rows are below the configured usage threshold
- **AND** the requested model is allowed for `pro` accounts by the model registry
- **WHEN** proxy account selection evaluates eligible accounts for the requested model
- **THEN** the Pro Lite account remains eligible for selection
- **AND** the selection does not fail with `no_accounts`

### Requirement: Background usage refresh reconciles recoverable blocked statuses
Background usage refresh SHALL reconcile persisted `rate_limited` and `quota_exceeded` accounts back to `active` after it writes fresh usage snapshots that prove the blocked window has recovered. This reconciliation SHALL be recovery-only and SHALL NOT promote `active` accounts into blocked statuses.

#### Scenario: Scheduler recovers a stale rate-limited account from fresh primary usage
- **WHEN** an account is persisted as `rate_limited`
- **AND** the persisted rate-limit reset deadline has already elapsed
- **AND** a later background usage refresh writes a fresh primary usage row recorded after the persisted block marker
- **AND** that primary usage row reports usage below `100%`
- **THEN** the scheduler marks the account `active`
- **AND** it clears persisted `reset_at` and `blocked_at`

#### Scenario: Scheduler recovers a legacy rate-limited account without a block marker
- **WHEN** an account is persisted as `rate_limited`
- **AND** the persisted rate-limit reset deadline has already elapsed
- **AND** the account has no persisted block marker
- **AND** a later background usage refresh writes a recent primary usage row that reports usage below `100%`
- **THEN** the scheduler marks the account `active`
- **AND** it clears persisted `reset_at`

#### Scenario: Scheduler preserves legacy rate-limited accounts without recent primary usage
- **WHEN** an account is persisted as `rate_limited`
- **AND** the persisted rate-limit reset deadline has already elapsed
- **AND** the account has no persisted block marker
- **AND** the latest primary usage row is not recent enough to prove background refresh recovery
- **THEN** the scheduler leaves the account `rate_limited`

#### Scenario: Scheduler preserves an unexpired rate-limit cooldown
- **WHEN** an account is persisted as `rate_limited`
- **AND** its persisted rate-limit reset deadline is still in the future
- **AND** a later background usage refresh writes a fresh primary usage row recorded after the persisted block marker
- **AND** that primary usage row reports usage below `100%`
- **THEN** the scheduler leaves the account `rate_limited`

#### Scenario: Scheduler recovers a stale quota-exceeded account from fresh secondary usage
- **WHEN** an account is persisted as `quota_exceeded`
- **AND** a later background usage refresh writes a fresh secondary usage row that reports usage below `100%`
- **THEN** the scheduler marks the account `active`
- **AND** it clears persisted `reset_at` and `blocked_at`

#### Scenario: Scheduler does not tighten active accounts into blocked statuses
- **WHEN** background usage refresh evaluates an account currently persisted as `active`
- **THEN** the scheduler does not change that account to `rate_limited` or `quota_exceeded`

#### Scenario: Scheduler ignores stale pre-block recovery evidence
- **WHEN** an account is persisted as `rate_limited`
- **AND** the latest primary usage row was recorded before the persisted block marker
- **THEN** the scheduler leaves the account blocked

#### Scenario: Scheduler skips recovery when the account row changed concurrently
- **WHEN** background usage refresh determines that a blocked account is recoverable
- **AND** the persisted account status or reset markers change before the scheduler writes recovery
- **THEN** the scheduler skips the stale recovery write

#### Scenario: Scheduler clears stale deactivation reasons on recovery
- **WHEN** background usage refresh recovers a `rate_limited` or `quota_exceeded` account to `active`
- **THEN** the scheduler writes `deactivation_reason` as `NULL`

### Requirement: Usage refresh does not trust elapsed reset windows

Background usage refresh MUST treat a latest usage row as stale when that row's `reset_at` timestamp is in the past, even when the row's `recorded_at` timestamp is still within the normal refresh interval.

#### Scenario: Past reset_at bypasses freshness

- **GIVEN** the latest usage row was recorded within the normal refresh interval
- **AND** that row's `reset_at` timestamp has already elapsed
- **WHEN** background usage refresh evaluates the account
- **THEN** the row is treated as stale
- **AND** codex-lb attempts a fresh upstream usage fetch

### Requirement: Blocked accounts refresh once their reset deadline elapses

When an account is `RATE_LIMITED` or `QUOTA_EXCEEDED` and its persisted `reset_at` timestamp has elapsed, background usage refresh MUST bypass the normal freshness interval so the account can recover from the upstream post-reset state. The bypass MUST NOT apply before the persisted reset deadline elapses.

#### Scenario: Quota-exceeded account with fresh primary row reaches reset deadline

- **GIVEN** an account is marked `QUOTA_EXCEEDED`
- **AND** the account's persisted `reset_at` timestamp has elapsed
- **AND** the latest primary usage row is still within the normal refresh interval
- **WHEN** background usage refresh evaluates the account
- **THEN** codex-lb performs an upstream usage fetch instead of waiting for the primary row to age out

#### Scenario: Rate-limited account reaches reset deadline

- **GIVEN** an account is marked `RATE_LIMITED`
- **AND** the account's persisted `reset_at` timestamp has elapsed
- **WHEN** background usage refresh evaluates the account
- **THEN** codex-lb performs an upstream usage fetch instead of waiting for the normal refresh interval

### Requirement: Credit-backed secondary quota remains usable

When account status is derived from persisted usage snapshots, an exhausted secondary-window usage percentage MUST NOT by itself mark an account `quota_exceeded` if the governing usage snapshot reports usable credit-backed capacity. Usable credit-backed capacity is present when `credits_unlimited` is true, `credits_has` is true, or `credits_balance` is positive.

This credit-aware interpretation MUST be shared by proxy account selection and account/dashboard summary status mapping so an account selected as usable by the proxy is not simultaneously displayed as `quota_exceeded` in the operator summary. Exhausted primary-window usage MUST still take precedence as `rate_limited`, and paused or deactivated accounts MUST NOT be reactivated solely because a usage snapshot reports usable credits.

#### Scenario: Secondary quota exhausted with credits remains active

- **GIVEN** an account is persisted as `quota_exceeded`
- **AND** its governing secondary-window usage reports `used_percent >= 100`
- **AND** the same usage snapshot reports usable credit-backed capacity
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the effective status is `active`

#### Scenario: Exhausted primary window keeps rate-limit precedence

- **GIVEN** an account has usable credit-backed capacity in its usage snapshot
- **AND** its primary-window usage reports `used_percent >= 100`
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the effective status is `rate_limited`

#### Scenario: Operator-disabled states are preserved

- **GIVEN** an account is `paused` or `deactivated`
- **AND** its usage snapshot reports usable credit-backed capacity
- **WHEN** proxy selection or account-summary mapping derives the effective status
- **THEN** the account remains `paused` or `deactivated`

### Requirement: Reset-confirmed limit warm-up

The system SHALL support an optional limit warm-up mechanism that is disabled by default. When enabled globally and for an account, background usage refresh MAY send one minimal upstream Responses request after it confirms that a selected quota window has moved from an exhausted sample to a newly available reset window.

#### Scenario: Warm-up is skipped unless reset is confirmed
- **GIVEN** limit warm-up is enabled globally and for an account
- **AND** the account's previous usage sample for a selected window was exhausted
- **WHEN** background usage refresh records a newer sample for that window with `used_percent < 100` and a later `reset_at`
- **THEN** the system sends at most one warm-up request for that account/window/reset tuple

#### Scenario: Warm-up is opt-in and safe by default
- **GIVEN** background usage refresh is preparing to evaluate limit warm-up candidates
- **WHEN** global limit warm-up is disabled
- **OR** the account is not opted in
- **THEN** background usage refresh MUST NOT send warm-up traffic

#### Scenario: Warm-up uses fresh opt-in state after usage refresh
- **GIVEN** an account was loaded before a background usage refresh cycle
- **AND** the account's limit warm-up opt-in changes while the refresh cycle is running
- **WHEN** the scheduler evaluates warm-up candidates after writing usage samples
- **THEN** the scheduler MUST evaluate the latest persisted opt-in value rather than the stale in-session account object

#### Scenario: Warm-up respects unsafe account states
- **WHEN** an account is paused, deactivated, rate-limited, quota-exceeded, or in an auth-refresh failure path
- **THEN** limit warm-up MUST NOT send traffic for that account

#### Scenario: Warm-up attempts are durable and deduplicated
- **WHEN** multiple refresh workers observe the same account/window/reset candidate
- **THEN** the database permits at most one persisted attempt for that tuple
- **AND** later refresh cycles skip that tuple after a prior attempt exists

### Requirement: Credit-backed usage remains selectable after quota windows fill

When deriving effective account status from upstream usage samples, the system MUST treat the latest credit metadata as an override for secondary quota-derived blocking state. If the latest usage sample with credit metadata reports `credits_has = true`, `credits_unlimited = true`, or `credits_balance > 0`, then secondary quota windows at `100%` MUST NOT by themselves make the account `quota_exceeded`. Primary-window exhaustion MUST keep `rate_limited` precedence even when credits are available.

This override MUST NOT reactivate accounts that are explicitly `paused` or
`deactivated`. When multiple usage samples carry credit metadata, the newest
sample by `recorded_at` MUST be used.

#### Scenario: Credit-backed weekly account remains selectable

- **GIVEN** an account is otherwise routable
- **AND** its weekly usage window reports `used_percent = 100`
- **AND** its primary usage window is below `100`
- **AND** the newest usage sample with credit metadata reports a positive credit balance
- **WHEN** the load balancer derives account state
- **THEN** the derived status remains `active`
- **AND** the account remains eligible for selection

#### Scenario: Credit-backed account remains rate-limited when primary window is exhausted

- **GIVEN** an account is otherwise routable
- **AND** its primary usage window reports `used_percent = 100`
- **AND** the newest usage sample with credit metadata reports a positive credit balance
- **WHEN** the load balancer derives account state
- **THEN** the derived status is `rate_limited`
- **AND** the reset guard points at the primary reset time

#### Scenario: Newer zero-credit sample removes the override

- **GIVEN** an older usage sample reports available credits
- **AND** a newer usage sample reports no credits and zero credit balance
- **WHEN** quota status is derived from usage
- **THEN** the newer zero-credit sample is authoritative
- **AND** a full quota window can still derive `rate_limited` or `quota_exceeded`

#### Scenario: Paused account is not reactivated by credits

- **GIVEN** an account is paused
- **AND** its newest usage sample reports available credits
- **WHEN** quota status is derived from usage
- **THEN** the account remains paused

### Requirement: token_expired at the refresh boundary requires re-authentication

When the OAuth refresh endpoint fails with a credential-token error code such as
`token_expired`, `invalid_grant`, `refresh_token_expired`,
`refresh_token_reused`, or `refresh_token_invalidated`, the system MUST treat it
as a permanent refresh-token/session failure. The affected account MUST be
marked `reauth_required` and removed from the routing pool until it is
re-authenticated.

#### Scenario: Refresh-time `token_expired` is classified as permanent

- **WHEN** `classify_refresh_error("token_expired")` is evaluated
- **THEN** it returns `True`

#### Scenario: Refresh-time `invalid_grant` is classified as permanent

- **WHEN** `classify_refresh_error("invalid_grant")` is evaluated
- **THEN** it returns `True`

#### Scenario: Refresh-time `token_expired` requires re-authentication

- **WHEN** `AuthManager.refresh_account` receives a `RefreshError("token_expired", ..., is_permanent=True)` from `refresh_access_token`
- **THEN** the account is transitioned to `REAUTH_REQUIRED`
- **AND** the reason references the re-login requirement so the dashboard can surface it
- **AND** the account is no longer selected by the load balancer until it is re-authenticated

#### Scenario: Usage-refresh-time `token_expired` requires re-authentication

- **WHEN** background usage refresh observes an upstream error whose code is `token_expired`
- **THEN** the account is transitioned to `REAUTH_REQUIRED` immediately, without entering the ambiguous-401 cooldown loop

### Requirement: Operators can probe an account to wake the upstream limiter

The dashboard MUST expose an admin-only endpoint that sends a single minimal `responses.create` directly to upstream pinned to one account, bypassing load-balancer scoring, then immediately refreshes that account's `/wham/usage` snapshot. The endpoint MUST surface the before/after usage and account status so operators can verify whether the upstream limiter re-evaluated.

#### Scenario: Probe wakes the upstream limiter and refreshes usage state
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/probe`
- **AND** the account is `active`, `rate_limited`, or `quota_exceeded`
- **THEN** the service sends one `responses.create` request directly to `{upstream_base_url}/codex/responses` with `max_output_tokens=1`, `stream=true`, `store=false`
- **AND** the service triggers an immediate `UsageUpdater.refresh_accounts` for that account
- **AND** the response body carries `probe_status_code`, `primary_used_percent_before`, `primary_used_percent_after`, `secondary_used_percent_before`, `secondary_used_percent_after`, `account_status_before`, `account_status_after`

#### Scenario: Probe rejects hard-blocked accounts
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/probe`
- **AND** the account `status` is `paused` or `deactivated`
- **THEN** the endpoint responds `409` with code `account_not_probable`
- **AND** no upstream request is sent

#### Scenario: Dashboard exposes Force probe only for probeable statuses

- **WHEN** the dashboard renders account actions for an account
- **AND** the account `status` is `active`, `rate_limited`, or `quota_exceeded`
- **THEN** the dashboard exposes a Force probe action for that account
- **AND** invoking the action refreshes the account list, dashboard overview, projections, and that account's trends
- **BUT WHEN** the account `status` is `paused` or `deactivated`
- **THEN** the Force probe action is disabled or hidden

#### Scenario: Probe returns 404 for unknown account
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/probe`
- **AND** no account with that id exists
- **THEN** the endpoint responds `404` with code `account_not_found`

### Requirement: Free-account quota normalizes to a monthly window

When upstream usage or rate-limit payloads report a single free-account quota window as `primary_window.limit_window_seconds == 2592000` with no `secondary_window`, the system SHALL normalize that payload as a monthly-only quota window rather than as a primary 5h window or a secondary 7d window.

#### Scenario: Monthly free-account payload becomes monthly-only
- **WHEN** usage refresh or rate-limit payload mapping receives `primary_window.limit_window_seconds = 2592000`
- **AND** `secondary_window` is `null`
- **THEN** the system records and exposes the quota as a monthly-only window
- **AND** it does not synthesize a 5h primary or 7d secondary window for that account

### Requirement: Free-account quota capacity applies only to the monthly window

The system SHALL treat the free-account monthly window as the only free-account quota capacity window for overview and summary calculations.

#### Scenario: Free account contributes only monthly quota capacity
- **WHEN** the system computes quota capacity for a free account with a normalized monthly-only window
- **THEN** the free account contributes capacity to the 30d monthly window
- **AND** the free account contributes zero 7d quota capacity

### Requirement: Weekly semantics are not inferred from the primary slot alone

The system SHALL NOT infer weekly secondary semantics solely because a primary-slot payload reports `limit_window_seconds == 604800`.

#### Scenario: Primary-slot weekly duration does not trigger implicit secondary mapping
- **WHEN** a payload includes a primary-slot window whose `limit_window_seconds` is `604800`
- **THEN** downstream interpretation is determined by the normalization rules for that account shape
- **AND** the system does not automatically treat that primary-slot payload as a secondary weekly window only because of that duration

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

### Requirement: Proactive active account credential refresh

Codex-LB SHALL periodically refresh active account credentials in the background when an active account's last refresh is older than a configured maximum age.

#### Scenario: Idle active account becomes stale

- **GIVEN** an account has status `active`
- **AND** its `last_refresh` is older than the configured Auth Guardian max age
- **WHEN** Auth Guardian runs on the elected leader
- **THEN** Codex-LB force-refreshes that account without requiring request traffic to select it first

### Requirement: Auth Guardian bounded and safe execution

Auth Guardian SHALL bound each run by configured batch size and concurrency, add jitter/backoff, and avoid logging token material.

#### Scenario: Refresh fails for one account

- **GIVEN** Auth Guardian attempts to refresh an active account
- **WHEN** refresh fails
- **THEN** Auth Guardian records per-account backoff
- **AND** later accounts in the batch are still eligible to run
- **AND** logs do not contain token material

### Requirement: Multi-replica leader guard

Auth Guardian SHALL use the existing leader-election mechanism so only the elected replica performs proactive refresh work.

#### Scenario: Replica is not leader

- **GIVEN** leader election is enabled
- **AND** the current replica does not acquire leadership
- **WHEN** Auth Guardian wakes
- **THEN** the scheduler skips refresh work for that pass

### Requirement: Usage refresh is account-slot scoped

Usage refresh MUST write usage and change account status only for the credential slot being refreshed. It MUST NOT apply a payload that proves a different workspace identity to the target account.

#### Scenario: Mismatched workspace payload is ignored

- **GIVEN** an account has stored workspace identity
- **WHEN** usage refresh receives a payload for a different workspace
- **THEN** no usage rows are written for the account
- **AND** the account status, plan type, workspace metadata, and seat type are not changed

#### Scenario: Unknown workspace plan mismatch is non-destructive

- **GIVEN** an account has no stored workspace identity
- **WHEN** usage refresh receives a payload whose plan type conflicts with the stored non-unknown plan
- **THEN** no usage rows are written for the account
- **AND** the account status and plan type are not changed

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

### Requirement: User-paused accounts survive auth sync

The system SHALL preserve an operator-paused account state when an auth import, Codex Home sync, or startup discovery sync refreshes the same account's token material.

#### Scenario: Auth sync updates tokens without unpausing

- **GIVEN** an account is `paused` by an operator in the Accounts tab
- **WHEN** the same upstream account is re-imported or refreshed from Codex Home auth material with an otherwise active auth snapshot
- **THEN** the stored account remains `paused`
- **AND** the account's token and refresh metadata MAY be updated
- **AND** only an explicit Reactivate/Resume action SHALL clear the paused state

