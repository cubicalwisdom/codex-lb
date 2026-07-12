## Why

The portable Electron app has no direct control for restarting Codex LB itself. Operators must close and reopen it manually, which is slower and can leave uncertainty about whether the backend process stopped. The Dashboard also exposes Resume only for paused accounts, so pausing an account requires navigating to Accounts. In CodexNeo, the Use auth action expands disproportionately compared with Refresh auth.

## What Changes

- Add an immediate one-click Restart Codex LB action in the CodexNeo page header.
- Coordinate the portable Electron relaunch with shutdown of its owned backend process before the replacement app starts.
- Add a Pause/Resume toggle to each eligible Dashboard account card and list row using the existing account state-transition API.
- Give Use auth and Refresh auth equal compact action sizing.

## Impact

The portable Electron shell, its preload bridge, CodexNeo header, Dashboard account controls, and their tests change. Account transition rules remain backend-authoritative. Codex Desktop is not restarted by the new Codex LB action.
