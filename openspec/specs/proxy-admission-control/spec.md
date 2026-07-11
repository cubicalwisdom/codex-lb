# proxy-admission-control Specification

## Purpose
Define how the proxy protects itself under load while preserving short request paths and surfacing local overload clearly.
## Requirements
### Requirement: Downstream proxy admission is split by traffic class

The system MUST enforce independent downstream admission limits for proxy HTTP requests, proxy websocket sessions, compact HTTP requests, and dashboard traffic. Exhausting one proxy lane MUST NOT consume capacity from the others.

#### Scenario: Websocket session load does not starve HTTP responses
- **WHEN** the proxy websocket admission lane is full
- **THEN** new websocket sessions are rejected locally
- **AND** eligible proxy HTTP requests may still proceed if their own lane has capacity

#### Scenario: Compact lane survives general proxy load
- **WHEN** the general proxy HTTP lane is saturated
- **AND** the compact lane still has capacity
- **THEN** `/backend-api/codex/responses/compact` and `/v1/responses/compact` requests continue to be admitted

### Requirement: Local overload responses are explicit

When the proxy rejects a request locally because an admission lane or expensive-work stage is full, it MUST return a local-overload response with a `Retry-After` header. HTTP requests MUST use an OpenAI-style error envelope and websocket handshake denials MUST use an HTTP denial response instead of a pre-accept close frame.

#### Scenario: HTTP admission rejection returns explicit overload envelope
- **WHEN** a proxy HTTP request is rejected locally for overload
- **THEN** the response status is `429`
- **AND** the response includes `Retry-After`
- **AND** the error payload identifies the failure as local proxy overload instead of upstream unavailability

#### Scenario: Websocket handshake rejection returns explicit overload status
- **WHEN** a websocket handshake is rejected locally for overload
- **THEN** the client receives an HTTP denial response with the real overload status
- **AND** the server access log reflects that overload status instead of `403 Forbidden`

### Requirement: Expensive upstream work is admission controlled

The proxy MUST enforce separate in-process admission limits for token refresh, upstream websocket connect, and first-turn response creation.

#### Scenario: Token refresh admission rejects excess work
- **WHEN** concurrent forced token refresh work reaches the configured refresh limit
- **THEN** additional refresh attempts are rejected locally with an explicit overload response

#### Scenario: Response creation admission releases after first upstream acceptance
- **WHEN** the proxy is waiting for an upstream response to be created
- **THEN** that request holds a response-create admission slot
- **AND** the slot is released when the request receives `response.created` or fails before creation completes

### Requirement: Account-local Responses work is capped before upstream creation

For `/v1/responses`, `/backend-api/codex/responses`, and compact Responses traffic, the proxy MUST enforce account-local response-create and streaming concurrency limits in addition to process-wide admission limits. The default account response-create cap MUST be 4 and the default account stream cap MUST be 8 unless operators configure a different value. When an account is at either cap, new soft-affinity work MUST prefer another eligible account before returning local overload. Hard-continuity work MAY fail closed when the required owner account is saturated.

#### Scenario: Soft work avoids saturated account

- **GIVEN** account A is at its account response-create cap
- **AND** account B is eligible and below cap
- **WHEN** a soft-affinity `/v1/responses` request is routed
- **THEN** the proxy selects account B instead of queueing on account A

#### Scenario: Hard continuity owner saturation fails closed

- **GIVEN** a follow-up request requires a specific previous-response owner account
- **AND** that account is at its account stream or response-create cap
- **WHEN** no safe continuity-preserving alternative exists
- **THEN** the proxy returns a bounded local overload/continuity failure
- **AND** the failure reason is stable and low-cardinality

### Requirement: Local overload reasons are stable and distinguishable

Local Responses overload failures MUST expose stable low-cardinality reason fields in logs and metrics so operators can distinguish `bridge_queue_full`, `response_create_gate_timeout`, `hard_affinity_saturated`, `previous_response_owner_unavailable`, `global_admission_timeout`, `capacity_exhausted_active_sessions`, `account_response_create_cap`, and `account_stream_cap`. These local reasons MUST NOT be reported as upstream rate limits.

#### Scenario: Bridge queue saturation is not ambiguous

- **WHEN** a local HTTP bridge queue rejects a request
- **THEN** logs and metrics use the stable reason `bridge_queue_full`
- **AND** they do not use the ambiguous alias `queue_full`

#### Scenario: Account cap rejection is local overload

- **WHEN** every eligible account is unavailable because of account-local caps
- **THEN** the HTTP response is a local overload response with `Retry-After`
- **AND** logs and metrics identify `account_response_create_cap` or `account_stream_cap`
- **AND** the selection error message identifies the exhausted account-local cap instead of reporting generic upstream account unavailability

#### Scenario: Local rate-limit selection errors are not retried as upstream recovery

- **WHEN** account selection fails with the local message `Rate limit exceeded. Try again in Ns`
- **THEN** the proxy does not enter the upstream account-capacity recovery sleep loop for that local selection error

### Requirement: HTTP bridge startup admission waits are bounded

The proxy MUST apply the configured proxy admission wait timeout to HTTP bridge startup waits for per-session response-create gate acquisition, bridge capacity waiters, and in-flight session creation waiters. When the timeout expires, the proxy MUST reject the request locally with HTTP 429 and an OpenAI-style `proxy_overloaded` error envelope. Timing out while observing another request's pending in-flight session creation MUST evict that in-flight marker when it is still pending so later requests can attempt a fresh bridge session instead of waiting on the same stalled future.

If a request owns in-flight bridge session creation and is cancelled or fails after publishing the in-flight marker but before registering the created session, the proxy MUST remove or settle that in-flight marker. If a session owner later finishes creation after its in-flight marker was evicted, the owner MUST NOT return an unregistered bridge session to the caller.

#### Scenario: Per-session response-create gate does not open

- **WHEN** a bridged Responses request waits for a session response-create gate
- **AND** the gate does not open before the configured proxy admission wait timeout
- **THEN** the request is rejected locally with HTTP 429
- **AND** the error payload uses `error.code = "proxy_overloaded"`
- **AND** no response-create gate lease is recorded on that request state

#### Scenario: In-flight bridge session creation does not finish

- **WHEN** a bridged Responses request waits on another request's in-flight session creation
- **AND** the in-flight creation does not finish before the configured proxy admission wait timeout
- **THEN** the waiter is rejected locally with HTTP 429 and `error.code = "proxy_overloaded"`
- **AND** the stalled in-flight marker is evicted if it is still pending

#### Scenario: Bridge capacity waiter does not make progress

- **WHEN** the HTTP bridge is at capacity and a request waits for in-flight bridge work to free capacity
- **AND** no capacity becomes available before the configured proxy admission wait timeout
- **THEN** the waiter is rejected locally with HTTP 429 and `error.code = "proxy_overloaded"`

#### Scenario: In-flight owner is cancelled during stale session close

- **WHEN** a bridge session creation owner has published an in-flight marker
- **AND** it is cancelled while closing a stale local bridge session before creating the replacement session
- **THEN** the in-flight marker is removed or settled
- **AND** later requests do not remain blocked on that cancelled owner's future

### Requirement: Stuck HTTP bridge response-create gate sessions are retired

When a visible HTTP bridge request times out waiting for a per-session response-create gate, the proxy MUST retire the bridge session only if locked final revalidation finds pending visible HTTP work that is still pre-`response.created`, owns the gate, has held that gate for at least the configured stuck-gate retirement threshold, has never been matched to an upstream event, and has no downstream-visible output. Total request age before gate acquisition MUST NOT determine eligibility. Upstream-event evidence MUST remain true across visible-output and authentication replay preparation even when replay resets response identifiers or event counters. Healthy active streams, recently acquired gates, synthetic prewarm requests, non-HTTP work, and any ever-event-bearing request MUST NOT be retired by this rule.

Retirement MUST be terminal for the affected session generation. The proxy MUST detach only that registered generation, prevent its reconnect/replay/resend or ownership reacquisition, synchronously cancel its reader and all registered active sends before releasing lifecycle ownership, then await them before other cleanup awaits. It MUST fail and remove pending requests using `stream_incomplete`, terminalize pending event queues, and release response-create, admission, account-response-create, reservation, account, durable, and alias resources. Cleanup MUST occur without awaiting while the pending or registry lock is held and MUST remain tracked if the caller is cancelled. The timed-out waiter MUST retain the stable `response_create_gate_timeout` error so the client can retry safely on a fresh generation.

Terminal account-lease release, durable-ownership release, and upstream-socket close MUST remain separately tracked until each operation succeeds. Failure or blocking of any one external settlement MUST NOT delay pending-request, queue, response-create-gate, admission, reservation, or alias cleanup, and MUST NOT prevent the other terminal resources from settling independently. Unresolved session references MUST be retained and retried, direct close MUST wait only for a bounded shielded interval, caller cancellation MUST be preserved, and bridge background drain MUST include the terminal-settlement task.

Initial submission and retry sends MUST register their actual upstream-send tasks during lifecycle validation and MUST await network I/O only after releasing the lifecycle lock. A blocked initial send MUST NOT prevent a gate-timeout waiter from entering retirement, receiving the stable timeout response, or fully settling the terminal generation.

If reconnect acquires a provisional upstream socket or a new account lease but exits before installing them, including because cancellation interrupts a named error handler or the final lifecycle wait, the proxy MUST transfer those resources to separately tracked cancellation-safe cleanup before preserving the original cancellation or exception. Repeated caller cancellation MUST NOT interrupt that ownership, and cleanup failures MUST retain and retry each unresolved resource. A reused session lease MUST NOT be released as provisional ownership or on a pre-install terminal failure. Old installed handles MUST remain session-discoverable until either retirement takes terminal ownership or a successful replacement commit transfers them. Final tombstone validation and replacement installation MUST contain no intervening await.

The final reconnect lifecycle commit MUST assign each old and provisional handle to exactly one cleanup owner. If retirement wins lifecycle, reconnect MUST leave the old session handles for terminal settlement and MUST clean only its losing provisional resources. If reconnect wins, it MUST atomically capture the exact displaced installed socket and lease, install the provisional replacement, and synchronously transfer the displaced handles to one tracked retry task before releasing lifecycle. Displaced socket close and lease release MUST retry independently, MUST NOT mutate the newly installed session fields, and MUST NOT release an identical lease reused by the replacement.

Concurrent reconnect attempts for one session MUST serialize their complete resource handoff so each attempt captures the currently installed socket, reader, and lease only in its final lifecycle commit after the preceding attempt has installed. A later reconnect MUST transfer the preceding installed resources to tracked settlement exactly once while installing its own replacement; it MUST NOT overwrite an untracked socket/reader or release the lease belonging to a concurrently installed winner.

#### Scenario: Old event-free request blocks a visible waiter

- **WHEN** a visible HTTP bridge waiter receives `response_create_gate_timeout`
- **AND** a pending visible HTTP request on the same session still owns the gate and has never been matched to an upstream event
- **AND** its gate-hold age meets or exceeds the configured retirement threshold
- **THEN** the proxy retires that bridge session
- **AND** the waiter receives `response_create_gate_timeout`
- **AND** the retired generation cannot reconnect, replay, resend, or reacquire ownership
- **AND** a later client retry can create a fresh bridge generation

#### Scenario: Retirement wins a concurrent reader replay race

- **WHEN** locked final revalidation retires an eligible generation while its upstream reader is blocked or waking from close
- **THEN** only the expected registered generation is detached
- **AND** the reader is cancelled and awaited without reconnecting or resending
- **AND** all pending queues, gates, reservations, leases, durable ownership, and aliases are settled

#### Scenario: Reconnect exits before replacement installation

- **WHEN** reconnect has acquired a provisional socket and lease
- **AND** cancellation or retirement prevents the final replacement commit
- **THEN** the provisional socket is closed
- **AND** a newly acquired provisional lease is released exactly once
- **AND** a reused session lease is not released as provisional ownership
- **AND** the old generation retains ownership of its installed socket and lease
- **AND** the original cancellation is propagated

#### Scenario: Healthy or ineligible pending work is preserved

- **WHEN** a gate waiter times out
- **AND** pending work acquired its gate recently, has ever received an upstream event, is already downstream-visible, is synthetic prewarm work, or is not HTTP bridge work
- **THEN** the proxy rejects only the waiter
- **AND** it does not retire the existing session under this rule

#### Scenario: Replay does not erase upstream-event evidence

- **WHEN** an upstream error is matched to a request and the request is prepared for visible-output or authentication replay
- **AND** replay resets the response id and response event count
- **THEN** the request remains marked as having received upstream input
- **AND** a later gate timeout does not retire its session under the stuck-gate rule

#### Scenario: Retirement wins after an active send starts

- **WHEN** initial submission or a retry path has registered a send but its network write is still blocked
- **AND** locked final revalidation retires that generation
- **THEN** close cancels and awaits the registered send
- **AND** no replay or resend completes after the terminal decision

#### Scenario: Blocked initial send does not starve gate-timeout retirement

- **WHEN** an initial visible HTTP submit owns the response-create gate and its registered upstream send is blocked before any event
- **AND** a second visible submit times out waiting for that gate after the threshold
- **THEN** retirement acquires lifecycle promptly and tombstones the generation
- **AND** it cancels the initial send before releasing lifecycle ownership
- **AND** the waiter receives `response_create_gate_timeout`
- **AND** the old submit and all generation resources are settled

#### Scenario: Terminal quiescing precedes close-child startup

- **WHEN** locked retirement marks a generation terminal while its reader or active sends are runnable
- **AND** bounded close startup is delayed
- **THEN** the reader and active sends already have cancellation requested before detach completes
- **AND** they cannot produce post-tombstone side effects during the startup delay

#### Scenario: Transient terminal resource failures retain ownership

- **WHEN** terminal account-lease release, durable-ownership release, or upstream-socket close fails transiently
- **THEN** each failed operation is retried independently
- **AND** its matching session reference is retained until the external operation succeeds
- **AND** successfully settled resources are cleared or marked complete exactly once

#### Scenario: Blocked terminal settlement does not delay local cleanup

- **WHEN** one terminal external release remains blocked
- **THEN** pending requests, event queues, response-create gates, admission ownership, reservations, and aliases settle promptly
- **AND** the other terminal external resources can settle independently

#### Scenario: Foreground interruption preserves terminal settlement ownership

- **WHEN** direct close reaches its bounded wait or its caller is cancelled while terminal resources remain unresolved
- **THEN** direct close returns or propagates the original cancellation without abandoning the settlement child
- **AND** unresolved resource references and the settlement task remain tracked for retry and background drain

#### Scenario: Repeated cancellation cannot abandon provisional ownership

- **WHEN** reconnect owns a provisional socket or new lease
- **AND** cancellation occurs in an error handler or during pre-install settlement
- **AND** another cancellation occurs while provisional cleanup is blocked
- **THEN** cleanup remains independently tracked and shielded
- **AND** each unresolved resource remains owned and is retried until settled
- **AND** the original cancellation is preserved

#### Scenario: Old request with a recently acquired gate is preserved

- **WHEN** a request is older than the configured threshold because it waited before gate acquisition
- **AND** its response-create gate was acquired less than the threshold ago
- **THEN** a later gate timeout does not retire its session under the stuck-gate rule

#### Scenario: Concurrent reconnects serialize resource handoff

- **WHEN** two callers request reconnect for the same bridge session concurrently
- **THEN** only one attempt provisions and installs at a time
- **AND** the later attempt snapshots the first attempt's installed socket, reader, and lease
- **AND** its final lifecycle commit installs the replacement and transfers those displaced resources to tracked settlement exactly once

#### Scenario: Reconnect wins lifecycle against retirement

- **WHEN** reconnect reaches the final lifecycle commit before retirement
- **THEN** it installs the provisional socket and lease
- **AND** one tracked child owns the exact displaced socket and any non-reused displaced lease
- **AND** transient close or release failures retry without clearing or closing the replacement fields

#### Scenario: Retirement wins lifecycle against reconnect

- **WHEN** retirement tombstones the generation before reconnect's final lifecycle commit
- **THEN** terminal settlement alone owns the old installed socket and lease
- **AND** reconnect rejects the installation and provisional cleanup alone owns the losing new socket and lease
- **AND** every old and provisional handle is closed or released exactly once

