# Fix CodexNeo Backup Identity and Pool Usage

## Why

Managed backup registry rows copied from root `auth.json` retain a mutable `auth_path`. After the provider rotates the root file, identity decoration can treat an older account-specific backup as the new root identity. This hides the real backup state, makes bulk actions count physical duplicate rows instead of the three visible logical identities, and re-adds the hidden account as a pool-only row. Pool-only rows then lose their existing quota display because the usage query excludes their account ids.

## What Changes

- Store only stable account metadata in managed backup registry rows and resolve identity from the immutable account-specific snapshot before any mutable root path.
- Collapse equivalent root/live/backup rows before bulk location actions and count messages by visible logical identity.
- Query usage history for every canonical Accounts row, including rows with no current Codex Home decoration.
- Repair legacy backup registry rows opportunistically when they are saved, without changing credentials or account membership.

## Non-goals

- Change provider rotation, proxy routing, account status policy, or automatic deletion.
- Restart Codex Desktop or the running portable app automatically.
