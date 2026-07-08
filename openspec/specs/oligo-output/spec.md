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

### Requirement: Inserts are screened for the cloning enzyme's recognition site

Every emitted insert sequence — the sgRNA spacer, the pegRNA spacer, and the pegRNA 3'
extension (RTT + PBS + motif) — SHALL be screened on **both strands** against its scheme's
Type IIS recognition site (BsmBI `CGTCTC`, BbsI `GAAGAC`, BsaI `GGTCTC`). On a match the
oligo builder SHALL attach a prominent `internal-<enzyme>-site` flag naming the component,
strand, and position, so an insert the cloning enzyme would cut internally is never shipped
as a clean, round-trip-valid deliverable.

#### Scenario: Spacer contains the enzyme site
- **WHEN** a spacer or extension contains the scheme's Type IIS recognition site on either
  strand
- **THEN** the oligo set carries an `internal-<enzyme>-site` flag naming the position — never
  emitted as clean

#### Scenario: Clean insert
- **WHEN** no insert contains the scheme's recognition site
- **THEN** the oligo set is emitted with no site flag

### Requirement: Renders state the oligo preparation prerequisite

Every oligo render SHALL state the annealing/phosphorylation prerequisite for the chosen
cloning scheme — whether the annealed oligos require 5' phosphorylation (T4 PNK) or a
dephosphorylated vector for the ligation to close — so a scientist does not set up a
ligation that cannot ligate.

#### Scenario: Phosphorylation note present
- **WHEN** an oligo set is rendered
- **THEN** the render states the phosphorylation/annealing requirement for its scheme

### Requirement: Duplex construction follows the declared cloning scheme

The sense sgRNA oligo SHALL be `top_overhang + [G] + spacer` and the antisense SHALL be
`bottom_overhang + revcomp([G] + spacer)`, where the transcription-start `G` is prepended
**only when the spacer does not already begin with `G`** — never doubled onto a G-initial
spacer — and the oligo set SHALL record whether a `G` was added. The pegRNA 3' extension
SHALL be assembled 5'→3' as `RTT + PBS + motif` with its scheme's overhangs. Reconstruction
SHALL reject a missing overhang, an incorrect transcription-start `G` (missing when the set
records one was added, or doubled), a wrong reverse complement, or a missing declared motif.

#### Scenario: Wrong antisense
- **WHEN** the antisense oligo is not the exact reverse complement of the sense body
- **THEN** reconstruction raises `ValueError`

#### Scenario: G-initial spacer is not double-G'd
- **WHEN** a spacer already begins with `G` and `prepend_g` is set
- **THEN** no second `G` is added, the emitted guide length is unchanged, and the oligo set
  records that no `G` was added

#### Scenario: Missing motif
- **WHEN** the declared 3' motif is absent from the extension oligo
- **THEN** reconstruction raises `ValueError`

### Requirement: Cloning schemes and motifs are named and cited

Cloning schemes, 3' epegRNA motifs, and the pegRNA 3'-extension overhangs SHALL be drawn
from named, parameterized, citation-bearing tables — the extension's distal overhang SHALL
NOT be a bare uncited constant — and a scheme's documented overhangs SHALL match the
constants the builder emits (docstring and code in agreement). A PE3/PE3b nicking guide,
when present, SHALL be emitted as a standard sgRNA duplex.

#### Scenario: Extension overhang is cited and consistent
- **WHEN** the pegRNA 3'-extension oligos are built
- **THEN** their overhangs come from the named, cited scheme, and the emitted constants match
  the scheme's documented acceptor overhangs

#### Scenario: PE3b nicking guide
- **WHEN** a candidate carries a PE3b nicking guide
- **THEN** the oligo set includes a separate nicking-guide duplex

### Requirement: Reagent-free candidates yield no oligos

`oligos_for` SHALL dispatch by chemistry and return nothing for a candidate that needs no
synthesized reagent.

#### Scenario: No reagent
- **WHEN** a candidate requires no synthesized oligo
- **THEN** `oligos_for` returns nothing rather than a spurious empty duplex
