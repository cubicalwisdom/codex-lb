# Design

## Root cause

The bridge reader permits up to `stream_idle_timeout_seconds` (600 seconds by default) without an upstream message. A second request waits only `proxy_admission_wait_timeout_seconds` (10 seconds by default) for the same session's response-create semaphore. Before this change, that timeout logged the pending request age and rejected the waiter but left the stale session registered. Live evidence showed pending ages of 311–363 seconds and repeated reuse of the same hashed bridge keys.

## Recovery rule

Port the guarded retirement threshold from upstream PR #1156 without importing its unrelated TTFT persistence/dashboard work. Each request state records a monotonic `upstream_event_seen` marker as soon as HTTP bridge upstream input is matched to it, before retry, typeless-error, or terminal-event branching. Replay preparation may reset `response_id` and `response_event_count`, but it never resets this marker.

At gate timeout, pending ids and ages may be snapshotted for diagnostics, but that snapshot never authorizes retirement. The final decision is made while holding the session lifecycle lock and revalidated under the pending lock. A state is eligible only when it:

- is a normal visible HTTP request (`skip_request_log` is false);
- still owns the response-create gate and awaits `response.created`;
- has never been matched to an upstream event and has no downstream-visible output;
- is at least the configured threshold old.

The eligible generation is permanently tombstoned and marked closed. While still serialized by the lifecycle lock, registry removal uses expected-generation detach so a replacement generation cannot be removed accidentally. All locks are then released before the normal full close path cancels and awaits the reader, closes the upstream, fails and removes pending requests with `stream_incomplete`, terminalizes their queues, and releases response-create, admission, account-response-create, reservation, account, durable, and alias ownership.

Reconnect rejects a tombstoned generation before account selection or socket open and rechecks the tombstone before installing a provisional replacement. A provisional socket and newly acquired account lease are closed/released on the second check. The timed-out waiter still receives the existing stable `response_create_gate_timeout` error; a later client retry may create a new generation, but the retired generation can never reconnect, replay, resend, or reacquire ownership.

## Safety boundary

The default 300-second threshold matches upstream. A healthy long stream has already received `response.created`, released the gate, produced downstream-visible output, or set the immutable upstream-event marker, so it cannot satisfy the predicate. Synthetic prewarm requests and non-HTTP work remain excluded. Existing reader-originated cleanup continues to run inside its caller-held lifecycle lock without re-entering that lock; only stuck-gate retirement applies the permanent tombstone. No prompt, raw affinity key, or account secret is logged.
