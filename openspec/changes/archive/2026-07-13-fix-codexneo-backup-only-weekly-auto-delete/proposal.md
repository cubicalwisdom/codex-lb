# Delete backup-only accounts when the confirmed weekly quota is exhausted

## Why

The `Auto delete when weekly remaining = 0%` preference is persisted and its write action is invoked, but the cleanup only accepts a matching snapshot from the managed Codex Home accounts directory. A pooled account that exists only in the app-owned Backup store therefore remains visible even after a fresh 10,080-minute weekly usage sample confirms exactly 0% remaining.

## What Changes

- Resolve auto-delete candidates across both managed Codex Home and app-owned Backup snapshots by real auth identity.
- When the enabled rule finds a fresh exact-zero weekly quota-exceeded account, remove its canonical account credential and any matching managed live/Backup records.
- Keep accounts whose weekly value is missing, non-weekly, or above 0% unchanged.
- Prove the existing free/auth-required cleanup already has the same Backup-only coverage and retain that behavior.

## Non-goals

- Delete aggregate usage statistics or audit history.
- Infer a weekly quota from a missing/unknown usage value.
- Restart Codex LB or Codex Desktop automatically.
