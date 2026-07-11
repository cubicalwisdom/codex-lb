## ADDED Requirements

### Requirement: Stuck HTTP bridge response-create gate sessions are retired

When a visible HTTP bridge request times out waiting for a per-session response-create gate, the proxy MUST retire the bridge session only if locked final revalidation finds pending visible HTTP work that is still pre-`response.created`, owns the gate, has never been matched to an upstream event, has no downstream-visible output, and meets or exceeds the configured stuck-gate retirement threshold. Upstream-event evidence MUST remain true across visible-output and authentication replay preparation even when replay resets response identifiers or event counters. Healthy active streams, recent pre-created requests, synthetic prewarm requests, non-HTTP work, and any ever-event-bearing request MUST NOT be retired by this rule.

Retirement MUST be terminal for the affected session generation. The proxy MUST detach only that registered generation, prevent its reconnect/replay/resend or ownership reacquisition, cancel and await its reader, fail and remove pending requests using `stream_incomplete`, terminalize pending event queues, and release response-create, admission, account-response-create, reservation, account, durable, and alias resources. Cleanup MUST occur without awaiting while the pending or registry lock is held. The timed-out waiter MUST retain the stable `response_create_gate_timeout` error so the client can retry safely on a fresh generation.

#### Scenario: Old event-free request blocks a visible waiter

- **WHEN** a visible HTTP bridge waiter receives `response_create_gate_timeout`
- **AND** a pending visible HTTP request on the same session still owns the gate and has never been matched to an upstream event
- **AND** its age meets or exceeds the configured retirement threshold
- **THEN** the proxy retires that bridge session
- **AND** the waiter receives `response_create_gate_timeout`
- **AND** the retired generation cannot reconnect, replay, resend, or reacquire ownership
- **AND** a later client retry can create a fresh bridge generation

#### Scenario: Retirement wins a concurrent reader replay race

- **WHEN** locked final revalidation retires an eligible generation while its upstream reader is blocked or waking from close
- **THEN** only the expected registered generation is detached
- **AND** the reader is cancelled and awaited without reconnecting or resending
- **AND** all pending queues, gates, reservations, leases, durable ownership, and aliases are settled

#### Scenario: Healthy or ineligible pending work is preserved

- **WHEN** a gate waiter times out
- **AND** pending work is recent, has ever received an upstream event, is already downstream-visible, is synthetic prewarm work, or is not HTTP bridge work
- **THEN** the proxy rejects only the waiter
- **AND** it does not retire the existing session under this rule

#### Scenario: Replay does not erase upstream-event evidence

- **WHEN** an upstream error is matched to a request and the request is prepared for visible-output or authentication replay
- **AND** replay resets the response id and response event count
- **THEN** the request remains marked as having received upstream input
- **AND** a later gate timeout does not retire its session under the stuck-gate rule
