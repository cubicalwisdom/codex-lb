# anthropic-structured-tool-results Specification

## Purpose
TBD - created by archiving change support-anthropic-structured-tool-results. Update Purpose after archive.
## Requirements
### Requirement: Complete Claude ToolSearch history uses the native Responses lifecycle

The Anthropic Messages facade MUST recognize a complete history pair consisting of an assistant `tool_use` named `ToolSearch` and its matching user `tool_result` whose content is a non-empty array containing only valid `tool_reference` blocks. It MUST translate that pair to matching Responses `tool_search_call` and `tool_search_output` input items. The output MUST contain the referenced converted function definitions in first-reference order, MUST remove duplicate references without reordering the remaining tools, and MUST retain the original call identifier.

#### Scenario: Claude loads one deferred workspace tool

- **WHEN** an assistant `ToolSearch` call is followed by a matching result containing one `tool_reference`
- **THEN** the forwarded input contains one `tool_search_call` followed by one `tool_search_output`
- **AND** the output contains the converted definition for the referenced tool

#### Scenario: Historical ToolSearch remains in a later conversation

- **WHEN** a later Claude Desktop request includes a previously completed ToolSearch pair before a new user turn
- **THEN** the adapter translates the historical pair without returning the text-only tool-result 400
- **AND** the new turn reaches the existing Responses execution path

### Requirement: Tool references are validated without silent loss

Every `tool_reference` MUST contain a non-empty `tool_name`. A reference used in a native ToolSearch output MUST resolve to an ordinary function tool supplied in the same request. A malformed or unresolved native reference MUST return an Anthropic `invalid_request_error` before upstream execution. The facade MUST NOT silently discard a valid reference or replace it with an empty result.

#### Scenario: ToolSearch references an unavailable tool

- **WHEN** a reference-only ToolSearch result names no matching function definition
- **THEN** the facade returns an Anthropic `invalid_request_error`
- **AND** it does not forward an incomplete native tool-search pair

### Requirement: Documented references outside complete ToolSearch pairs remain paired

When a valid `tool_reference` appears in a non-ToolSearch result or in mixed text/reference result content, the facade MUST preserve the complete ordered content array as deterministic compact JSON inside the matching Responses `function_call_output`. It MUST NOT move that content into system instructions, a separate user message, or an unmatched output item. Unrelated unsupported nested content types MUST retain explicit local rejection.

#### Scenario: A custom catalog tool returns a reference

- **WHEN** an ordinary client tool returns a valid `tool_reference`
- **THEN** its matching `function_call_output` contains the canonical serialized result
- **AND** the call identifier remains unchanged

### Requirement: Existing text tool-result behavior remains stable

String `tool_result` content MUST remain the same output string. An array containing only text blocks MUST continue to concatenate the text values in order without adding separators or metadata.

#### Scenario: Existing ordinary tool result is replayed

- **WHEN** a tool result contains a string or only text blocks
- **THEN** its `function_call_output` is identical to the pre-change conversion

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
