# CodexNeo Windows Integration Delta

## ADDED Requirements

### Requirement: CodexNeo settings persistence

The system SHALL persist CodexNeo settings locally under the codex-lb configured data directory.

#### Scenario: Settings are read without exposing buyer token

- **WHEN** the dashboard reads CodexNeo settings
- **THEN** the response SHALL include the Codex API base URL, CodexGO provider URL, auto-refresh enabled state, refresh interval, and a boolean indicating whether a buyer token is saved
- **AND** the response SHALL NOT include the plaintext buyer token

#### Scenario: Buyer token is updated

- **WHEN** an admin saves a non-empty buyer token
- **THEN** the system SHALL encrypt the token before writing it to local settings storage
- **AND** later CodexGO use/refresh calls SHALL decrypt it only for the outgoing provider request

#### Scenario: Portable startup preference is saved

- **WHEN** an admin changes the CodexNeo `Start with Windows` setting in the Electron portable app
- **THEN** the system SHALL persist the setting with the other CodexNeo settings under the codex-lb configured data directory
- **AND** the Electron shell SHALL register or unregister the current packaged `Codex IB.exe` for current-user Windows login startup
- **AND** disabling the setting SHALL remove that login startup registration without deleting CodexNeo account or usage data

### Requirement: Codex API provider config actions

The system SHALL expose CodexNeo actions to test, set, and revert the configured Codex API provider URL for the real Windows Codex home.

#### Scenario: API URL is tested

- **WHEN** an admin triggers Auth->API Test with a Codex API base URL
- **THEN** the system SHALL run a non-mutating connectivity check against that base URL
- **AND** the system SHALL report success or the concrete failure message

#### Scenario: API URL is set

- **WHEN** an admin triggers Auth->API Set with a Codex API base URL
- **THEN** the system SHALL back up `%USERPROFILE%\.codex\config.toml` when it exists
- **AND** the system SHALL atomically write a managed provider override using `model_provider = "openai"` and `openai_base_url = "<configured URL>"`
- **AND** the system SHALL maintain a protected original `config.toml` baseline that is created only once and is not overwritten by later Set/Revert actions
- **AND** if the current config already contains a CodexNeo or legacy managed API override, the protected original baseline SHALL be created from the sanitized config with that managed override removed
- **AND** after the written config is verified, the action response SHALL report that Codex must be restarted manually to apply the provider configuration
- **AND** Auth->API Set SHALL NOT stop, kill, start, or restart Codex Desktop automatically

#### Scenario: API URL is reverted

- **WHEN** an admin triggers Auth->API Revert
- **THEN** the system SHALL back up `%USERPROFILE%\.codex\config.toml` when it exists
- **AND** the system SHALL restore the protected original `config.toml` baseline when it exists
- **AND** if no protected original baseline exists, the system SHALL atomically remove only managed CodexNeo or legacy provider overrides from the current config
- **AND** plain user `model_provider = "openai"` settings without a managed `openai_base_url` override SHALL be preserved
- **AND** after the reverted config is verified, the action response SHALL report that Codex must be restarted manually to apply the provider configuration
- **AND** Auth->API Revert SHALL NOT stop, kill, start, or restart Codex Desktop automatically

#### Scenario: Config backups are retained safely

- **WHEN** Auth->API Set or Auth->API Revert creates timestamped CodexNeo config backups
- **THEN** the system SHALL prune old web-created timestamp backups by age and count
- **AND** the protected original baseline SHALL NOT be pruned
- **AND** unrelated user backups and Windows app backups SHALL NOT be deleted by the web app retention policy

#### Scenario: Codex Desktop restart remains explicit

- **WHEN** an admin clicks the explicit Restart Codex control
- **THEN** the system MAY stop and relaunch Codex Desktop through the configured restart provider
- **AND** restart success or failure SHALL be reported in the action response

### Requirement: CodexGO auth use and refresh

The system SHALL use the configured CodexGO provider URL and encrypted buyer token to request Codex auth JSON.

#### Scenario: Use auth is triggered

- **WHEN** an admin triggers Use auth
- **THEN** the system SHALL POST to `/use` under the normalized provider URL with the buyer token as a bearer token
- **AND** the system SHALL validate the returned auth JSON before replacing `%USERPROFILE%\.codex\auth.json`

#### Scenario: Refresh auth is triggered

- **WHEN** an admin triggers Refresh auth
- **THEN** the system SHALL POST to `/refresh` under the normalized provider URL with the buyer token as a bearer token
- **AND** the system SHALL validate the returned auth JSON before replacing `%USERPROFILE%\.codex\auth.json`

### Requirement: Timed CodexGO refresh

The system SHALL support a local timed CodexGO refresh loop.

#### Scenario: Auto-refresh is enabled and configured

- **WHEN** auto-refresh is enabled and a buyer token is saved
- **THEN** the system SHALL refresh CodexGO auth at the configured interval
- **AND** the interval SHALL be constrained to a safe minute range

#### Scenario: Auto-refresh is not configured

- **WHEN** auto-refresh is disabled or no buyer token is saved
- **THEN** the scheduler SHALL skip refresh work without logging secrets

### Requirement: CodexNeo activity log

The system SHALL maintain a temporary CodexNeo activity log under the codex-lb configured data directory.

#### Scenario: Activity log streams are enabled independently

- **WHEN** OpenAI log and Management log settings are saved
- **THEN** each stream SHALL be enabled or disabled independently
- **AND** disabled streams SHALL NOT append new lines

#### Scenario: Activity log line is appended

- **WHEN** an enabled stream records a dashboard or OpenAI-compatible request summary
- **THEN** the system SHALL append a timestamped safe summary to the temporary log file
- **AND** the log line SHALL NOT include buyer tokens, API keys, auth tokens, prompts, request bodies, or full responses

#### Scenario: Activity log is cleared

- **WHEN** an admin clears the activity log
- **THEN** the system SHALL clear the visible log state
- **AND** the system SHALL delete the temporary log file when it exists

#### Scenario: Activity log is capped

- **WHEN** more than 1000 activity log entries are appended
- **THEN** the system SHALL retain only the latest 1000 entries
- **AND** reads SHALL return only those retained entries

#### Scenario: Activity log coverage is bounded to configured streams

- **WHEN** OpenAI log is enabled
- **THEN** the system SHALL append safe summaries for `/v1/*` API requests
- **WHEN** Management log is enabled
- **THEN** the system SHALL append safe summaries for `/api/*` API requests
- **AND** the system SHALL skip `/api/codexneo/activity-log` to prevent recursive log entries
- **AND** the system SHALL NOT claim to capture non-API page loads or static assets

#### Scenario: Activity log content overflows

- **WHEN** the visible log contains many lines
- **THEN** the dashboard SHALL keep the Activity log content inside a fixed-height scrollable area
- **AND** the Clear action SHALL remain visible without requiring the log content itself to be scrolled to the top

### Requirement: Codex Home account discovery

The system SHALL discover Codex Home account state for CodexNeo without exposing auth secrets.

#### Scenario: Local registry account state is loaded

- **WHEN** `%USERPROFILE%\.codex\accounts\registry.json` exists and contains account rows
- **THEN** the system SHALL parse safe account fields including account key, selector, email, alias, account name, plan, auth mode, active state, last usage, and cached usage windows
- **AND** the system SHALL recognize managed auth snapshots stored as either raw `<account_key>.auth.json` filenames or URL-safe base64-encoded account-key filenames
- **AND** the response SHALL NOT include access tokens, refresh tokens, id tokens, or raw auth JSON

#### Scenario: Account table sortable columns

- **WHEN** CodexNeo account rows are displayed
- **THEN** the table SHALL include a sortable `#` source-order number column
- **AND** the `Plan`, `5h`, `Weekly`, `Avail`, and `Status / Last` headers SHALL be sortable
- **AND** numeric usage columns SHALL sort by percentage values instead of display text
- **AND** `Avail` SHALL sort `Ready` before `Backup` before unavailable or temporary states
- **AND** `Status / Last` SHALL sort `Fresh` before `Stored` before `Unknown` before unavailable or error states
- **AND** sorting SHALL preserve selected account keys and SHALL NOT mutate Codex/Backup location state
- **AND** sortable headers SHALL NOT render visible helper labels such as `SORT`, `ASC`, or `DESC`

#### Scenario: Registry is missing or invalid

- **WHEN** the Codex Home account registry is missing or invalid
- **THEN** the system SHALL return an empty account list with a safe status message instead of crashing

### Requirement: Codex Home controls

The system SHALL expose Codex Home controls that use the configured Codex Home for CodexNeo account, auth, and config operations.

#### Scenario: Codex Home path is saved

- **WHEN** an admin enters or selects an existing Codex Home folder
- **THEN** the system SHALL validate that it is a directory
- **AND** the system SHALL persist the absolute path locally
- **AND** subsequent CodexNeo account discovery, auth writes, provider config writes, imports, exports, and account actions SHALL use that path

#### Scenario: Codex Home path is reset

- **WHEN** an admin resets Codex Home
- **THEN** the system SHALL clear the custom path
- **AND** subsequent operations SHALL use the default `%USERPROFILE%\.codex`

#### Scenario: Folder picker is requested

- **WHEN** an admin clicks Select Codex home
- **THEN** the backend MAY open a native Windows folder picker and return the selected absolute path
- **AND** if the picker is unavailable or cancelled, the system SHALL return a safe failure message so the manual path box remains usable

### Requirement: CodexNeo import and export

The system SHALL expose import and export controls with no-overwrite safeguards.

#### Scenario: Import file or folder is requested

- **WHEN** an admin requests Import file or Import folder with a path
- **THEN** the system SHALL validate the local path exists
- **AND** the system SHALL run the configured Codex auth import command against the selected Codex Home
- **AND** supported auth snapshots SHALL also be imported into the codex-lb encrypted Accounts database
- **AND** the activity log SHALL record a safe summary without auth JSON or token contents

#### Scenario: Browser import picker is requested

- **WHEN** an admin clicks Import file without a manually entered file path
- **THEN** the browser SHALL open a file picker and upload the selected auth JSON file to the backend for import
- **WHEN** an admin clicks Import folder without a manually entered folder path
- **THEN** the browser SHALL open a folder-capable file picker and upload the selected JSON files to the backend for import
- **AND** the backend SHALL NOT block on a server-side native Windows picker for browser import actions
- **AND** cancellation SHALL leave the page usable without a long-running busy overlay

#### Scenario: Export all is requested

- **WHEN** an admin requests Export all
- **THEN** the system SHALL create a timestamped export directory under the codex-lb data directory unless an explicit destination is provided
- **AND** the system SHALL copy known managed auth snapshots from the configured Codex Home accounts directory and the app-owned backup store
- **AND** the system SHALL report a safe no-op response when no account auth snapshots are available to export
- **AND** the system SHALL NOT overwrite existing export files

#### Scenario: Export selected is requested

- **WHEN** an admin exports selected accounts
- **THEN** the system SHALL copy only matching managed auth snapshots into a timestamped export directory
- **AND** the system SHALL search both the configured Codex Home accounts directory and the app-owned Backup store for selected snapshots
- **AND** selected snapshot lookup SHALL support real Codex URL-safe base64-encoded account-key filenames
- **AND** filenames SHALL be sanitized and de-duplicated
- **AND** missing snapshots SHALL be reported without exposing token contents

### Requirement: CodexNeo account actions

The system SHALL expose confirmation-gated account actions for selected Codex Home account keys.

#### Scenario: Metadata action is requested

- **WHEN** an admin marks accounts temporarily unavailable or marks accounts available
- **THEN** the system SHALL update local codex-lb account metadata for the selected account keys
- **AND** the account table SHALL reflect the metadata on the next load

#### Scenario: Switch or delete action is requested

- **WHEN** an admin switches, switches and restarts, or deletes selected accounts
- **THEN** the system SHALL route the operation through the configured Codex auth command using the selected Codex Home
- **AND** Switch and Delete SHALL require explicit UI confirmation
- **AND** Switch and Restart SHALL invoke restart only after the switch command succeeds

#### Scenario: Delete removes account locations

- **WHEN** an admin deletes selected accounts
- **THEN** the system SHALL remove those accounts from Codex Home
- **AND** the system SHALL remove matching backup snapshots and backup registry rows
- **AND** if the active Codex Home account is removed, the system SHALL clear the active root auth file

### Requirement: CodexNeo Codex and Backup location controls

The CodexNeo account table SHALL expose Codex Home and Backup location controls that mirror CodexNeo executable behavior.

#### Scenario: Account location columns are rendered

- **WHEN** the CodexNeo account table is shown
- **THEN** the `Codex` and `Backup` columns SHALL render checkboxes instead of text placeholders
- **AND** the checkboxes SHALL reflect whether each account is present in Codex Home and in the app-owned backup store

#### Scenario: Single account location is changed

- **WHEN** an admin toggles a row-level `Codex` checkbox off
- **THEN** the system SHALL remove that account from Codex Home only if the account remains present in Backup
- **WHEN** an admin toggles a row-level `Backup` checkbox off
- **THEN** the system SHALL delete that account's backup snapshot and backup registry row only if the account remains present in Codex Home
- **AND** the system SHALL block row changes that would leave the account absent from both Codex Home and Backup
- **AND** location mutation APIs SHALL reject any location value other than `codex` or `backup`

#### Scenario: Bulk location controls are changed

- **WHEN** an admin enables `Codex all`
- **THEN** all currently visible accounts missing from Codex Home SHALL be restored from Backup when backup data is available
- **WHEN** an admin disables `Codex all`
- **THEN** all currently visible accounts that can safely leave Codex Home SHALL be removed from Codex Home
- **AND** rows that would be absent from both Codex Home and Backup SHALL be skipped
- **AND** `Codex all` SHALL reflect whether all currently visible rows are in Codex Home, not a future restore policy
- **WHEN** an admin enables `Backup all`
- **THEN** all currently visible accounts missing from Backup SHALL be copied to Backup when live Codex data is available
- **WHEN** an admin disables `Backup all`
- **THEN** all currently visible accounts that can safely leave Backup SHALL be removed from Backup
- **AND** rows that would be absent from both Codex Home and Backup SHALL be skipped
- **AND** `Backup all` SHALL reflect whether all currently visible rows are in Backup
- **AND** future newly discovered live Codex accounts SHALL be copied to Backup only while the previous visible-table `Backup all` state remains enabled
- **AND** manually turning any row-level Backup checkbox off SHALL clear that future Backup-all state until all visible rows are backed up again

### Requirement: CodexNeo and Accounts tab two-way sync

The system SHALL keep CodexNeo account availability and the main Accounts tab in sync through explicit import, delete, and Codex Home discovery operations.

#### Scenario: Account is imported from the Accounts tab

- **WHEN** an admin imports an `auth.json` file through the main Accounts tab
- **THEN** the system SHALL store the account in the codex-lb encrypted Accounts database
- **AND** the system SHALL register the same auth snapshot into the configured Codex Home for CodexNeo/native Codex use
- **AND** failures in the Codex Home registration SHALL be reported safely without logging token contents

#### Scenario: Account is added by CodexGO or native Codex Home

- **WHEN** a valid Codex auth snapshot appears in the configured Codex Home without using the Codex IB Add account flow
- **THEN** the CodexNeo account refresh SHALL discover the snapshot without launching a login flow
- **AND** the CodexNeo account refresh endpoint SHALL remain read-only and SHALL NOT mutate the codex-lb encrypted Accounts database
- **AND** explicit Sync or enabled Auto sync SHALL import the account into the codex-lb encrypted Accounts database using the existing AccountsService identity and duplicate rules
- **AND** the system SHALL copy newly discovered managed Codex Home snapshots into the app-owned Backup store only when the previous visible-table `Backup all` state is enabled
- **AND** unsupported JSON files SHALL be skipped without exposing token contents

#### Scenario: Account is imported from the CodexNeo tab

- **WHEN** an admin imports an auth snapshot file or folder through CodexNeo
- **THEN** the system SHALL register the snapshot with the configured Codex Home
- **AND** supported auth snapshots SHALL be imported into the codex-lb encrypted Accounts database using the existing AccountsService identity/duplicate rules
- **AND** failures SHALL be reported safely without logging token contents

#### Scenario: Account is deleted from the Accounts tab

- **WHEN** an admin deletes an account from the main Accounts tab
- **THEN** the system SHALL remove the account from the codex-lb Accounts database using the existing delete-history behavior
- **AND** the system SHALL attempt to unregister matching account snapshots from the configured Codex Home
- **AND** the system SHALL remove matching app-owned Backup registry rows and auth snapshots for the same real auth identity, even if Codex Home unregister succeeds through the external Codex auth command
- **AND** the system SHALL remove matching app-owned Backup data when the account no longer has a live Codex Home snapshot but still has a Backup snapshot
- **AND** the delete response SHALL report Codex Home sync status safely

#### Scenario: Account is deleted from the CodexNeo tab

- **WHEN** an admin deletes selected CodexNeo account keys
- **THEN** the system SHALL remove those keys from the configured Codex Home through the Codex auth command
- **AND** the system SHALL attempt to remove matching rows from the codex-lb Accounts database without deleting request history
- **AND** the system SHALL preserve enough pre-delete auth snapshot data to match Accounts rows even if the Codex auth command deletes live snapshots
- **AND** matching Codex Home and app-owned Backup registry rows and auth snapshots SHALL be removed by real auth identity, not only by exact account-key string
- **AND** the system SHALL NOT delete matching Accounts rows when the Codex auth command fails
- **AND** the action response SHALL report the combined result safely

#### Scenario: Account is available only in Backup

- **WHEN** a CodexNeo account exists only in the app-owned Backup store
- **THEN** CodexNeo account refresh SHALL keep the row visible as Backup
- **AND** the system SHALL import the backup snapshot into the codex-lb encrypted Accounts database so the Codex IB API can use the account

### Requirement: CodexNeo account table cleanup

The CodexNeo account table SHALL omit fields and row actions that are no longer required.

#### Scenario: Account table is rendered

- **WHEN** the CodexNeo account table is shown
- **THEN** the table SHALL NOT display the `API`, `API h`, or `API d` columns
- **AND** the table SHALL display an `Avail` column with a safe account availability label
- **AND** the per-row action list SHALL NOT display `Use API`
- **AND** the selected-account toolbar SHALL NOT display `Use API`

### Requirement: CodexNeo refresh action and account freshness display

The CodexNeo account table SHALL mirror CodexNeo Windows app availability and status display while avoiding the deprecated Use API action.

#### Scenario: Account availability and status are rendered

- **WHEN** the CodexNeo account table loads accounts from Codex Home and Backup state
- **THEN** each account SHALL include an `Avail` label derived from location and availability metadata such as `Ready`, `Backup`, or `Temp off`
- **AND** each account SHALL include `Status / Last` text derived from usage status and relative last-usage time such as `Fresh / just now` or `Stored / 7h ago`
- **AND** a valid top-level Codex Home `auth.json` SHALL be shown as an active Codex account row even when it has not yet been materialized into the managed `accounts/registry.json` snapshot store
- **AND** `Unknown` SHALL be used only when no usage status, usage window, Codex presence, Backup presence, or Accounts status source can provide a stronger status
- **AND** raw Unix timestamps SHALL NOT be displayed as the `Status / Last` cell text

#### Scenario: Selected accounts are refreshed

- **WHEN** an admin selects one or more accounts and clicks `Refresh selected`
- **THEN** the dashboard SHALL refresh the CodexNeo accounts state instead of invoking the deprecated Use API preference action
- **AND** the selected-account toolbar SHALL NOT expose a `Use API` button
- **AND** the dashboard API SHALL NOT expose the deprecated selected-account Use API route

#### Scenario: CodexGO auth refresh updates account lists

- **WHEN** an admin triggers CodexGO Use auth or Refresh auth
- **THEN** the dashboard SHALL refresh the CodexNeo account table after the action completes
- **AND** the dashboard SHALL refresh the main Accounts tab data after the action completes
- **AND** repeated syncs of the same Codex Home auth snapshots SHALL update the existing Accounts rows instead of creating duplicate `__copy` rows

#### Scenario: Account controls remain aligned

- **WHEN** the CodexNeo account action controls are rendered on a desktop viewport
- **THEN** the selected-account toolbar SHALL NOT display validity date controls
- **AND** the account table SHALL keep action buttons on one line with enough minimum width for the visible columns

#### Scenario: Duplicate auth snapshots are listed once

- **WHEN** the same real account identity appears in multiple Codex Home or Backup auth snapshots
- **THEN** the CodexNeo table SHALL display one row for that identity
- **AND** the row SHALL merge Codex Home and Backup location flags
- **AND** the row SHALL prefer a live Codex Home account key for row actions when a live copy exists
- **AND** creating or refreshing an app-owned Backup snapshot SHALL replace older app-owned Backup copies for the same real auth identity instead of accumulating duplicate Backup rows
- **AND** the system SHALL NOT expose access tokens, refresh tokens, ID tokens, API keys, or raw auth JSON contents while detecting duplicates

#### Scenario: Generated Accounts copy rows are not API candidates

- **WHEN** legacy codex-lb Accounts rows include generated `__copy` rows for the same upstream ChatGPT account identity
- **THEN** dashboard account listing and API account candidate selection SHALL use only one canonical row for that generated-copy group
- **AND** ordinary non-generated duplicate rows MAY still be visible for duplicate-warning workflows
- **AND** read-only listing routes SHALL NOT delete historical duplicate rows while applying display/routing dedupe
- **AND** explicit sync/import write paths MAY consolidate generated-copy rows for the same upstream identity and remove the generated duplicate rows after moving associated usage/history data to the canonical row

#### Scenario: Codex Home Accounts refresh gives visible feedback

- **WHEN** an admin clicks the Codex Home Accounts `Refresh` button
- **THEN** the dashboard SHALL run the CodexNeo accounts refresh path
- **AND** the button or nearby status text SHALL indicate refresh activity or completion
- **AND** a disabled refresh control SHALL clearly reflect that the page is busy or read-only

#### Scenario: CodexNeo account rows can be selected in bulk

- **WHEN** an admin clicks the CodexNeo `Select all` control
- **THEN** all currently visible CodexNeo account table rows SHALL become selected
- **AND** Codex Home and Backup location checkboxes SHALL NOT be changed by selection alone

#### Scenario: CodexGO refresh interval unit is visible

- **WHEN** the CodexGO refresh interval control is shown
- **THEN** the control SHALL visibly indicate that the stored interval value is in minutes

#### Scenario: Delete selected removes accounts everywhere

- **WHEN** an admin selects multiple CodexNeo account rows and clicks `Delete selected`
- **THEN** the backend SHALL call the Codex auth remove command with one account selector per command invocation
- **AND** matching Codex IB Accounts rows SHALL be deleted only after the external remove command succeeds
- **AND** matching Codex Home and app-owned Backup snapshots and registry entries SHALL be removed after successful delete
- **AND** a failed external remove SHALL leave matching Codex IB Accounts rows and app-owned Backup snapshots intact

#### Scenario: Newer Codex registry schema can be deleted locally

- **WHEN** the configured Codex registry schema is known to be newer than the supported local Codex auth binary schema
- **THEN** the backend SHALL bypass the external Codex auth remove command and use local Codex Home and app-owned Backup registry/snapshot deletion as a compatibility fallback
- **AND** the backend SHALL use the same local compatibility fallback if the external Codex auth remove command returns an equivalent unsupported-registry-schema error
- **AND** the main Accounts-tab delete flow SHALL report the Codex Home sync as successful after that fallback removes the matching Codex Home account
- **AND** the fallback SHALL NOT run for unrelated Codex auth command failures

#### Scenario: Backup-only encoded account keys can be deleted on Windows

- **WHEN** an admin deletes a Backup-only CodexNeo account whose account key contains characters that are invalid in Windows filenames
- **THEN** the backend SHALL remove the app-owned Backup registry row and encoded auth snapshot without attempting to unlink an invalid raw Windows path
- **AND** the CodexNeo account list SHALL no longer include that Backup-only row after the delete refresh
- **AND** delete API failures SHALL be surfaced in the dashboard with a visible error toast

#### Scenario: Explicit master sync reconciles CodexNeo and Codex IB

- **WHEN** an admin clicks the CodexNeo `Sync` control
- **THEN** the dashboard SHALL sync valid configured Codex Home and app-owned Backup auth snapshots into the encrypted Codex IB Accounts database
- **AND** eligible Codex IB Accounts rows that are missing from Codex Home SHALL be registered into the configured Codex Home
- **AND** a Codex IB account whose only configured Codex Home presence is root `auth.json` SHALL be registered into the managed Codex Home accounts registry/snapshot store with a token-free registry row and a local auth snapshot so it can continue to appear in the CodexNeo account table
- **AND** generated Accounts `__copy` rows for the same upstream identity MAY be consolidated during this write operation
- **AND** the backend SHALL write a local `codexneo-master-registry.json` inventory under the codex-lb data directory
- **AND** the master registry and action responses SHALL NOT contain access tokens, refresh tokens, ID tokens, API keys, buyer tokens, or raw auth JSON contents
- **AND** the CodexNeo and main Accounts queries SHALL be invalidated after the sync completes

#### Scenario: Codex Home Accounts auto refreshes while the page is open

- **WHEN** an admin enables Codex Home auto refresh on the CodexNeo page
- **THEN** the page SHALL refresh the CodexNeo account list and diagnostics on the configured seconds interval
- **AND** the interval control SHALL accept seconds and clamp unsafe values to the supported 5-3600 second range
- **AND** refresh activity SHALL show safe status feedback without exposing token or auth JSON contents

#### Scenario: Auto sync reconciles a visible mismatch

- **WHEN** the Accounts sync diagnostic reports a CodexNeo and Codex IB account-count mismatch
- **THEN** the diagnostic SHALL use an error/red status
- **AND** enabling Auto sync SHALL run the same safe master sync operation as the explicit `Sync` button
- **AND** the page SHALL avoid overlapping auto-sync runs while one sync is already pending
- **AND** synced queries SHALL be invalidated through the normal sync success path

#### Scenario: CodexNeo actions do not show secondary browser confirmations

- **WHEN** an admin clicks CodexNeo actions such as Restart Codex, Switch, Switch & Restart, or Delete selected
- **THEN** the action SHALL execute directly from the button click without a `window.confirm` browser dialog
- **AND** backend validation failures SHALL still appear through the existing visible error toast or banner mechanisms

#### Scenario: Newer Codex registry schema can be switched locally

- **WHEN** the configured Codex registry schema is known to be newer than the supported local Codex auth binary schema
- **THEN** Switch and Switch & Restart SHALL use a local compatibility fallback instead of failing on `codex-auth switch`
- **AND** the fallback SHALL set the active Codex Home account and copy the selected account snapshot to root `auth.json`
- **AND** Switch & Restart SHALL still restart Codex Desktop after a successful local switch because restart is intended runtime behavior
- **AND** the fallback SHALL NOT run for unrelated Codex auth command failures

### Requirement: CodexNeo health diagnostics

The CodexNeo page SHALL expose a compact diagnostics panel adapted for the Codex IB + CodexNeo web setup.

#### Scenario: Health diagnostics are loaded

- **WHEN** the CodexNeo page loads diagnostics
- **THEN** the dashboard SHALL show safe status badges for Codex IB server/API availability, configured Codex Home, Codex Home registry/snapshot count, app-owned Backup store/snapshot count, Accounts sync count, Activity log stream state, CodexGO auth configuration, and OpenAI-compatible bridge configuration
- **AND** each badge SHALL use `ok`, `warning`, or `error` status with actionable text
- **AND** safe paths or URLs MAY expose copy actions
- **AND** diagnostics SHALL NOT expose buyer tokens, access tokens, refresh tokens, ID tokens, API keys, or raw auth JSON contents

#### Scenario: One diagnostics source is unavailable

- **WHEN** one diagnostics source such as Codex Home registry or Codex IB Accounts storage is unavailable
- **THEN** the diagnostics endpoint SHALL still return the remaining badge rows
- **AND** the affected badge SHALL report warning or error status instead of making the entire CodexNeo page fail with a generic error

### Requirement: Dashboard-only CodexNeo Windows usage import

The system SHALL support a one-time dashboard-only import of rough aggregate usage values from the CodexNeo Windows app.

#### Scenario: Rough Windows usage values are imported

- **WHEN** the operator runs the CodexNeo Windows usage import script
- **THEN** the system SHALL write idempotent synthetic dashboard request-log rows that contribute roughly 337,735,265 tokens today, 2.5B lifetime tokens, and about $8342.81 estimated cost
- **AND** the import SHALL affect dashboard aggregate metrics only
- **AND** the import SHALL NOT add an ongoing calculator UI or change account auth material
- **AND** rerunning the import SHALL replace the previous synthetic import rows instead of duplicating totals

### Requirement: Hidden Windows startup launcher

The native Windows installation SHALL provide a hidden-window startup launcher for Codex IB.

#### Scenario: Windows starts for the current user

- **WHEN** the current Windows user logs in and the Startup VBS is present
- **THEN** the VBS SHALL launch the Codex IB startup BAT with a hidden window style
- **AND** the BAT SHALL start the native codex-lb server from the source checkout
- **AND** the launcher SHALL prefer the repo `.venv` FastAPI executable and write startup logs under `%LOCALAPPDATA%\CodexIB`
- **AND** no visible command prompt window SHALL remain open for normal startup
