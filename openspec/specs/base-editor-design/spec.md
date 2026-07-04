# base-editor-design Specification

## Purpose

For a transition SNV, enumerate every ABE/CBE sgRNA that places the target base inside an
editor's activity window, then predict the window-allele distribution, the probability of
the exact intended allele, and the bystander burden. Protospacer positions are 1-based
with PAM-distal = position 1.

## Requirements

### Requirement: Base editors are declarative descriptors

Each base editor SHALL be a declarative descriptor (deaminase, chemistry, target base,
result base, activity window, PAM, motif preference) so adding an editor is a data change,
not new control flow.

#### Scenario: Registered editor
- **WHEN** a new editor descriptor is added to the registry
- **THEN** it is enumerable without changes to the enumeration logic

### Requirement: Only transition SNVs are editable

Enumeration SHALL proceed only for transition SNVs an editor can install; a transversion
or non-SNV SHALL yield no candidates.

#### Scenario: Transversion
- **WHEN** the variant is a transversion
- **THEN** enumeration returns empty

### Requirement: The target base must sit in-window on the edited strand

A candidate SHALL require the target base to sit within the activity window (default
protospacer positions 4–8) on the editing strand, choosing plus or minus strand as the
editor's chemistry requires; other in-window target bases SHALL be recorded as bystanders.

#### Scenario: Minus-strand editing
- **WHEN** a correction needs a `G→A` change on the plus strand
- **THEN** the CBE edits the complementary `C→T` on the minus strand and an sgRNA placing
  that base in-window is emitted

#### Scenario: Bystander present
- **WHEN** a second editable base falls in-window
- **THEN** it is recorded as a bystander and the candidate carries bystander flags

### Requirement: Outcome quantities are calibrated Predictions

The outcome predictor SHALL enumerate the window alleles, derive `p_intended_exact`
(target edited with no bystander) and a bystander burden, and return each as a
`Prediction[float]`; per-base edit probability SHALL peak mid-window and be modulated by
the editor's sequence-motif preference. The heuristic baseline and the gated trained
BE-DICT path SHALL both honor the uncertainty contract, and the trained path SHALL be
license/consent-gated and limited to its supported editors.

#### Scenario: Motif preference
- **WHEN** a CBE edits a C with a 5' T neighbor
- **THEN** its edit probability is boosted relative to a non-T neighbor

#### Scenario: Unsupported trained editor
- **WHEN** BE-DICT is asked for an editor it does not support
- **THEN** it raises `ValueError` before the gate

### Requirement: Cleanest candidate is recommended

Candidates SHALL be ranked by descending `p_intended_exact` then ascending bystander
burden, and the cleanest SHALL carry a `recommended` flag.

#### Scenario: No bystanders
- **WHEN** a candidate has no in-window bystanders
- **THEN** it is flagged `clean`, and the top candidate additionally gets `recommended`
