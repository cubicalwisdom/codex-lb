# Normalize CodexNeo Weekly Usage Windows

## Why

The upstream quota response currently supplies a single seven-day window for some accounts. The usage updater persists that response in the legacy `primary` slot with `window_minutes=10080`. The main Accounts mapper recognizes the duration and displays it as weekly, but CodexNeo maps storage slots directly to 5h/Weekly columns. As a result, current weekly usage appears under 5h, accounts without an older `secondary` row show no weekly value, and accounts with an older row show stale weekly usage.

## What Changes

- Normalize CodexNeo usage histories by their actual window duration before merging them into display rows.
- Treat a 10,080-minute `primary` record as weekly and prefer it over an older weekly `secondary` record.
- Leave the 5h value empty when no real short-window record is available.
- Preserve existing behavior when genuine 5h and weekly records are both present.

## Non-goals

- Invent or estimate a missing 5h quota.
- Change usage refresh scheduling, account synchronization, routing, or OpenAI quota policy.
- Restart the portable app or Codex Desktop automatically.
