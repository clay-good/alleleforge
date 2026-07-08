## ADDED Requirements

### Requirement: Inserts are screened for the cloning enzyme's recognition site

Every emitted insert sequence — the sgRNA spacer, the pegRNA spacer, and the pegRNA 3'
extension (RTT + PBS + motif) — SHALL be screened on **both strands** against its scheme's
Type IIS recognition site (e.g. BsmBI `CGTCTC`, BbsI `GAAGAC`, BsaI `GGTCTC`). On a match the
oligo builder SHALL either refuse to emit the oligo set with a clear error or attach a
prominent `internal-<enzyme>-site` flag naming the position, so an insert the cloning enzyme
would cut internally is never shipped as a clean, round-trip-valid deliverable.

#### Scenario: Spacer contains the enzyme site
- **WHEN** a spacer or extension contains the scheme's Type IIS recognition site on either
  strand
- **THEN** the oligo set is refused with a clear error or carries an `internal-<enzyme>-site`
  flag naming the position — never emitted as clean

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

## MODIFIED Requirements

### Requirement: Duplex construction follows the declared cloning scheme

The sense sgRNA oligo SHALL be `top_overhang + [G] + spacer` and the antisense SHALL be
`bottom_overhang + revcomp([G] + spacer)`, where the transcription-start `G` is prepended
**only when the spacer does not already begin with `G`** — never doubled onto a G-initial
spacer — and the oligo set SHALL record whether a `G` was added. The pegRNA 3' extension SHALL
be assembled 5'→3' as `RTT + PBS + motif` with its scheme's overhangs. Reconstruction SHALL
reject a missing overhang, an incorrect transcription-start `G` (missing when required, or
doubled), a wrong reverse complement, or a missing declared motif.

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

Cloning schemes, 3' epegRNA motifs, and the pegRNA 3'-extension overhangs SHALL be drawn from
named, parameterized, citation-bearing tables — the extension's distal overhang SHALL NOT be a
bare uncited constant — and a scheme's documented overhangs SHALL match the constants the
builder emits (docstring and code in agreement). A PE3/PE3b nicking guide, when present, SHALL
be emitted as a standard sgRNA duplex.

#### Scenario: Extension overhang is cited and consistent
- **WHEN** the pegRNA 3'-extension oligos are built
- **THEN** their overhangs come from the named, cited scheme, and the emitted constants match
  the scheme's documented acceptor overhangs

#### Scenario: PE3b nicking guide
- **WHEN** a candidate carries a PE3b nicking guide
- **THEN** the oligo set includes a separate nicking-guide duplex
