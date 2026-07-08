# data-registry (delta)

## MODIFIED Requirements

### Requirement: External datasets are consent- and checksum-gated

`DatasetRegistry.resolve` SHALL raise `ConsentError` for an uncached dataset without
`consent=True`, `ChecksumError` when the descriptor's `sha256` is `None`, and
`ConsentError` when `source_url` is `None`; downloaded bytes SHALL be SHA-256 verified.
When the descriptor pins a `sha256`, `resolve` SHALL ALSO re-verify an already-cached
artifact against it on every load, so a corrupted or tampered cached dataset cannot be
served. An unregistered name SHALL raise `KeyError`.

#### Scenario: Tampered cached dataset
- **WHEN** a cached dataset's bytes no longer match the pinned `sha256`
- **THEN** `resolve` raises `ChecksumError` rather than returning the stale file

#### Scenario: Uncached dataset without consent
- **WHEN** `resolve` is called for an uncached dataset without consent
- **THEN** it raises `ConsentError`
