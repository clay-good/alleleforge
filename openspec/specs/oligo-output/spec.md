# oligo-output Specification

## Purpose

Turn a scored candidate into the exact annealed oligo duplexes a bench scientist orders
for cloning, with a round-trip reconstruction invariant enforced at construction. This is
a real wet-lab deliverable: a wrong oligo wastes reagents and experiments, so correctness
is safety-critical.

## Requirements

### Requirement: Every oligo set round-trips

Each oligo set SHALL be reconstructable back to its inputs at construction: an sgRNA set
recovers its spacer, a pegRNA set recovers its spacer, RTT, and PBS; construction SHALL
call the reconstruction and fail fast on any mismatch.

#### Scenario: Round-trip on build
- **WHEN** an oligo set is constructed
- **THEN** it reconstructs its source sequences or raises `ValueError`

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
