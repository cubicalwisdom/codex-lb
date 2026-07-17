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

The facade MUST return final hosted-search answer text through the existing Anthropic non-streaming or streaming Messages lifecycle and MUST preserve terminal usage and errors. When the upstream response supplies a completed web-search call plus result entries containing the exact Anthropic-compatible opaque result fields, the facade MUST translate them into ordered `server_tool_use` and `web_search_tool_result` blocks. It MUST attach citations to text only when the upstream annotation supplies the exact Anthropic-compatible citation fields. Public Responses URL annotations or lifecycle events that lack those opaque fields MUST retain the existing text-only fallback. The facade MUST NOT fabricate encrypted result content, encrypted citation indexes, cited text, server-tool results, or citations.

#### Scenario: Hosted search completes during a stream

- **WHEN** the upstream emits web-search lifecycle events followed by text deltas and a completed response
- **THEN** the facade emits the existing ordered Anthropic text-block and terminal events
- **AND** it does not expose raw Responses events to Claude Desktop

#### Scenario: Exact hosted result data becomes Anthropic blocks

- **WHEN** a completed upstream web-search item contains a query and result entries with URL, title, and upstream-supplied encrypted content
- **THEN** the Messages response contains an ordered `server_tool_use` block followed by its `web_search_tool_result`
- **AND** the facade preserves the upstream opaque fields verbatim

#### Scenario: Public URL annotations remain a text fallback

- **WHEN** the upstream supplies answer text with public `url_citation` annotations but no Anthropic-compatible encrypted citation index
- **THEN** the facade returns the answer text without fabricated Anthropic citations

### Requirement: Claude Desktop public Workspace WebFetch avoids oversized client results

For the authenticated loopback-only `claudedesktop` profile, the facade MUST replace an `mcp__workspace__web_fetch` client-tool definition with the Responses hosted `web_search` tool when the latest human user prompt contains one or more explicit HTTP(S) targets and every such target is public, whether Claude advertises that alias eagerly or with `defer_loading`. It MUST deduplicate that alias with any supported Anthropic web server tool and MUST preserve the server tool's enforceable hosted controls. A forced choice of an alias replaced for that request MUST select the hosted web tool.

The facade MUST retain the ordinary client-function definition for non-Desktop callers, for conversations without an explicit public URL, and for loopback/private/local URL targets. It MUST NOT read a path named in an oversized tool-result marker or otherwise add host filesystem access while applying this compatibility rule.

Claude Desktop can omit WebFetch from a dynamic ToolSearch result because of its own permission policy, then invoke `mcp__workspace__web_fetch` client-side without advertising that alias in the current Messages `tools` array. The facade cannot replace a tool definition that the client did not send. Such an invocation remains governed by Claude's permission mode: the current Desktop Auto classifier can reject it as a proxy for a denied WebFetch operation, while Manual mode can present or execute the client-side fetch. This client-policy boundary MUST NOT be described as an adapter HTTP or hosted-web failure.

#### Scenario: Cowork fetches a public documentation URL

- **WHEN** an authenticated Claude Desktop request advertises eager `mcp__workspace__web_fetch`
- **AND** the conversation explicitly contains `https://claude.com/docs`
- **THEN** the forwarded Responses tools contain one hosted `web_search` tool instead of the Workspace client function
- **AND** the hosted model can open the page without returning the raw document through Claude's client-tool result channel

#### Scenario: Workspace-local fetch remains client-executed

- **WHEN** the same client tool is used for a loopback, private, local, or non-explicit URL
- **THEN** the forwarded tool remains an ordinary function with its original schema

#### Scenario: Historical public URL does not override the current local target

- **WHEN** an older user prompt contains a public URL
- **AND** the latest human user prompt targets a loopback, private, or local URL
- **THEN** the Workspace tool remains an ordinary client function

#### Scenario: Mixed public and local targets remain client-executed

- **WHEN** the latest human user prompt contains both public and loopback, private, or local URLs
- **THEN** the Workspace tool remains an ordinary client function rather than losing local-network access

#### Scenario: Deferred public Workspace fetch uses the hosted tool

- **WHEN** `mcp__workspace__web_fetch` is marked `defer_loading: true`
- **AND** the active Claude Desktop conversation contains an explicit public HTTP(S) URL
- **THEN** it is replaced by the hosted `web_search` tool
- **AND** any historical ToolSearch reference to the alias remains resolvable through hosted-alias bookkeeping

#### Scenario: Deferred private Workspace fetch remains client-executed

- **WHEN** `mcp__workspace__web_fetch` is marked `defer_loading: true`
- **AND** the active Claude Desktop conversation targets a loopback, private, or local URL
- **THEN** it remains a function definition suitable for client execution

#### Scenario: Historical ToolSearch selected the now-hosted alias

- **WHEN** an authenticated Claude Desktop request contains a prior ToolSearch result whose `tool_reference` names `mcp__workspace__web_fetch`
- **AND** the current definition is replaced by hosted `web_search` for an explicit public URL
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
