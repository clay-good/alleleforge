# model-zoo (delta)

## MODIFIED Requirements

### Requirement: Uncached artifacts require consent, a pinned hash, and a source

`ModelRegistry.checkpoint` SHALL, when the artifact is not cached, require `consent=True`
(`ConsentError`), a pinned `checkpoint_sha256` (`ChecksumError`), and a `source_url`, and
SHALL stream-hash downloaded bytes and reject a mismatch. It SHALL ALSO verify an
**already-cached** artifact against its pinned hash on every load, not only on download,
so a tampered or truncated cache entry cannot pass silently.

#### Scenario: Tampered cache entry
- **WHEN** a cached checkpoint's bytes no longer match the pinned `checkpoint_sha256`
- **THEN** loading it raises `ChecksumError`

#### Scenario: No consent
- **WHEN** an uncached checkpoint is requested without consent
- **THEN** it raises `ConsentError` naming the source URL

### Requirement: Every model carries a complete, validated card

Loading any model SHALL require a validated `ModelCard` with the fields `name`,
`version`, `chemistry`, `training_data`, `intended_use`, `out_of_scope_use`, `license`,
`citation`, and `known_failure_modes` (now required, so every model's safety-audit
surface is complete). A missing file or non-mapping YAML SHALL raise `CardError`; a card
missing any required field SHALL be rejected.

#### Scenario: Card without failure modes
- **WHEN** a card omits `known_failure_modes`
- **THEN** card validation rejects it
