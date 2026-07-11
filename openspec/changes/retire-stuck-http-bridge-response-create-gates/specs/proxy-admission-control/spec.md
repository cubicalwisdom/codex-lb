## ADDED Requirements

### Requirement: Stuck HTTP bridge response-create gate sessions are retired

When a visible HTTP bridge request times out waiting for a per-session response-create gate, the proxy MUST retire the bridge session only if locked final revalidation finds pending visible HTTP work that is still pre-`response.created`, owns the gate, has held that gate for at least the configured stuck-gate retirement threshold, has never been matched to an upstream event, and has no downstream-visible output. Total request age before gate acquisition MUST NOT determine eligibility. Upstream-event evidence MUST remain true across visible-output and authentication replay preparation even when replay resets response identifiers or event counters. Healthy active streams, recently acquired gates, synthetic prewarm requests, non-HTTP work, and any ever-event-bearing request MUST NOT be retired by this rule.

Retirement MUST be terminal for the affected session generation. The proxy MUST detach only that registered generation, prevent its reconnect/replay/resend or ownership reacquisition, cancel and await its reader and active retry sends before other cleanup awaits, fail and remove pending requests using `stream_incomplete`, terminalize pending event queues, and release response-create, admission, account-response-create, reservation, account, durable, and alias resources. Cleanup MUST occur without awaiting while the pending or registry lock is held and MUST remain tracked if the caller is cancelled. The timed-out waiter MUST retain the stable `response_create_gate_timeout` error so the client can retry safely on a fresh generation.

If reconnect acquires a provisional upstream socket or a new account lease but exits before installing them, including because cancellation interrupts old-socket settlement, old-lease settlement, or a named error handler, the proxy MUST transfer those resources to separately tracked cancellation-safe cleanup before preserving the original cancellation or exception. Repeated caller cancellation MUST NOT interrupt that ownership, and cleanup failures MUST retain and retry each unresolved resource. A reused session lease MUST NOT be released as provisional ownership or on a pre-install terminal failure. The old session lease MUST remain discoverable by session retirement until its release completes. Final tombstone validation and replacement installation MUST contain no intervening await.

Concurrent reconnect attempts for one session MUST serialize their complete resource handoff so each attempt snapshots the currently installed socket, reader, and lease only after the preceding attempt has completed. A later reconnect MUST close and release the preceding installed resources exactly once before installing its own replacement; it MUST NOT overwrite an untracked socket/reader or release the lease belonging to a concurrently installed winner.

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

#### Scenario: Reader cancellation interrupts reconnect before replacement installation

- **WHEN** reconnect has acquired a provisional socket and lease
- **AND** cancellation interrupts old-socket close or old-lease release before the replacement is installed
- **THEN** the provisional socket is closed
- **AND** a newly acquired provisional lease is released exactly once
- **AND** a reused session lease is not released as provisional ownership
- **AND** the old generation retains discoverable ownership of any old lease whose release did not complete
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

#### Scenario: Retirement wins after a retry send starts

- **WHEN** a retry path has registered a send but its network write is still blocked
- **AND** locked final revalidation retires that generation
- **THEN** close cancels and awaits the registered send
- **AND** no replay or resend completes after the terminal decision

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
- **AND** it cancels or closes and releases those resources exactly once before installing its replacement
