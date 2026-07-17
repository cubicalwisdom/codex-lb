# Design

## Decision

CodexNeo will apply the same duration-aware history normalization already used by the main Accounts mapper. A history row whose duration matches the configured weekly window is a weekly candidate even when its storage slot is named `primary`. When both `primary` and `secondary` contain weekly-duration rows, the normalizer selects the fresher candidate using the existing shared comparison policy.

## Compatibility

True short-window rows remain primary/5h. True weekly rows remain secondary/Weekly. Weekly-only accounts expose `primary=null` and the current weekly value in `secondary`. No stored history is rewritten.
