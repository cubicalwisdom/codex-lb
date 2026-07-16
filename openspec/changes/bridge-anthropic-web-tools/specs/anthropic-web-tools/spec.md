## ADDED Requirements

### Requirement: Messages bridges supported Anthropic web server tools to the native hosted tool

The Anthropic Messages facade MUST accept documented, supported versioned WebSearch and WebFetch server-tool definitions without requiring `input_schema`. It MUST require the server-tool `name` to agree with its versioned `type`, collapse one or both supported web tools into a single Responses `web_search` hosted tool, and preserve ordinary client-function tool validation and ordering. Supported WebSearch types MUST include `web_search_20250305`, `web_search_20260209`, and `web_search_20260318`; supported WebFetch types MUST include `web_fetch_20250910`, `web_fetch_20260209`, `web_fetch_20260309`, and `web_fetch_20260318`. Unknown versions or mismatched server-tool definitions MUST return an Anthropic `invalid_request_error` before upstream execution.

#### Scenario: Claude Desktop advertises built-in WebSearch

- **WHEN** a local Claude Desktop request includes `{"type":"web_search_20250305","name":"web_search"}`
- **THEN** the forwarded Responses request contains `{"type":"web_search"}`
- **AND** the request does not require a synthetic function `input_schema`

#### Scenario: Claude Desktop advertises WebSearch and WebFetch together

- **WHEN** a request contains supported versioned `web_search` and `web_fetch` server tools
- **THEN** the forwarded Responses request contains one hosted `web_search` tool
- **AND** any ordinary client function tools remain present with their original schemas

### Requirement: Web server-tool controls are preserved or rejected safely

The facade MUST translate a supported `allowed_domains` list to the Responses web-search allow-list filter and MUST translate a compatible approximate `user_location`. For ordinary API clients, it MUST NOT silently discard a `blocked_domains` restriction or another restriction whose loss would broaden permitted access; unsupported enforceable restrictions MUST return an Anthropic `invalid_request_error` before upstream execution. For the authenticated loopback-only `claudedesktop` profile, the facade MUST accept and omit `blocked_domains` to maximize built-in Desktop compatibility, and the documented contract MUST state that the mapped upstream search does not enforce that deny-list. Other non-enforceable compatibility metadata MAY be accepted without forwarding only when that limitation remains documented.

When multiple supported web tools carry hosted-tool controls, the facade MUST deduplicate them only when their enforceable configuration is identical. Conflicting allowed-domain or location controls MUST return an Anthropic `invalid_request_error` before upstream execution.

#### Scenario: Allowed domains remain enforced

- **WHEN** a supported Anthropic web server tool specifies `allowed_domains`
- **THEN** the forwarded hosted web-search tool contains the same allowed domains

#### Scenario: Claude Desktop requests maximum compatibility

- **WHEN** an authenticated loopback Claude Desktop request specifies `blocked_domains`
- **THEN** the forwarded hosted tool omits `blocked_domains`
- **AND** the upstream hosted search remains available without deny-list enforcement

#### Scenario: Other clients retain fail-closed domain handling

- **WHEN** a non-Desktop Anthropic request specifies `blocked_domains`
- **THEN** the facade returns an Anthropic `invalid_request_error` before upstream execution
- **AND** it does not run an unrestricted search

#### Scenario: Duplicate web tools disagree on restrictions

- **WHEN** WebSearch and WebFetch specify different allowed-domain or user-location controls
- **THEN** the facade returns an Anthropic `invalid_request_error` before upstream execution
- **AND** it does not select or weaken either restriction

### Requirement: Forced web-tool choice uses the hosted tool

When an Anthropic request forces the supported `web_search` or `web_fetch` tool by name, the facade MUST translate that selection to the Responses hosted web-search choice. Existing `auto`, `any`, `none`, and named client-function choices MUST retain their current behavior.

#### Scenario: WebSearch is required for the turn

- **WHEN** a request supplies `tool_choice` with type `tool` and name `web_search`
- **THEN** the forwarded Responses request forces the hosted web-search tool

### Requirement: Web tool completion uses the existing Messages response lifecycle

The facade MUST return final hosted-search answer text through the existing Anthropic non-streaming or streaming Messages lifecycle and MUST preserve terminal usage and errors. This compatibility slice MUST NOT fabricate Anthropic server-tool result blocks or citations when the upstream response does not supply sufficient equivalent data.

#### Scenario: Hosted search completes during a stream

- **WHEN** the upstream emits web-search lifecycle events followed by text deltas and a completed response
- **THEN** the facade emits the existing ordered Anthropic text-block and terminal events
- **AND** it does not expose raw Responses events to Claude Desktop

### Requirement: Claude Desktop public Workspace WebFetch avoids oversized client results

For the authenticated loopback-only `claudedesktop` profile, the facade MUST replace an eager `mcp__workspace__web_fetch` client-tool definition with the Responses hosted `web_search` tool when the active conversation contains an explicit public HTTP(S) URL. It MUST deduplicate that alias with any supported Anthropic web server tool and MUST preserve the server tool's enforceable hosted controls. A forced choice of an alias replaced for that request MUST select the hosted web tool.

The facade MUST retain the ordinary client-function definition for non-Desktop callers, for conversations without an explicit public URL, for loopback/private/local URL targets, and when the Workspace tool is deferred for ToolSearch. It MUST NOT read a path named in an oversized tool-result marker or otherwise add host filesystem access while applying this compatibility rule.

#### Scenario: Cowork fetches a public documentation URL

- **WHEN** an authenticated Claude Desktop request advertises eager `mcp__workspace__web_fetch`
- **AND** the conversation explicitly contains `https://claude.com/docs`
- **THEN** the forwarded Responses tools contain one hosted `web_search` tool instead of the Workspace client function
- **AND** the hosted model can open the page without returning the raw document through Claude's client-tool result channel

#### Scenario: Workspace-local fetch remains client-executed

- **WHEN** the same client tool is used for a loopback, private, local, or non-explicit URL
- **THEN** the forwarded tool remains an ordinary function with its original schema

#### Scenario: Deferred Workspace tool remains replayable

- **WHEN** `mcp__workspace__web_fetch` is marked `defer_loading: true`
- **THEN** it remains a function definition suitable for ToolSearch reference replay

#### Scenario: Historical ToolSearch selected the now-hosted alias

- **WHEN** an authenticated Claude Desktop request contains a prior ToolSearch result whose `tool_reference` names `mcp__workspace__web_fetch`
- **AND** the current eager definition is replaced by hosted `web_search` for an explicit public URL
- **THEN** the original Workspace name is accepted as an available hosted alias
- **AND** the historical ToolSearch call/output pair is omitted when it selected no ordinary client tools
- **AND** the alias is not reintroduced as a client-executed function

#### Scenario: Historical ToolSearch selected hosted and client tools together

- **WHEN** the prior ToolSearch result references the replaced Workspace alias and one or more ordinary client functions
- **THEN** the historical ToolSearch output retains only those ordinary function definitions
- **AND** the hosted web tool remains available through the request-level `web_search` declaration

#### Scenario: Historical ToolSearch names an unavailable tool

- **WHEN** a ToolSearch result references a name that is neither an available client function nor an alias replaced for the current request
- **THEN** the facade returns an Anthropic `invalid_request_error` before upstream execution
