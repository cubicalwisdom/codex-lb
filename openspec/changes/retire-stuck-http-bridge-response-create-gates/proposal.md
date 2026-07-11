# Retire stuck HTTP bridge response-create gates

## Why

Live Codex traffic produced repeated `response_create_gate_timeout` failures while two HTTP bridge sessions held their one-slot response-create gates for more than five minutes without receiving any upstream event. Each Codex reconnect reused the same stalled bridge and failed again. The overload response is an intentional safety boundary, but repeatedly returning it for a demonstrably stale pre-created request is not a recoverable operator experience.

## What Changes

- Add a configurable stuck-gate retirement threshold with the upstream-compatible default of 300 seconds.
- When a visible HTTP bridge gate waiter times out, retire the session only if a visible request is still pre-`response.created`, has held the gate for the threshold, and has emitted no upstream/downstream event.
- Preserve healthy active streams, recent pre-created requests, synthetic prewarm requests, and non-HTTP work.
- Keep the current waiter failure explicit; the next Codex reconnect creates a fresh bridge instead of looping behind the stale session.
- Make retirement and reconnect cleanup cancellation-safe so tombstoned generations cannot resend and provisional sockets or leases remain tracked until settled.
- Register initial and retry upstream sends as cancellable session activity without holding the lifecycle lock across network I/O.
- Mirror and verify the portable runtime without restarting Codex Desktop.
