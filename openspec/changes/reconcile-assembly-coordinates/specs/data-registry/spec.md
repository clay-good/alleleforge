## ADDED Requirements

### Requirement: Database parsers record each record's native assembly

ClinVar, dbSNP, and other assembly-bound parsers SHALL record the native assembly of each
parsed record rather than inheriting a default build silently. The recorded assembly SHALL
be available to variant resolution so a requested build can be reconciled against — not
overwritten onto — the source data.

#### Scenario: Parsed record carries its assembly
- **WHEN** a ClinVar or dbSNP release is parsed
- **THEN** each resulting variant carries the release's native assembly, not an unexamined
  default

#### Scenario: Assembly absent from the source
- **WHEN** the source data does not state its assembly
- **THEN** the parser records the assembly as unknown rather than assuming the default
  build, so downstream resolution can require the caller to disambiguate
