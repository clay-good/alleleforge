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
not run past the template. Results SHALL be deterministically sorted.

#### Scenario: No reachable nick
- **WHEN** no PAM places a nick 5' of the edit within RT reach
- **THEN** enumeration returns empty

#### Scenario: Deterministic order
- **WHEN** multiple pegRNAs are enumerated
- **THEN** they are returned sorted by `(nick_site, PBS length, RTT length)`

### Requirement: PE3b nicking guides are preferred

A default pegRNA SHALL attach a tevopreQ1 epegRNA 3' motif; when a nicking guide is
requested, a seed-disrupting PE3b guide SHALL be preferred over an in-range PE3 guide, and
a candidate with no available nicking guide SHALL be flagged accordingly.

#### Scenario: PE3b available
- **WHEN** a seed-disrupting nicking guide spanning the edit exists
- **THEN** it is chosen over a plain PE3 guide

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

The enumerable edit classes SHALL be documented so routing does not advertise prime for
edits enumeration cannot yet produce; when an eligible edit yields no pegRNA, the menu
SHALL record an explicit reason rather than silently returning nothing.

#### Scenario: Routed but unenumerable edit
- **WHEN** an edit routes to prime but no pegRNA can be enumerated for its class
- **THEN** the menu records an explicit "eligible but no actionable candidate" note
