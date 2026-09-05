# cas9-design Specification

## Purpose

For a resolved variant and intent, enumerate every PAM-anchored SpCas9 guide whose blunt
cut lands in the actionable window, then attach a calibrated on-target efficiency
interval and a predicted indel spectrum to each. Coordinates are 0-based half-open.

## Requirements

### Requirement: Guides are enumerated on both strands with a defined cut

The system SHALL enumerate 20-nt protospacers on both strands anchored to an `NGG` PAM
by default, placing the predicted blunt cut 3 bp 5' of the PAM, and SHALL keep a guide
only if its cut falls in the actionable window (the whole working interval for a knockout
intent, else a ±10 bp box around the variant).

#### Scenario: Actionable plus-strand guide
- **WHEN** a variant has a nearby plus-strand `NGG`
- **THEN** a guide is emitted with its cut 3 bp 5' of the PAM inside the actionable window

### Requirement: Guides never contain N and are deterministically ordered

A guide SHALL never contain `N` in its PAM or protospacer, its concrete PAM SHALL satisfy
the declared pattern at construction, and results SHALL be sorted deterministically by
`(cut_site, strand)`.

#### Scenario: N rejection
- **WHEN** a candidate window contains `N`
- **THEN** no guide is emitted there

### Requirement: Correction-intent guides are enumerated against the carried allele

For a CORRECT, REVERT, or INSTALL intent — where the target genome carries the alternate
allele — the Cas9 enumerator SHALL substitute the carried allele onto the local window
before enumerating protospacers and PAMs, so guides are enumerated against the sequence
the target genome actually contains, consistent with the base-editor and prime enumerators.
A PAM the alternate allele destroys SHALL NOT be emitted; a PAM the alternate allele
creates SHALL be found; and on-/off-target scoring SHALL run on the carried 20-mer.
This SHALL hold for a **length-changing** allele too: the substitution is applied
whatever the allele's length, every emitted placement and cut site is mapped back to the
reference footprint its bases derive from, a guide with no reference footprint is dropped
rather than placed on a locus it does not occupy, and the scored context is located in
the carried sequence **by content** so a coordinate shift cannot silently hand a scorer a
frame-shifted window of the wrong length.

#### Scenario: Alt allele destroys the reference PAM
- **WHEN** a CORRECT intent's alternate allele removes a PAM present in the reference
- **THEN** no guide is emitted at that PAM, because it does not exist in the target genome

#### Scenario: Alt allele creates a PAM
- **WHEN** the alternate allele creates a PAM absent from the reference
- **THEN** the corresponding guide is enumerated and scored on the carried sequence

#### Scenario: Deletion removes the reference PAM
- **WHEN** the carried allele is a deletion that removes a PAM present in the reference
- **THEN** no guide is emitted at that PAM — the same intent's `INSTALL` direction, where
  the genome still carries the reference, still emits it

#### Scenario: Deletion creates a junction PAM
- **WHEN** a carried deletion brings two bases together into a PAM the reference does not
  contain
- **THEN** the guide at that junction is enumerated, and every emitted guide's
  protospacer+PAM is present in the genome it targets

#### Scenario: Outcome context and cut index across a length change
- **WHEN** the outcome predictor is asked to score a guide near a length-changing
  carried allele
- **THEN** the context it receives is a window of the *carried* genome and the cut
  index it receives points at the same base of that window the guide's own cut site
  points at — a downstream cut shifts by the allele's length change

#### Scenario: Context shape across a length change
- **WHEN** a guide near a length-changing carried allele is scored
- **THEN** its context is the carried sequence and keeps the requested flank shape (a
  4+20+3+3 request returns 30 nt), and a placement 5' of the edit still fetches back to
  its protospacer verbatim

### Requirement: Relaxed PAMs are opt-in and labeled

Relaxed PAMs SHALL be emitted only on explicit opt-in and only as a fallback when no
`NGG` guide is actionable: `NG` (SpCas9-NG) first, then `NRN`/`NYN` (SpRY); candidates
using them SHALL carry a `relaxed-pam:<pattern>` flag.

#### Scenario: No relaxation without opt-in
- **WHEN** no `NGG` guide is actionable and relaxation is not enabled
- **THEN** the result is empty (no silent PAM relaxation)

### Requirement: Efficiency is a calibrated Prediction with honest gating

On-target efficiency SHALL be returned as a calibrated `Prediction[float]` carrying its
method, calibration flag, and in-distribution flag. The default heuristic baseline SHALL
report `method = heuristic`; the trained Rule Set 3 path SHALL be gated through the model
zoo (consent + the `cas9-rs3` extra), enforce its 30-nt context contract, and be
distinguishable from the heuristic path.

#### Scenario: Heuristic vs trained
- **WHEN** the heuristic baseline scores a guide
- **THEN** `method = heuristic`, and a context containing `N` yields `in_distribution =
  False`

#### Scenario: Trained path without consent
- **WHEN** the trained Rule Set 3 path is requested without consent or the extra
- **THEN** it raises from the weight gate rather than silently using the heuristic

### Requirement: Editing outcome is a normalized spectrum with intent-aware labeling

The predicted indel spectrum SHALL be a normalized `EditOutcome` computed from local
reference around the cut, and a frameshift allele SHALL be marked intended only for a
knockout intent.

#### Scenario: Knockout frameshift
- **WHEN** the intent is knockout
- **THEN** frameshift indels are flagged as intended in the outcome

#### Scenario: Cut outside context
- **WHEN** the cut lies outside the outcome context window
- **THEN** the outcome predictor raises `ValueError`

### Requirement: A precise nuclease candidate carries its repair template

A double-strand break alone corrects nothing — it is repaired by error-prone NHEJ
into indels — so a nuclease candidate offered for a CORRECT, REVERT, or INSTALL
intent SHALL carry the HDR donor that makes the edit, or state that none was
available. It SHALL also flag whether the repaired product is still a Cas9
substrate, and SHALL flag that its attached outcome distribution is the NHEJ
byproduct spectrum rather than the intended correction. A knock-out candidate,
which wants the break itself, SHALL carry no donor and none of these flags.

#### Scenario: Donor over an assembly gap
- **WHEN** a homology arm would reach a reference `N` (an assembly gap)
- **THEN** no donor is built, mirroring the enumerators' per-span `N` guards — while
  an arm that merely runs past a contig end is shortened to the sequence the
  reference actually provides, not padded and then refused

#### Scenario: Precise intent
- **WHEN** the nuclease vertical designs for a precise intent
- **THEN** every candidate carries an `HDRDonor`, an `hdr-donor:*` flag naming its
  re-cut disposition, and an `outcome-is-nhej-spectrum` flag

#### Scenario: Knock-out intent
- **WHEN** the nuclease vertical designs for a disruption intent
- **THEN** no donor is attached and no donor flags are emitted

#### Scenario: The reagent line names the pair
- **WHEN** a precise nuclease candidate is summarized for a reader
- **THEN** the line names the donor and its re-cut disposition, not the guide alone

#### Scenario: Cleanliness of a precise nuclease candidate
- **WHEN** a precise nuclease candidate is ranked
- **THEN** its cleanliness score reflects the NHEJ spectrum it carries — which
  contains no intended allele — rather than an assumed HDR rate, and the
  `outcome-is-nhej-spectrum` flag says so; no HDR efficiency is invented

### Requirement: An HDR donor is not a substrate for re-cutting

When `hdr_donor` proposes an HDR template for a precise correction and is given the guide
it must survive, it SHALL introduce a PAM-blocking silent mutation in a homology arm so the
corrected allele is not re-cleaved by the guide, or SHALL explicitly report that none is
available — never silently emit a donor whose corrected product the guide still matches.

#### Scenario: Guide still matches the corrected allele
- **WHEN** the correcting edit leaves the guide's PAM and seed intact
- **THEN** the donor carries a reported PAM-blocking mutation, or `recut_blocked` is
  `False` with a note that none is available, rather than shipping a re-cuttable donor

#### Scenario: Correction itself disrupts the guide
- **WHEN** the correcting edit removes the guide's PAM or seed
- **THEN** the donor reports `recut_blocked` with no extra mutation needed

### Requirement: Candidates are ranked and flag their caveats

Cas9 candidates SHALL be ranked by descending efficiency then ascending worst-case
off-target, and SHALL surface `relaxed-pam` and `ood` as flags.

#### Scenario: Out-of-distribution guide
- **WHEN** a guide's efficiency input is out of distribution
- **THEN** the candidate carries an `ood` flag
