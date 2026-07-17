## ADDED Requirements

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
