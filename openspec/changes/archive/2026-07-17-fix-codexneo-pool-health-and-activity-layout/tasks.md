## 1. Regression coverage

- [x] 1.1 Add a health regression with one live snapshot and ten canonical pool rows; it must not report mismatch.
- [x] 1.2 Add Activity component assertions for viewport-aware flex layout and internal log scrolling.

## 2. Implementation

- [x] 2.1 Change the health card to report the canonical managed pool instead of comparing independent source inventories.
- [x] 2.2 Replace the fixed Activity log maximum height with a viewport-aware flex layout.

## 3. Verification and portable delivery

- [x] 3.1 Run focused backend and frontend regression tests.
- [x] 3.2 Run full checks, mirror the verified runtime files, restart only Codex LB portable, and verify the live page.
