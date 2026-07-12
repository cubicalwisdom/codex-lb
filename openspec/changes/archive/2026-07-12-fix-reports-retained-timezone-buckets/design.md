# Design

Reports already converts each requested local date into a `[UTC start, UTC end)` range. The retained aggregate query now joins aggregate minute buckets to those explicit ranges and groups by the range's local-date label. This avoids database-specific timezone conversion and keeps SQLite's 500-term compound-select limit by using the same batching policy as live rows.
