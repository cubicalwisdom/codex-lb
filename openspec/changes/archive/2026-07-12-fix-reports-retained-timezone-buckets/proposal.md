# Fix retained report timezone buckets

## Why

After raw request history is compacted into UTC minute aggregates, Reports grouped those aggregates by UTC calendar date even when the requested report timezone was non-UTC. Local dates near midnight could therefore raise a `KeyError` and return HTTP 500.

## What Changes

- Group retained request aggregates through the same timezone-derived UTC day ranges used for live request logs.
- Preserve existing report filters, totals, and active-account merging.
- Add a regression for Asia/Calcutta local midnight crossing the previous UTC date.
