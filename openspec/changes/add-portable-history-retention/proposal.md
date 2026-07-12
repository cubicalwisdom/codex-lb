## Why

The portable SQLite database retains high-frequency usage samples and detailed request logs indefinitely. This has grown the active store to hundreds of megabytes and slows normal startup, while operators only need one day of request-level detail.

## What Changes

- Retain detailed request logs and usage samples for 24 hours.
- Roll expired normal request logs into compact aggregate records before deletion.
- Make Dashboard, Reports, API-key, and account usage aggregates include both live detail and retained aggregate records.
- Keep account state, configuration, credentials, and current usage untouched.

## Impact

- Detailed forensic request rows older than 24 hours are intentionally unavailable.
- Long-term token, cost, request, error, account, and model statistics remain available.
