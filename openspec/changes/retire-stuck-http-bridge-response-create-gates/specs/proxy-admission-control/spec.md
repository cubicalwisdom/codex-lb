## ADDED Requirements

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
