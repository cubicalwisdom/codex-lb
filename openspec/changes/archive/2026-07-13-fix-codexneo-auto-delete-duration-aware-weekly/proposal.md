# Use duration-aware weekly usage for CodexNeo automatic deletion

## Why

CodexNeo displays the current 10,080-minute quota response as Weekly even when the usage updater persists it in the legacy `primary` slot. The weekly auto-delete implementation still reads only `secondary` records, so its request returns success while it silently finds zero candidates.

## What Changes

- Normalize the latest primary and secondary records by actual duration before evaluating the weekly auto-delete rule.
- Treat a current weekly-duration primary record as the weekly value and do not treat it as a 5-hour value for quota-status calculation.
- Preserve exact-zero-only, positive/unknown retention, Backup-only cleanup, and retained aggregate-history behavior.

## Non-goals

- Infer missing weekly quota data.
- Change the provider's refresh schedule or account-routing policy.
- Restart Codex LB or Codex Desktop automatically.
