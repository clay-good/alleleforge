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

#### Scenario: Alt allele destroys the reference PAM
- **WHEN** a CORRECT intent's alternate allele removes a PAM present in the reference
- **THEN** no guide is emitted at that PAM, because it does not exist in the target genome

#### Scenario: Alt allele creates a PAM
- **WHEN** the alternate allele creates a PAM absent from the reference
- **THEN** the corresponding guide is enumerated and scored on the carried sequence

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
