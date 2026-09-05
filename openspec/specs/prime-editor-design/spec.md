# prime-editor-design Specification

## Purpose

Enumerate every geometrically valid pegRNA that installs a variant's edit and score each
for editing efficiency and intended-vs-byproduct outcome, including the optional PE3/PE3b
nicking guide and epegRNA 3' motif. Prime editing is the flagship coverage gap.

## Requirements

### Requirement: pegRNA geometry is validated at construction

A `PegRNA` SHALL enforce its geometry at construction: PBS length in 8–17, RTT length in
7–34, and the RTT 3' homology at least 5 nt and no longer than the RTT, so a malformed
design is rejected up front rather than deep in scoring.

#### Scenario: Out-of-range PBS
- **WHEN** a pegRNA is constructed with a PBS length outside 8–17
- **THEN** construction raises a validation error

### Requirement: Enumeration places the nick 5' of the edit within reach

For each candidate PAM the nick SHALL sit 3 bp 5' of the PAM and the edit SHALL lie 3' of
the nick; the PBS SHALL be enumerated over its length range (skipping lengths that run off
the window), and the RTT SHALL encode the edited allele plus at least 5 nt 3' homology and
not run past the template. The RT template SHALL be **variable-length** — 5' homology from
the nick to the edit, then the whole desired allele, then the 3' homology — so a
substitution, MNV, insertion, deletion, or delins is templated by the same path, a deleted
span consuming no template length. Every synthesized span (spacer, PBS, and RTT) SHALL be
concrete A/C/G/T; a pegRNA whose RTT window covers a reference `N` (assembly gap) SHALL be
skipped, consistent with the cas9/base-editor enumerators. Results SHALL be
deterministically sorted.

#### Scenario: No reachable nick
- **WHEN** no PAM places a nick 5' of the edit within RT reach
- **THEN** enumeration returns empty

#### Scenario: RTT spans an assembly gap
- **WHEN** a pegRNA's RT template window reaches a reference `N` (an assembly gap)
- **THEN** that pegRNA is skipped (its RTT would be an unsynthesizable oligo templating an
  ambiguous base into the genome), while shorter RTTs that stop before the gap still resolve

#### Scenario: Multi-base edit
- **WHEN** an insertion, deletion, MNV, or delins within the supported size is enumerated
- **THEN** pegRNAs are emitted on both strands, and each one's reverse-transcribed product
  reconstructs exactly the intended edited genome at the locus its PBS anneals to

#### Scenario: Deleted span costs no template
- **WHEN** a deletion is templated
- **THEN** the RTT length is independent of the deleted span's length (it carries only the
  5' and 3' homology), so a large deletion is templatable inside `RTT_RANGE`

#### Scenario: Deterministic order
- **WHEN** multiple pegRNAs are enumerated
- **THEN** they are returned sorted by `(nick_site, PBS length, RTT length)`

### Requirement: PE3b nicking guides are preferred

A default pegRNA SHALL attach a tevopreQ1 epegRNA 3' motif; when a nicking guide is
requested, a seed-disrupting PE3b guide SHALL be preferred over an in-range PE3 guide, and
a candidate with no available nicking guide SHALL be flagged accordingly. A guide SHALL be
classified PE3b only when the edit falls in the nicking guide's **PAM-proximal seed** —
measured from the PAM-proximal protospacer end (for a frame-minus guide,
`edit - protospacer_start < seed_length`), the region whose disruption actually prevents
the guide from nicking the edited strand — never from the PAM-distal end.

#### Scenario: PE3b available
- **WHEN** a seed-disrupting nicking guide spanning the edit exists
- **THEN** it is chosen over a plain PE3 guide

#### Scenario: Edit in the PAM-proximal seed
- **WHEN** the edit lies within the nicking guide's PAM-proximal seed and changes the base
- **THEN** the guide is classified PE3b and preferred

#### Scenario: Edit in the PAM-distal region only
- **WHEN** the edit lies in the protospacer but outside the PAM-proximal seed
- **THEN** the guide is NOT classified PE3b, so the `pe3b` label never advertises
  seed disruption that does not hold

### Requirement: Efficiency and outcome honor the uncertainty contract

The default heuristic efficiency scorer SHALL return a calibrated `Prediction[float]` and
SHALL flag `in_distribution = False` for a cell context outside its supported set; the
outcome predictor SHALL return a normalized intended-vs-byproduct `EditOutcome` with a
calibrated intended-probability. The real PRIDICT2.0 path SHALL be sequence-level,
consent/license-gated, and opt-in.

#### Scenario: Unsupported cell context
- **WHEN** the cell context is outside the supported set (e.g. not HEK293T/K562)
- **THEN** the efficiency prediction is flagged out-of-distribution

#### Scenario: PRIDICT without consent
- **WHEN** the PRIDICT2.0 engine is invoked without consent
- **THEN** weight resolution raises before any external process runs

### Requirement: Enumeration coverage is stated honestly

Routing SHALL advertise prime editing only for edit classes that enumeration can produce (a
feasibility check), and SHALL state a specific reason when it declines an edit it cannot
enumerate — not a generic "no actionable candidate" note. The supported edit classes SHALL
be documented. Two bounds SHALL be enforced identically by routing and enumeration: the
reference span an edit replaces SHALL be at most `PRIME_MAX_EDIT`, and the allele the RT
template must **write** (the desired allele, which depends on the intent) SHALL be at most
`PRIME_MAX_TEMPLATED_EDIT` — the `RTT_RANGE` ceiling less the minimum 3' homology.

#### Scenario: Routed but unenumerable edit
- **WHEN** an edit routes to prime but no pegRNA can be enumerated for its class
- **THEN** the menu records an explicit "eligible but no actionable candidate" note

#### Scenario: Small indel
- **WHEN** an insertion, deletion, or delins within both bounds is requested
- **THEN** routing admits prime and enumeration produces valid pegRNAs

#### Scenario: Allele too long to template
- **WHEN** the desired allele is longer than `PRIME_MAX_TEMPLATED_EDIT`
- **THEN** routing declines prime and enumeration returns empty — never a truncated RT
  template — while the opposite intent on the same variant, which writes a short allele,
  remains eligible

#### Scenario: No-op edit
- **WHEN** the start allele and the desired allele are identical
- **THEN** enumeration returns empty

### Requirement: Placements are reference footprints, never loci of convenience

Enumeration runs over the genome the target actually carries (the reference window with the
start allele substituted in), whose coordinates drift from the reference past a
length-changing edit. Every emitted placement and nick site SHALL be expressed in reference
coordinates as the footprint the reagent's bases derive from: exact for a span that does not
cross the edit, wider for one spanning a deletion, narrower for one spanning an insertion. A
protospacer lying wholly inside carried bases the reference does not contain has no
reference locus and SHALL be reported without a placement (pegRNA) or dropped (nicking
guide), rather than assigned a locus it does not occupy.

#### Scenario: Protospacer 5' of the edit
- **WHEN** a pegRNA's protospacer does not cross the edit
- **THEN** fetching its placement from the reference returns the protospacer verbatim

#### Scenario: Protospacer spanning a corrected deletion
- **WHEN** a protospacer spans an edit whose carried allele is shorter than the reference
  span it replaces
- **THEN** its placement is wider than the protospacer by exactly the missing bases

#### Scenario: On-target exclusion across a length-changing edit
- **WHEN** a pegRNA whose protospacer does not cross the edit is scanned for
  off-targets with its placement supplied
- **THEN** the guide's own locus is dropped from the report — on both strands, and
  regardless of whether the edit changed the sequence's length

#### Scenario: Nicking guide with no reference locus
- **WHEN** a candidate nicking-guide protospacer lies wholly inside carried inserted bases
- **THEN** it is not emitted, and no emitted nicking guide has a zero-width placement

### Requirement: A geometry-only efficiency score says what it cannot see

The default prime-efficiency scorer is a geometry prior: its features are PBS/RTT
length, nick-to-edit distance, PBS GC, and the epegRNA motif — there is no edit-size
or edit-class term. When it scores an edit that writes other than a single base, the
prediction SHALL carry an explicit note saying the score does not reflect the edit's
size, the model card SHALL record the limitation as a known failure mode, and the
candidate SHALL carry an inspectable flag naming how many bases the RT template
writes.

#### Scenario: Multi-base edit scored by the geometry prior
- **WHEN** the default scorer scores a pegRNA whose RT template writes other than one
  base
- **THEN** the returned prediction carries the edit-size-blind note, and a single-base
  edit's prediction does not

#### Scenario: Menu shows what a candidate writes
- **WHEN** a prime candidate installs an edit of other than one base
- **THEN** its flags name the templated length

### Requirement: A pegRNA records the geometry its scorers consume

A `PegRNA` SHALL record both RT-template homology arms — the 5' arm between the
nick and the edit (the nick-to-edit distance) and the 3' arm past it — so the
templated allele's length is recoverable rather than inferred. Consumers that need
the nick-to-edit distance SHALL read the recorded arm; deriving it from the RTT
length assumes a one-base edit and silently absorbs the templated allele into the
distance. The arms SHALL NOT together exceed the RTT length.

#### Scenario: Multi-base edit scored on its real distance
- **WHEN** two pegRNAs share an RTT length and 3' homology but template alleles of
  different lengths
- **THEN** the one whose nick is nearer its edit scores the higher efficiency

#### Scenario: Homology arms outrunning the template
- **WHEN** a pegRNA is constructed whose 5' and 3' homology arms together exceed
  its RTT length
- **THEN** construction raises a validation error

### Requirement: PE3b classification survives a length-changing edit

A nicking guide SHALL be classified PE3b only when the edit genuinely disrupts its
PAM-proximal seed, judged by comparing the seed window in the start and edited genomes, and
only where the two genomes share their indexing (the protospacer's PAM-proximal boundary at
or 5' of the edit). A PE3b guide's spacer SHALL be templated from the edited genome; any
other nicking guide's from the start genome.

#### Scenario: Indel in the ngRNA seed
- **WHEN** an insertion or deletion falls inside a candidate ngRNA's PAM-proximal seed
- **THEN** the guide is classified PE3b and its spacer matches the edited strand

#### Scenario: Edit past the shared indexing
- **WHEN** a candidate ngRNA's protospacer begins 3' of the edit, where a length-changing
  edit has shifted the two genomes apart
- **THEN** it is not classified PE3b and its spacer is templated from the start genome

### Requirement: Pol-III transcription constraints are enforced and inspectable

pegRNA enumeration SHALL apply Pol-III (U6) transcription constraints — reject spacers
containing a `TTTT` terminator, enforce or annotate the 5'-G transcription start, and
apply a spacer-GC band — and SHALL expose each rejection as a stated reason rather than a
silent omission.

#### Scenario: Terminator in the spacer
- **WHEN** a candidate spacer contains a `TTTT` Pol-III terminator
- **THEN** it is rejected with a stated reason

### Requirement: Chromatin-aware efficiency is opt-in and honesty-preserving

`design_prime` SHALL support an optional **open-chromatin (ePRIDICT-style) efficiency
adjustment** driven by ENCODE tracks. When the caller supplies both an `EncodeTracks` source
and a track name, the design path SHALL score each pegRNA with the chromatin context of its
own edit locus (the pegRNA placement interval), so a variant in open chromatin is predicted
to edit more efficiently than one in closed chromatin. The `PrimeEfficiencyScorer` protocol
SHALL expose the `chromatin` parameter so the adjustment is reachable through the design path,
not only by calling a scorer directly.

The adjustment SHALL be opt-in and SHALL NOT weaken any honesty guarantee:

- When no tracks are supplied, the efficiency SHALL be the pure pegRNA-geometry baseline —
  byte-identical to the pre-wiring default, so no existing caller's output changes.
- The adjustment SHALL only scale the efficiency **point estimate**; it SHALL NOT flip the
  `in_distribution` flag or assert calibration the scorer has not earned. An out-of-distribution
  cell context SHALL remain out-of-distribution after a chromatin adjustment.
- A locus with **no track coverage** (signal 0) SHALL be a no-op (the unadjusted value), never a
  penalty for missing data.
- A requested track name that the `EncodeTracks` object does not carry SHALL **fail closed**
  (raise), rather than silently applying no adjustment and misleading the caller into believing
  the efficiency was chromatin-adjusted.
- A candidate whose efficiency was chromatin-adjusted SHALL record that fact in its rationale, so
  the researcher can distinguish a chromatin-adjusted efficiency from a pure-geometry one.

#### Scenario: Opt-in — no tracks leaves the baseline unchanged
- **WHEN** `design_prime` is called without `encode_tracks`
- **THEN** every candidate's efficiency is the pure pegRNA-geometry baseline, identical to the
  output before chromatin wiring existed

#### Scenario: Open chromatin raises the predicted efficiency
- **WHEN** `design_prime` is called with an `EncodeTracks` source and a track name, and the
  pegRNA's edit locus has positive accessibility signal
- **THEN** the candidate's efficiency point estimate is higher than the pure-geometry baseline,
  and its rationale records that the efficiency was chromatin-adjusted

#### Scenario: Chromatin adjustment does not launder an OOD prediction
- **WHEN** the cell context is out-of-distribution and a chromatin adjustment is applied
- **THEN** the efficiency prediction remains flagged `in_distribution = False`

#### Scenario: Uncovered locus is a no-op
- **WHEN** the requested track has no coverage over the pegRNA's edit locus
- **THEN** the efficiency equals the unadjusted geometry baseline (no penalty for missing signal)

#### Scenario: Unknown track fails closed
- **WHEN** the requested track name is not present in the supplied `EncodeTracks`
- **THEN** the design raises rather than silently returning an unadjusted efficiency labeled as
  chromatin-aware

### Requirement: A PE3 candidate states where its second nick is

The nick-to-nick distance is the PE3 design parameter: two PE3 candidates otherwise
differ in nothing, and two opposite-strand nicks placed close together amount to a
staggered double-strand break — the outcome prime editing is chosen to avoid. Every PE3
candidate SHALL carry its signed nick offset in its flags and on its reagent line, and a
nick closer than the close-nick floor SHALL be annotated.

The distance SHALL NOT enter the composite ranking score. Scoring it requires a byproduct
model calibrated against real PE3 data, which the project does not have; a fabricated
weight would make the composite appear better informed than it is.

#### Scenario: Two PE3 candidates
- **WHEN** a menu contains PE3 candidates with different nicking guides
- **THEN** each states its own signed nick offset, so they are distinguishable

#### Scenario: A nick close enough to act as a double-strand break
- **WHEN** the second nick is closer to the pegRNA nick than the close-nick floor
- **THEN** the candidate is annotated `close-nick`, without its rank being altered

### Requirement: A chromatin track that adjusts nothing is reported as such

Recording a chromatin track in provenance asserts that the run was chromatin-aware.
Whether the track covered any candidate locus is a separate fact, and it is the one that
determines whether the efficiencies differ from the unadjusted estimates. A candidate the
track actually moved SHALL be flagged, and a menu whose supplied track moved none SHALL
say so.

#### Scenario: A track covering another locus
- **WHEN** a chromatin track is supplied that covers none of the candidate loci
- **THEN** the menu states that every efficiency is the unadjusted estimate, and no
  candidate is flagged as chromatin-adjusted

#### Scenario: A covering track
- **WHEN** the track covers the candidates
- **THEN** they are flagged and no such statement is made
