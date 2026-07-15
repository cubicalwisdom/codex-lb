## ADDED Requirements

### Requirement: Owner-forward headers cross a filtered trust boundary

Before forwarding a request to another HTTP bridge owner, the proxy MUST remove inbound forwarding, hop-by-hop, framing, cookie, and bridge-reserved headers, including names nominated by the inbound `Connection` header. It MUST retain the downstream `Authorization` value only for owner-side API-key validation, then add the authenticated internal bridge headers and signature. The forwarding client MUST allow aiohttp to generate its own JSON content headers.

#### Scenario: Spoofable bridge and hop-by-hop headers are removed

- **WHEN** an inbound request contains `Connection`, cookies, content framing, or client-supplied `x-codex-bridge-*` headers
- **THEN** those headers are absent from the owner-forward request
- **AND** the owner-forward request contains only the regenerated signed bridge headers and preserved downstream authorization
