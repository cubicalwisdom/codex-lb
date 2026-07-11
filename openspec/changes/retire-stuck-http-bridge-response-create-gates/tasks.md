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
