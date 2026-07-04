# oligo-output (delta)

## MODIFIED Requirements

### Requirement: Every oligo set round-trips

Each oligo set SHALL be reconstructable back to its inputs at construction, and reverse
complementation SHALL validate its input against the `ACGTN` DNA alphabet, raising on any
other character (RNA `U`, IUPAC ambiguity codes, whitespace) so a mis-complemented oligo
can never be emitted. An sgRNA set recovers its spacer; a pegRNA set recovers its spacer,
RTT, and PBS; construction calls the reconstruction and fails fast on any mismatch.

#### Scenario: Non-DNA character
- **WHEN** an oligo input contains a character outside `ACGTN` (e.g. `U` or an IUPAC code)
- **THEN** construction raises with a clear message and no oligo is produced

#### Scenario: Round-trip on build
- **WHEN** an oligo set is constructed from valid DNA
- **THEN** it reconstructs its source sequences or raises `ValueError`

## ADDED Requirements

### Requirement: The cloning scaffold is verified

The pegRNA/sgRNA scaffold carried in an oligo set SHALL be verified against the expected
constant for the chosen cloning scheme, so a wrong or empty scaffold is caught at
construction rather than silently shipped in the deliverable.

#### Scenario: Wrong scaffold
- **WHEN** an oligo set is built with a scaffold that does not match its scheme's constant
- **THEN** construction raises
