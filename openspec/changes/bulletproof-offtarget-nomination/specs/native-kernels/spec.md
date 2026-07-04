# native-kernels (delta)

## ADDED Requirements

### Requirement: Linear and native paths agree on dirty input

The pure-Python linear scan and the FM-index/native path SHALL handle non-`ACGTN` input
identically — both skipping it, or both rejecting it with the same error — so a region
containing unexpected characters cannot produce different results depending on which path
ran. Parity SHALL be exercised at genome scale, including low-complexity poly-N and poly-A
runs.

#### Scenario: Non-ACGTN region
- **WHEN** a region contains a base outside `ACGTN`
- **THEN** the linear and FM/native paths produce the same outcome (both skip or both
  raise), not a crash on one path and a silent skip on the other

#### Scenario: Genome-scale parity
- **WHEN** a multi-megabase reference with poly-N/poly-A runs is searched
- **THEN** the FM/native hits are byte-identical to the linear-scan hits
