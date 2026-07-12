## Scope and decisions

The feature adds three narrowly related operator controls without changing account-state rules or Codex Desktop behavior. Restart Codex LB is immediate and intentionally has no confirmation dialog. Pause and Resume remain per-account actions. Re-auth-required and deactivated accounts are not eligible because the existing backend rejects those transitions.

## Portable restart architecture

The renderer calls a new method exposed by the context-isolated Electron preload bridge. The main Electron process owns the restart sequence and accepts only the fixed internal IPC channel; the renderer cannot supply an executable path or command.

On request, the main process prevents a second restart request, marks the app as quitting, logs the operation, stops the backend child that this Electron instance owns, and waits for its exit with a short bounded timeout. After the child is gone, Electron schedules `app.relaunch()` and exits the old process. The existing single-instance lock prevents overlapping windows, and the replacement process follows the normal boot and health-check path.

If the Electron instance does not own a backend child because it attached to an already healthy service, the restart request must fail visibly instead of terminating an unknown process. If graceful child exit exceeds the timeout, the shell may force termination only for that already-owned child and must still await its exit before relaunching. Browser-only CodexNeo sessions render the control disabled with an Electron-required explanation.

## Dashboard account toggle

Dashboard reuses `useAccountMutations` and the existing `/api/accounts/{id}/pause` and `/resume` endpoints. Paused accounts render Resume. Active, rate-limited, and quota-exceeded accounts render Pause. Re-auth-required and deactivated accounts render no transition action because those states require recovery in Accounts.

On success, the existing mutation invalidation refreshes Dashboard and account queries so the control and status badge switch without navigation. While a transition is pending, the affected action is disabled to prevent duplicate writes. Backend conflict and authorization messages continue through the existing toast/error path.

Both Dashboard card and compact-list presentations use the same action contract so switching view mode does not remove the toggle.

## CodexGO action sizing

Use auth and Refresh auth share the same height, compact minimum width, and non-growing grid columns. On narrower layouts they may wrap, but neither action consumes the remaining row width by itself.

## Verification

- Node tests cover restart sequencing, duplicate-request protection, owned-child exit, timeout handling, relaunch, and browser bridge exposure.
- React tests begin RED for the missing Restart Codex LB control, missing Dashboard Pause actions, and unequal CodexGO action sizing.
- Dashboard tests verify Pause and Resume dispatch from both card and list views and verify ineligible states do not offer invalid transitions.
- CodexNeo tests verify the restart control is immediate, Electron-gated, and placed in the header; Use auth and Refresh auth have equivalent sizing.
- Backend transition tests remain the authority for valid and invalid account states.
- Final verification includes backend/frontend tests, Electron tests, lint, typecheck, production build, strict OpenSpec validation, portable package/runtime mirroring, hash checks, and rendered Electron-page QA. The app is restarted only when explicitly exercising the newly approved Restart Codex LB control.
