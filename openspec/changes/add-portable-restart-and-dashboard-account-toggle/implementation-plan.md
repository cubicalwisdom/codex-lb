# Portable Restart and Dashboard Account Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an immediate, coordinated portable Codex LB restart, expose Pause/Resume on every eligible Dashboard account presentation, and make the CodexGO auth actions equally compact.

**Architecture:** Electron owns restart coordination through a fixed preload IPC bridge and a separately tested helper that waits for its backend child before scheduling relaunch. Dashboard reuses the existing account mutations and shared action contract in both card and list components. CodexNeo keeps the restart state local to the page and gates it on the Electron bridge.

**Tech Stack:** Electron/CommonJS, React 19, TypeScript, TanStack Query, Vitest/Testing Library, Node test runner, Tailwind CSS, OpenSpec.

---

### Task 1: Electron restart coordinator

**Files:**
- Create: `desktop/electron/restart.cjs`
- Create: `desktop/electron/restart.test.cjs`
- Modify: `desktop/electron/main.cjs`
- Modify: `desktop/electron/preload.cjs`

- [ ] **Step 1: Write failing restart coordinator tests**

Cover an owned child that emits `exit`, no owned child, duplicate concurrent calls, and a child that does not exit within the timeout. Assert that relaunch is scheduled only after the owned child exits and that the old app exits only after the IPC result can be returned.

```js
const restart = createPortableRestartCoordinator({
  app: fakeApp,
  getBackendProcess: () => child,
  markQuitting: () => calls.push("mark-quitting"),
  appendLog: (_root, message) => calls.push(`log:${message}`),
  root: "H:\\Portable",
  timeoutMs: 25,
  scheduleExit: (callback) => scheduled.push(callback),
});

const result = await restart();
assert.deepEqual(result, { success: true, message: "Codex LB is restarting" });
assert.deepEqual(calls.slice(0, 3), ["mark-quitting", "kill-backend", "relaunch"]);
scheduled[0]();
assert.equal(fakeApp.exit.mock.calls[0][0], 0);
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `node --test desktop/electron/restart.test.cjs`

Expected: FAIL because `restart.cjs` and `createPortableRestartCoordinator` do not exist.

- [ ] **Step 3: Implement the minimal coordinator**

Export a factory with this public contract:

```js
function createPortableRestartCoordinator({
  app,
  getBackendProcess,
  markQuitting,
  appendLog,
  root,
  timeoutMs = 5000,
  scheduleExit = setImmediate,
}) {
  let restartPromise = null;
  return async function restartPortableApp() {
    if (restartPromise) return restartPromise;
    restartPromise = restartOwnedBackendAndApp({
      app,
      backendProcess: getBackendProcess(),
      markQuitting,
      appendLog,
      root,
      timeoutMs,
      scheduleExit,
    });
    const result = await restartPromise;
    if (!result.success) restartPromise = null;
    return result;
  };
}
```

The helper must reject an absent/already-exited child, call `child.kill()` only for the captured owned child, await its `exit` event with a bounded timeout, call `app.relaunch()`, and schedule `app.exit(0)` for the next turn. Timeout returns `{ success: false, message: "Codex LB backend did not stop in time" }` and does not relaunch.

- [ ] **Step 4: Connect the main process and preload bridge**

In `main.cjs`, create one coordinator after module state initialization and register:

```js
ipcMain.handle("codex-ib:restart", () => restartPortableApp());
```

Use `markQuitting: () => { isQuitting = true; }` and the existing `backendProcess` getter. In `preload.cjs`, expose:

```js
restartApp: () => ipcRenderer.invoke("codex-ib:restart"),
```

- [ ] **Step 5: Run Electron tests GREEN**

Run: `node --test desktop/electron/restart.test.cjs desktop/electron/single-instance.test.cjs desktop/electron/startup.test.cjs`

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 1**

```powershell
git add desktop/electron/restart.cjs desktop/electron/restart.test.cjs desktop/electron/main.cjs desktop/electron/preload.cjs
git commit -m "feat(portable): coordinate Codex LB restart"
```

### Task 2: CodexNeo restart control and compact auth actions

**Files:**
- Modify: `frontend/src/vite-env.d.ts`
- Modify: `frontend/src/features/codexneo/components/codexneo-page.tsx`
- Modify: `frontend/src/features/codexneo/components/codexneo-page.test.tsx`

- [ ] **Step 1: Write failing CodexNeo tests**

Add a bridge stub returning `{ success: false, message: "Codex LB backend is not owned by this app" }`. Assert Restart Codex LB appears in the header, invokes `restartApp` immediately without `window.confirm`, reports failure without leaving a permanent busy state, and is disabled when `restartApp` is absent. Assert Use auth and Refresh auth share `h-10 min-w-28` and neither uses a growing `1fr` grid column.

```tsx
expect(screen.getByRole("button", { name: "Restart Codex LB" })).toBeEnabled();
await user.click(screen.getByRole("button", { name: "Restart Codex LB" }));
expect(restartApp).toHaveBeenCalledTimes(1);
expect(confirmSpy).not.toHaveBeenCalled();
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `node node_modules/vitest/vitest.mjs run src/features/codexneo/components/codexneo-page.test.tsx`

Expected: FAIL because the bridge type/control and equal sizing do not exist.

- [ ] **Step 3: Add the typed Electron bridge and restart handler**

Extend `Window.codexIbElectron`:

```ts
restartApp?: () => Promise<{ success: boolean; message: string }>;
```

Change `PageHeader` to accept `restartAvailable`, `restartPending`, and `onRestart`. Render the action at the right edge with `RotateCcw`, `disabled={!restartAvailable || restartPending}`, and title text explaining that normal browsers cannot restart the portable app. The handler calls the bridge directly, uses a local pending flag, and shows `toast.error(result.message)` only when the bridge returns failure or throws.

- [ ] **Step 4: Equalize CodexGO auth action sizing**

Replace the expanding action grid columns with compact `auto` columns and give both buttons:

```tsx
className="h-10 min-w-28 px-4"
```

They may wrap below the form at narrower widths but must remain equal.

- [ ] **Step 5: Run CodexNeo tests GREEN**

Run: `node node_modules/vitest/vitest.mjs run src/features/codexneo/components/codexneo-page.test.tsx`

Expected: all tests PASS.

- [ ] **Step 6: Commit Task 2**

```powershell
git add frontend/src/vite-env.d.ts frontend/src/features/codexneo/components/codexneo-page.tsx frontend/src/features/codexneo/components/codexneo-page.test.tsx
git commit -m "feat(codexneo): add portable restart control"
```

### Task 3: Dashboard Pause and Resume in both views

**Files:**
- Modify: `frontend/src/features/dashboard/components/account-card.tsx`
- Modify: `frontend/src/features/dashboard/components/account-card.test.tsx`
- Modify: `frontend/src/features/dashboard/components/account-list.tsx`
- Modify: `frontend/src/features/dashboard/components/account-list.test.tsx`
- Modify: `frontend/src/features/dashboard/components/dashboard-page.tsx`
- Modify: `frontend/src/features/dashboard/components/dashboard-page.test.tsx`

- [ ] **Step 1: Write failing component tests**

Extend `AccountAction` with `"pause"`. In card and list tests, assert active, rate-limited, and quota-exceeded rows dispatch `pause`; paused rows dispatch `resume`; and re-auth-required/deactivated rows expose neither transition.

```tsx
await user.click(screen.getByRole("button", { name: "Pause Active Account" }));
expect(onAction).toHaveBeenCalledWith(activeAccount, "pause");
```

- [ ] **Step 2: Write the failing Dashboard wiring test**

Mock both mutations and capture `onAction` from mocked cards/list components. Invoke `onAction(account, "pause")` and `onAction(account, "resume")`, then assert the matching mutation receives `account.accountId` and the other mutation does not.

- [ ] **Step 3: Run Dashboard tests and verify RED**

Run: `node node_modules/vitest/vitest.mjs run src/features/dashboard/components/account-card.test.tsx src/features/dashboard/components/account-list.test.tsx src/features/dashboard/components/dashboard-page.test.tsx`

Expected: FAIL because Pause is absent and Dashboard destructures only Resume.

- [ ] **Step 4: Implement card and list Pause controls**

Import the `Pause` icon. For normalized statuses `active`, `limited`, and `exceeded`, render Pause using the same dimensions as Resume and dispatch `"pause"`. Keep Resume for `paused`. Keep recovery actions for `reauth` and `deactivated` without adding invalid transitions.

- [ ] **Step 5: Wire the pause mutation in Dashboard**

Destructure `pauseMutation` and add:

```ts
case "pause":
  if (canWrite) void pauseMutation.mutateAsync(account.accountId);
  break;
```

Include `pauseMutation` in callback dependencies. Existing account mutations already invalidate account and Dashboard queries after success.

- [ ] **Step 6: Run Dashboard tests GREEN**

Run the same three-file Vitest command.

Expected: all tests PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add frontend/src/features/dashboard/components/account-card.tsx frontend/src/features/dashboard/components/account-card.test.tsx frontend/src/features/dashboard/components/account-list.tsx frontend/src/features/dashboard/components/account-list.test.tsx frontend/src/features/dashboard/components/dashboard-page.tsx frontend/src/features/dashboard/components/dashboard-page.test.tsx
git commit -m "feat(dashboard): toggle account pause state"
```

### Task 4: Verification, package, and live restart

**Files:**
- Modify: `openspec/changes/add-portable-restart-and-dashboard-account-toggle/tasks.md`
- Modify: `CODEXNEO_IMPLEMENTATION_LIST.md`
- Modify: `HANDOVER_CODEXNEO_INTEGRATION.md`

- [ ] **Step 1: Run full focused verification**

```powershell
node --test desktop/electron/restart.test.cjs desktop/electron/single-instance.test.cjs desktop/electron/startup.test.cjs
cd frontend
node node_modules/vitest/vitest.mjs run src/features/codexneo src/features/dashboard/components/account-card.test.tsx src/features/dashboard/components/account-list.test.tsx src/features/dashboard/components/dashboard-page.test.tsx
npm run lint
npm run typecheck
npm run build
cd ..
.\.venv\Scripts\python.exe -m pytest tests/integration/test_accounts_api.py tests/unit/test_accounts_service_transitions.py -q
.\.venv\Scripts\python.exe -m ruff check app tests
openspec validate add-portable-restart-and-dashboard-account-toggle --strict
openspec validate --specs
git diff --check
```

Expected: all commands exit 0; only documented existing build-size or SQLite reflection warnings may remain.

- [ ] **Step 2: Rebuild the portable Electron package without deleting portable data**

Run the repository packaging script against `dist/CodexIB-Electron-Portable`, preserving `portable-data` and logs according to its existing safeguards. Verify `resources/app.asar` contains the updated `main.cjs`, `preload.cjs`, and `restart.cjs`; mirror the verified Python/static files as required by the package convention and compare SHA-256 hashes.

- [ ] **Step 3: Exercise the approved live restart action**

Record the old Electron and backend PIDs. Click Restart Codex LB once in the Electron-hosted CodexNeo header. Verify both old PIDs exit, exactly one replacement Electron shell and one embedded backend listener appear, `/health` and `/health/ready` return `ok`, and the replacement window renders CodexNeo without console errors. Do not restart Codex Desktop.

- [ ] **Step 4: Rendered interaction QA**

Using the Browser plugin when it can attach to the Electron-hosted page, otherwise the repo's Playwright workflow, verify:

- Restart Codex LB is in the CodexNeo header.
- Use auth and Refresh auth have equal bounding boxes.
- Active Dashboard cards/list rows expose Pause.
- Pausing changes the selected test account to Resume; resuming changes it back to Pause.
- No relevant console errors occur.

Restore any test account to its original state.

- [ ] **Step 5: Update evidence and commit**

Check every task, append exact commands/PIDs/hash counts to the handover and implementation list, then commit:

```powershell
git add openspec/changes/add-portable-restart-and-dashboard-account-toggle/tasks.md CODEXNEO_IMPLEMENTATION_LIST.md HANDOVER_CODEXNEO_INTEGRATION.md
git commit -m "docs(portable): verify restart and account toggles"
```
