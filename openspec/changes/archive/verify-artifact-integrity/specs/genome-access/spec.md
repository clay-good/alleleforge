# genome-access (delta)

## MODIFIED Requirements

### Requirement: Reference downloads are consent- and checksum-gated

`from_build` SHALL refuse to download an uncached build unless `consent=True`
(`ConsentError`) and SHALL refuse any build whose pinned `sha256` is `None`
(`ChecksumError`); a downloaded artifact SHALL be SHA-256 verified before use. When a
build pins a `sha256`, an already-cached reference FASTA SHALL ALSO be re-verified against
it on load, and the FM-index cache SHALL expose an on-demand integrity check, so a
corrupted or externally-modified cached genome or index cannot be trusted silently.

#### Scenario: Tampered cached reference
- **WHEN** a cached reference FASTA no longer matches its build's pinned `sha256`
- **THEN** loading it raises `ChecksumError`

#### Scenario: No consent
- **WHEN** `from_build` is asked to fetch an uncached build without consent
- **THEN** it raises `ConsentError`
