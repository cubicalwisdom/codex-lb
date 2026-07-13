# Design

The deletion path will reuse `app.core.usage.normalize_weekly_only_rows`, the shared duration-aware selection utility used by display logic. It returns the effective short-window and weekly records for each account, preferring a fresher weekly-primary record over a stale legacy secondary record.

The exact-zero gate then evaluates the effective weekly record. For a weekly-only primary record, the effective primary value is absent, so the status evaluation cannot misinterpret a seven-day window as a short quota window.

Example: an account with a 10,080-minute `primary` record at 100% used and no secondary row is eligible when its effective state is quota-exceeded; it is retained if the primary record is not the configured weekly duration or has less than 100% used.
