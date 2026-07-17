# outbound-http-clients Specification

## Purpose

Define outbound HTTP client behavior so upstream OAuth and API calls use stable headers, personas, and proxy handling.
## Requirements
### Requirement: OAuth authorize requests use a configurable originator persona
Browser OAuth authorize requests MUST include an `originator` query parameter. The service MUST default that parameter to `codex_chatgpt_desktop` and MUST let operators override it through configuration when they need a different first-party Codex persona.

#### Scenario: default OAuth authorize originator uses the Desktop persona
- **WHEN** the operator does not configure an override
- **THEN** the browser OAuth authorize URL includes `originator=codex_chatgpt_desktop`

#### Scenario: configured OAuth authorize originator falls back to the CLI persona
- **WHEN** the operator configures the OAuth authorize originator as `codex_cli_rs`
- **THEN** the browser OAuth authorize URL includes `originator=codex_cli_rs`

### Requirement: Upstream websocket handshakes auto-detect standard proxy environment variables

When operators don't explicitly configure `upstream_websocket_trust_env`, upstream websocket handshakes MUST honor standard outbound proxy environment variables before connecting directly.
Explicit configuration MUST still override auto-detection.

#### Scenario: secure websocket handshakes honor scheme-compatible env proxies by default

- **WHEN** an upstream websocket URL uses the `wss://` scheme
- **AND** `wss_proxy`, `socks_proxy`, `https_proxy`, or `all_proxy` is set
- **AND** `upstream_websocket_trust_env` is not explicitly configured
- **THEN** upstream websocket handshakes use the configured proxy instead of bypassing it

#### Scenario: plain websocket handshakes honor scheme-compatible env proxies by default

- **WHEN** an upstream websocket URL uses the `ws://` scheme
- **AND** `ws_proxy`, `socks_proxy`, `https_proxy`, `http_proxy`, or `all_proxy` is set
- **AND** `upstream_websocket_trust_env` is not explicitly configured
- **THEN** upstream websocket handshakes use the configured proxy instead of bypassing it

#### Scenario: ws handshakes preserve HTTPS proxy fallback

- **WHEN** an upstream websocket URL uses the `ws://` scheme
- **AND** `https_proxy` is set without a `ws_proxy` or `http_proxy` override
- **THEN** the upstream websocket handshake uses the `https_proxy` value before falling back to `all_proxy`

#### Scenario: explicit direct-connect override bypasses env proxies

- **WHEN** `upstream_websocket_trust_env=false`
- **AND** standard outbound proxy environment variables are set
- **THEN** upstream websocket handshakes connect directly without using those proxies

### Requirement: Runtime version status checks latest GitHub release

The service SHALL expose a dashboard-auth protected runtime version status API that reports a running application display label, the latest known GitHub release version when available, whether an update is available, and the time of the latest lookup attempt. The lookup MUST be cached in-process to avoid per-request GitHub traffic, and lookup failures MUST NOT cause the API to fail. When a portable build uses a display label that differs from its canonical package version, GitHub-release comparison and the release-check user agent MUST continue to use the canonical package version; only the reported dashboard `currentVersion` value MAY use the display label.

#### Scenario: Latest release is newer than current version

- **WHEN** the running version is `1.19.0`
- **AND** the GitHub latest release tag is `v1.20.0`
- **THEN** the runtime version status reports `currentVersion: "1.19.0"`, `latestVersion: "1.20.0"`, and `updateAvailable: true`

#### Scenario: Latest release is newer than canonical package version

- **GIVEN** the running canonical package version is `1.20.1`
- **AND** the portable display label is `v1.21parity`
- **WHEN** the GitHub latest release tag is `v1.21.0`
- **THEN** the runtime version status reports `currentVersion: "v1.21parity"`, `latestVersion: "1.21.0"`, and `updateAvailable: true`

#### Scenario: GitHub lookup fails

- **WHEN** the GitHub latest release lookup fails
- **THEN** the runtime version status API still returns the current version
- **AND** `updateAvailable` is `false`

#### Scenario: Version lookup is unavailable for a parity display label

- **GIVEN** the portable display label is `v1.21parity`
- **WHEN** the GitHub latest release lookup fails
- **THEN** the runtime version status API still returns `currentVersion: "v1.21parity"`

### Requirement: Model refresh recovers from shared HTTP client transport failures

When the model registry refresh path fails before receiving an upstream HTTP response because of a transport-level error, the system MUST treat that failure as recoverable transport state, rebuild the shared outbound HTTP client, and retry the failed model-refresh operation at most once for the current failover cycle. HTTP status failures, invalid upstream payloads, and permanent authentication failures MUST NOT trigger shared-client rotation.

#### Scenario: model fetch transport failure rotates the shared client once

- **WHEN** a model refresh attempts to fetch upstream models for an active account
- **AND** the fetch fails with a timeout, `aiohttp.ClientError`, or OS-level transport error before an upstream HTTP response is received
- **THEN** the system rotates the shared outbound HTTP client
- **AND** retries the model fetch once with the replacement client
- **AND** does not perform additional client rotations for later transport errors in the same failover cycle

#### Scenario: token refresh transport failure also rotates the shared client once

- **WHEN** model refresh needs to refresh an account token before fetching models
- **AND** the token refresh fails with a timeout, `aiohttp.ClientError`, or OS-level transport error before an upstream HTTP response is received
- **THEN** the system rotates the shared outbound HTTP client
- **AND** retries the token refresh once with the replacement client
- **AND** preserves existing permanent/non-permanent refresh error classification for non-transport failures

### Requirement: Shared outbound HTTP client rotation preserves in-flight users

Callers that use the default shared outbound HTTP session or retry client MUST lease the current shared client for the full duration of their upstream operation. Rotating the shared client MUST make new callers use the replacement client while deferring closure of the retired client until all active leases on that retired client have released. Process shutdown MAY force-close active and retired clients to keep shutdown bounded.

#### Scenario: in-flight request keeps using retired client until release

- **WHEN** an upstream operation acquires a lease on the current shared client
- **AND** model refresh rotates the shared client after a transport failure
- **THEN** new shared-client callers use the replacement client
- **AND** the retired client remains open until the in-flight operation releases its lease

#### Scenario: long-lived operations hold one lease across their whole upstream exchange

- **WHEN** a shared-client caller performs a streaming response, compact request, transcription request, usage fetch, token refresh, OAuth call, model fetch, or file create/finalize poll loop
- **THEN** the caller holds a shared-client lease until the operation has finished consuming the upstream response or poll loop
- **AND** a concurrent shared-client rotation does not close that operation's client mid-exchange

#### Scenario: shutdown force-closes active leases

- **WHEN** the application is shutting down
- **AND** active leases still exist on the current or retired shared client
- **THEN** global HTTP client close is allowed to force-close those clients instead of waiting indefinitely for long-lived streams

### Requirement: Upstream Responses egress uses a canonical Codex fingerprint

When an OpenAI-compatible client is forwarded to the upstream Codex Responses API, the proxy MUST replace SDK-specific user-agent and client fingerprint headers with the current Codex CLI fingerprint before upstream HTTP or WebSocket egress. Native Codex callers MUST preserve their valid native fingerprint. The selected account identifier MUST replace any caller-supplied account identity value.

#### Scenario: OpenAI-compatible WebSocket caller is normalized before egress

- **WHEN** an OpenAI-compatible client opens a Responses WebSocket with an SDK user agent and client headers
- **THEN** upstream receives the canonical Codex CLI user agent rather than the SDK fingerprint
- **AND** upstream receives the selected account identity rather than a caller-supplied account value

### Requirement: Outbound HTTP and WebSocket sessions transparently tunnel through a SOCKS proxy

The outbound HTTP and WebSocket clients MUST use a configured SOCKS proxy for all
upstream connections when any supported proxy environment variable carries a
SOCKS URL.
Configuring a SOCKS proxy MUST NOT require code changes — setting an environment
variable MUST be sufficient.

#### Scenario: SOCKS5 proxy is active — HTTP session uses ProxyConnector

- **GIVEN** `SOCKS_PROXY=socks5://gateway:1080` (or any equivalent env var below)
- **WHEN** the shared outbound HTTP client is initialised
- **THEN** the HTTP session uses a `ProxyConnector` built from that URL
- **AND** `trust_env=False` is passed to `aiohttp.ClientSession` to prevent double-proxying

#### Scenario: SOCKS5 proxy is active — WebSocket session routes through proxy when opt-in

- **GIVEN** a SOCKS URL is detected in the environment
- **AND** `upstream_websocket_trust_env=True` is configured
- **WHEN** the shared outbound WebSocket client is initialised
- **THEN** the WebSocket session uses a `ProxyConnector` built from the same SOCKS URL
- **AND** `trust_env=False` is passed to that session

#### Scenario: SOCKS5 proxy is active — WebSocket session connects directly when not opted in

- **GIVEN** a SOCKS URL is detected in the environment
- **AND** `upstream_websocket_trust_env` is not set to `True`
- **WHEN** the shared outbound WebSocket client is initialised
- **THEN** the WebSocket session uses a plain `TCPConnector` (unchanged behaviour)

#### Scenario: No SOCKS proxy configured — behaviour is identical to before

- **GIVEN** no SOCKS URL is present in any proxy environment variable
- **WHEN** the shared outbound HTTP client is initialised
- **THEN** both sessions use `aiohttp.TCPConnector` as before
- **AND** `trust_env` is passed unchanged per existing settings

### Requirement: SOCKS proxy URL detection follows a defined env var precedence

The service MUST probe the following environment variables in order and return the
first value that carries a SOCKS scheme:

1. `SOCKS_PROXY`
2. `socks_proxy`
3. `ALL_PROXY`
4. `HTTPS_PROXY`
5. `HTTP_PROXY`
6. `all_proxy`
7. `https_proxy`
8. `http_proxy`

Accepted input schemes: `socks5://`, `socks5h://`, `socks4://`, `socks4a://`.

Additional normalisation rules:
- Values MUST be stripped of leading/trailing whitespace before inspection.
- A bare `http://` scheme in `SOCKS_PROXY` or `socks_proxy` MUST be normalised
  to `socks5://` (accommodates misconfigured env vars while keeping the URL
  parseable by the configured proxy connector).
- `socks5h://` and `socks4a://` values MUST be normalised to `socks5://` and
  `socks4://` before connector construction because the configured proxy parser
  rejects the extended schemes.
- `HTTP_PROXY` and `http_proxy` MUST be skipped when `REQUEST_METHOD` is set in
  the environment (httpoxy / CGI security convention).

#### Scenario: Whitespace-padded value is accepted and returned stripped

- **GIVEN** `SOCKS_PROXY="  socks5://gateway:1080  "`
- **WHEN** the SOCKS URL is resolved
- **THEN** the returned URL is `socks5://gateway:1080` (no surrounding whitespace)

#### Scenario: Bare `http://` scheme in `SOCKS_PROXY` is normalised

- **GIVEN** `socks_proxy=http://gateway:1080`
- **WHEN** the SOCKS URL is resolved
- **THEN** the returned URL is `socks5://gateway:1080`

#### Scenario: Extended SOCKS schemes are normalised before connector use

- **GIVEN** `SOCKS_PROXY=socks5h://gateway:1080`
- **WHEN** the SOCKS URL is resolved
- **THEN** the returned URL is `socks5://gateway:1080`

#### Scenario: CGI environment skips `HTTP_PROXY`

- **GIVEN** `REQUEST_METHOD=GET` is set
- **AND** `HTTP_PROXY=socks5://gateway:1080` is the only SOCKS var
- **WHEN** the SOCKS URL is resolved
- **THEN** the result is `None` (variable is ignored)

