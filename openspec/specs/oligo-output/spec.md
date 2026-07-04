# oligo-output Specification

## Purpose

Turn a scored candidate into the exact annealed oligo duplexes a bench scientist orders
for cloning, with a round-trip reconstruction invariant enforced at construction. This is
a real wet-lab deliverable: a wrong oligo wastes reagents and experiments, so correctness
is safety-critical.

## Requirements

### Requirement: Every oligo set round-trips

Each oligo set SHALL be reconstructable back to its inputs at construction, and reverse
complementation SHALL validate its input against the `ACGTN` DNA alphabet, raising on any
other character (RNA `U`, IUPAC ambiguity codes, whitespace) so a mis-complemented oligo
can never be emitted. An sgRNA set recovers its spacer; a pegRNA set recovers its spacer,
RTT, and PBS (with an RTT/PBS boundary check independent of the stored slice length);
construction calls the reconstruction and fails fast on any mismatch.

#### Scenario: Non-DNA character
- **WHEN** an oligo input contains a character outside `ACGTN` (e.g. `U` or an IUPAC code)
- **THEN** construction raises with a clear message and no oligo is produced

#### Scenario: Round-trip on build
- **WHEN** an oligo set is constructed from valid DNA
- **THEN** it reconstructs its source sequences or raises `ValueError`

### Requirement: The cloning scaffold is verified

The pegRNA/sgRNA scaffold carried in an oligo set SHALL be verified against the expected
constant for the chosen cloning scheme, so a wrong or empty scaffold is caught at
construction rather than silently shipped in the deliverable.

#### Scenario: Wrong scaffold
- **WHEN** an oligo set is built with a scaffold that does not match its scheme's constant
- **THEN** construction raises

### Requirement: Duplex construction follows the declared cloning scheme

The sense sgRNA oligo SHALL be `top_overhang + [G] + spacer` and the antisense SHALL be
`bottom_overhang + revcomp(G + spacer)`; the pegRNA 3' extension SHALL be assembled
5'→3' as `RTT + PBS + motif` with its scheme's overhangs. Reconstruction SHALL reject a
missing overhang, a missing transcription-start `G`, a wrong reverse complement, or a
missing declared motif.

#### Scenario: Wrong antisense
- **WHEN** the antisense oligo is not the exact reverse complement of the sense body
- **THEN** reconstruction raises `ValueError`

#### Scenario: Missing motif
- **WHEN** the declared 3' motif is absent from the extension oligo
- **THEN** reconstruction raises `ValueError`

### Requirement: Cloning schemes and motifs are named and cited

Cloning schemes and 3' epegRNA motifs SHALL be drawn from named, parameterized,
citation-bearing tables, and a PE3/PE3b nicking guide, when present, SHALL be emitted as
a standard sgRNA duplex.

#### Scenario: PE3b nicking guide
- **WHEN** a candidate carries a PE3b nicking guide
- **THEN** the oligo set includes a separate nicking-guide duplex

### Requirement: Reagent-free candidates yield no oligos

`oligos_for` SHALL dispatch by chemistry and return nothing for a candidate that needs no
synthesized reagent.

#### Scenario: No reagent
- **WHEN** a candidate requires no synthesized oligo
- **THEN** `oligos_for` returns nothing rather than a spurious empty duplex
