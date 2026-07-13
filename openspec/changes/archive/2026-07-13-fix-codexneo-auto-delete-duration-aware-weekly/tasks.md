## 1. Regression coverage

- [x] 1.1 Add a failing Backup-only regression for a weekly-duration primary record at exactly 0% remaining.

## 2. Implementation

- [x] 2.1 Normalize latest primary and secondary records by duration before weekly auto-delete eligibility.
- [x] 2.2 Preserve exact-zero and status safety rules after normalization.

## 3. Verification and delivery

- [x] 3.1 Run the focused and complete CodexNeo discovery/sync tests.
- [x] 3.2 Validate the OpenSpec change and stable specs.
- [x] 3.3 Update handover/tracking and mirror the verified module into the portable package without restart.
