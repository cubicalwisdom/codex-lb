## Why

Some legacy account slots can keep stale usage rows after upstream usage refresh
reports a different plan type than the stored account. The current default
safety behavior skips those payloads, which protects workspace identity but can
leave operators unable to see fresh usage for accounts that upstream has
downgraded or upgraded.

## What Changes

- Add an opt-in usage refresh setting that allows plan-only reconciliation for
  account slots without workspace identity.
- Preserve the existing default behavior unless the setting is enabled.
- Continue rejecting payloads that conflict with stored workspace identity, or
  omit workspace identity for a stored workspace account.

## Impact

- Operators can choose to let upstream usage refresh update `plan_type` and
  write fresh usage rows for legacy slots where the only mismatch is plan.
- Reconciled accounts are routed according to their new stored plan type.
- Workspace-scoped slots remain protected from ambiguous payloads.
