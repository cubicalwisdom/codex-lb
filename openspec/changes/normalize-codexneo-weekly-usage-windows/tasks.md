## 1. Regression coverage

- [x] 1.1 Add a failing test for an account whose only latest usage row is weekly-duration data stored in `primary`.
- [x] 1.2 Add a failing test proving a newer weekly-duration `primary` row replaces an older weekly `secondary` row.

## 2. Implementation

- [x] 2.1 Normalize CodexNeo history windows before display freshness and merge decisions.
- [x] 2.2 Keep true 5h plus weekly behavior unchanged.

## 3. Verification and delivery

- [x] 3.1 Run focused and full CodexNeo backend tests plus scoped static checks.
- [x] 3.2 Validate the OpenSpec change and stable specs.
- [x] 3.3 Update implementation tracking and handover.
- [x] 3.4 Mirror the verified backend module into the portable package without restarting it.
