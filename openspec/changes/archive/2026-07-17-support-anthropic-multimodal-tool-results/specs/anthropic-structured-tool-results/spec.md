## ADDED Requirements

### Requirement: Documented multimodal client tool results remain paired and ordered

The Anthropic Messages facade MUST accept valid `image`, `document`, and `search_result` blocks nested in a client `tool_result`. It MUST keep every converted block inside the matching Responses `function_call_output`, retain the mapped call identifier, and preserve content order. It MUST NOT promote result content into instructions or an ordinary user message.

#### Scenario: A client tool returns text around a screenshot

- **WHEN** a tool result contains text, a valid image, and more text
- **THEN** the matching function output contains ordered `input_text`, `input_image`, and `input_text` items
- **AND** no separate user message is synthesized for the screenshot

### Requirement: Tool-result documents use bounded local extraction

A valid base64 PDF, UTF-8 plain-text, or UTF-8 CSV document returned by a client tool MUST reuse the facade's existing media, size, page, content-stream, encoding, encryption, and extracted-text limits. A document using Anthropic's inline `source.type: text` form MUST be accepted when its media type is `text/plain` and its non-empty text is within the extracted-text limit. The extracted labelled text MUST remain inside the matching function output. Document URLs, OCR, and hosted uploads MUST remain unsupported.

#### Scenario: A tool returns an inline PDF

- **WHEN** a tool result contains a valid text-bearing base64 PDF document
- **THEN** the matching function output contains the bounded labelled page text
- **AND** the facade does not fetch or upload the document

#### Scenario: A tool returns Anthropic inline text document content

- **WHEN** a tool result document has `source.type` equal to `text`, media type `text/plain`, and bounded non-empty data
- **THEN** the matching function output contains that labelled text

### Requirement: Client search results are validated without hosted-search fabrication

Every nested `search_result` MUST contain non-empty `source` and `title` strings and a non-empty array containing only non-empty text blocks. The facade MUST preserve the ordered result and supplied metadata as deterministic compact JSON text inside the matching function output. It MUST NOT fabricate a hosted web-search call, server-tool result, or citation annotation.

#### Scenario: A knowledge-base tool returns a cited search result

- **WHEN** a valid search result includes source, title, text content, and citation configuration
- **THEN** its canonical representation remains inside the matching function output
- **AND** no hosted search lifecycle item is added

### Requirement: Multimodal tool-result validation fails closed

Malformed documented blocks and unrelated nested block types MUST return an Anthropic `invalid_request_error` with a nested parameter path before upstream execution. Existing string, empty, text-only, and `tool_reference` behavior MUST remain unchanged.

#### Scenario: A tool returns an unsupported nested block

- **WHEN** a tool result contains a block outside the documented supported families and `tool_reference`
- **THEN** the facade returns a local Anthropic validation error
- **AND** the Responses execution path is not invoked

### Requirement: Historical capacity recovery handles result images

When response-create recovery slims historical inline images, it MUST also replace inline `input_image` items nested inside historical function output arrays with the existing omission notice. It MUST retain images in the protected recent suffix.

#### Scenario: An old tool screenshot contributes to capacity pressure

- **WHEN** a recoverable response-create retry inspects a historical function output containing an inline image
- **THEN** the retry candidate replaces that image with the omission notice
- **AND** the matching function output and call identifier remain present
