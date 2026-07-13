## 1. Regression coverage

- [x] 1.1 Add a failing backend test for an exact-zero weekly quota-exceeded account that exists only in app-owned Backup.
- [x] 1.2 Verify the free/auth-required cleanup removes an eligible Backup-only account.

## 2. Implementation

- [x] 2.1 Resolve quota auto-delete candidates across managed Codex Home and Backup snapshots by auth identity.
- [x] 2.2 Preserve the exact-zero weekly eligibility rule and retained usage history.

## 3. Verification and delivery

- [x] 3.1 Run the focused CodexNeo auto-delete regression tests.
- [x] 3.2 Validate the OpenSpec change and stable specs.
- [x] 3.3 Update implementation tracking and handover.
- [x] 3.4 Mirror the verified backend module into the portable package without restarting it.
