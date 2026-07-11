# Tasks

## 1. Evidence and contract

- [x] 1.1 Confirm live repeated gate timeouts, pending ages, bridge reuse, and loaded runtime version.
- [x] 1.2 Compare the local behavior with upstream PR #1156 and define the narrow retirement predicate.
- [x] 1.3 Add the proxy-admission-control delta.

## 2. Test-first implementation

- [x] 2.1 Add RED coverage for a real blocked reader, full pending/gate/lease cleanup, and no reconnect or resend.
- [x] 2.2 Add RED coverage for immutable upstream-event evidence after replay-shaped state resets and retired-generation reconnect rejection.
- [x] 2.3 Add the threshold, monotonic request marker, permanent stuck-generation tombstone, and locked retirement predicate.
- [x] 2.4 Implement expected-generation detach, reader cancellation, full close cleanup, and reconnect double-check cleanup.
- [x] 2.5 Preserve the stable waiter error and existing reader-originated clean-close recovery behavior.

## 3. Verification and closeout

- [x] 3.1 Reconfirm the three intended RED failures before production edits and run them to GREEN.
- [x] 3.2 Run the focused adjacent selection, full HTTP bridge unit file, and bridge timeout/reconnect integration selection.
- [x] 3.3 Run Ruff, scoped ty, strict OpenSpec validation, and `git diff --check`.
- [x] 3.4 Self-review the owned diff, write the Task 2 evidence report, and commit only Task 2 files.

## 4. Cancellation cleanup correction

- [x] 4.1 Add RED coverage for cancellation after provisional socket/lease acquisition during old-socket close, including new and reused lease ownership.
- [x] 4.2 Add RED coverage for cancellation during old-lease release and require the incomplete old lease to remain session-discoverable.
- [x] 4.3 Clean provisional ownership on every pre-install cancellation/exception while preserving the original failure and reader recovery behavior.
- [x] 4.4 Run focused/full bridge verification, selected integration, Ruff, scoped ty, strict OpenSpec, and diff checks.
- [x] 4.5 Append correction evidence to the Task 2 report and commit the correction separately.

## 5. Cancellation-safe terminal lifecycle correction

- [x] 5.1 Add RED coverage for caller cancellation after detach, retirement winning all four replay/resend paths, and request age diverging from gate-hold age.
- [x] 5.2 Add RED coverage for repeated cancellation during provisional close/release, cancellation inside refresh/proxy-error handlers, and terminal failures with a reused lease.
- [x] 5.3 Cancel readers and registered sends before close awaits, use bounded tracked retirement cleanup, and apply the threshold to the gate-acquisition timestamp.
- [x] 5.4 Transfer provisional reconnect ownership to bounded shielded cleanup that retains and retries unresolved resources; install replacements in a no-await lifecycle commit.
- [x] 5.5 Run focused/full bridge verification, selected integration, Ruff, scoped ty, strict OpenSpec, and diff checks; append evidence and commit separately.
- [x] 5.6 Add RED coverage for concurrent reconnect handoff, serialize reconnect provisioning per session, and rerun the verification ladder.

## 6. Blocked initial-send correction

- [x] 6.1 Add RED coverage for a real initial submit blocked in `send_text` while a second visible submit times out waiting for the gate.
- [x] 6.2 Register the initial send while lifecycle is held, await it after releasing lifecycle, and generalize registered activity from retry-only to all active sends.
- [x] 6.3 Cancel reader and active-send snapshots synchronously inside terminal retirement before expected-generation detach or close-child startup.
- [x] 6.4 Run focused/full bridge verification, selected integration, Ruff, scoped ty, strict OpenSpec, and diff checks; independently review and commit separately.

## 7. Terminal external-settlement correction

- [x] 7.1 Add RED coverage for transient account-lease, durable-ownership, and upstream-close failures plus foreground timeout and cancellation.
- [x] 7.2 Move terminal external resources to a separately tracked task with independent retry loops and clear exact session ownership only after success.
- [x] 7.3 Settle pending work and gates before the bounded shielded settlement wait, preserve caller cancellation, and include terminal settlement in background drain.
- [x] 7.4 Run affected/full bridge verification, selected integration, Ruff, scoped ty, strict OpenSpec, and diff checks; append evidence and commit separately.
- [x] 7.5 Complete an independent exact-commit review and address any Critical or Important finding before Task 2 closes.

## 8. Atomic reconnect ownership-handoff correction

- [x] 8.1 Add RED coverage for fail-once displaced-socket settlement and a barrier-controlled retirement-winning reconnect race with exact per-handle accounting.
- [x] 8.2 Remove pre-install old-resource awaits and atomically install the replacement plus transfer displaced socket and non-reused lease ownership under lifecycle.
- [x] 8.3 Settle displaced resources independently in one tracked retry task, preserve reused leases, and include the task in bridge background drain.
- [x] 8.4 Run focused/full verification, static and strict checks, update evidence, and commit the correction separately.
- [x] 8.5 Complete an independent exact-commit review and address any Critical or Important finding before Task 2 closes.
