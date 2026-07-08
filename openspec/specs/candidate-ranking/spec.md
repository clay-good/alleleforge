# candidate-ranking Specification

## Purpose

Assemble a multi-chemistry candidate menu for a variant, then order candidates by a
transparent, deterministic, multi-objective score and expose the Pareto front, so a
researcher sees not just a top pick but why it won and what it trades off.

## Requirements

### Requirement: Routing selects only biologically eligible chemistries

Routing SHALL evaluate a data-driven table of pure predicates and return one decision per
chemistry: nuclease for knockout intents, ABE/CBE for a transition SNV an editor can
install, and prime for a non-knockout edit within the supported size, each with a
rationale. Ineligible or unrequested chemistries SHALL be recorded with a note.

#### Scenario: Knockout intent
- **WHEN** the intent is knockout
- **THEN** only nuclease routes eligible; base and prime are recorded as not eligible

### Requirement: Verticals degrade gracefully into one menu

Each eligible chemistry vertical SHALL run and the menu SHALL always carry either a
candidate per eligible chemistry or an explicit reason. A genuine defect (an unexpected
exception) SHALL be surfaced as a typed failure that is distinguishable from a legitimate
"no design found," rather than both collapsing into the same graceful-degradation note, so
a real bug is not masked.

#### Scenario: Expected empty result
- **WHEN** a vertical legitimately produces no candidate
- **THEN** the menu records a "no design" reason for that chemistry

#### Scenario: Unexpected defect
- **WHEN** a vertical raises an unexpected error (e.g. a type error, a bad handle)
- **THEN** it is surfaced as a typed failure distinguishable from "no design," and other
  chemistries still populate the menu

### Requirement: Candidates are scored on four transparent objectives

Ranking SHALL project each candidate onto efficiency, cleanliness (intended-outcome
probability), safety, and simplicity, and order by a weighted sum with published default
weights, validated non-negative and not all-zero.

#### Scenario: Weighted composite
- **WHEN** candidates are ranked
- **THEN** each carries a human-readable score breakdown naming its four objective values

### Requirement: Safety uses the worst-affected ancestry

The safety objective SHALL use the worst-affected ancestry off-target score, never the
average, with a deterministic tie-break, so a guide dangerous in a single ancestry is
penalized rather than averaged out.

#### Scenario: Single-ancestry danger
- **WHEN** a guide is dangerous only in one ancestry
- **THEN** its safety score reflects that worst ancestry

### Requirement: Ordering is total, deterministic, and Pareto-aware

Ordering SHALL be total and deterministic (composite, then efficiency, then safety, then
simplicity), on top of deterministic enumeration order, and the non-dominated Pareto front
over the four objectives SHALL be reported as indices into the final order.

#### Scenario: Tie resolution
- **WHEN** two candidates tie on the composite
- **THEN** efficiency, then safety, then simplicity break the tie deterministically

#### Scenario: Incomparable candidates
- **WHEN** two candidates are Pareto-incomparable
- **THEN** both appear in the reported Pareto front

### Requirement: The menu carries its rationale

The ranked menu SHALL carry a rationale naming the weights and the worst-ancestry safety
rule, and each candidate SHALL surface any caveat flags (e.g. `ood`, `relaxed-pam`).

#### Scenario: Empty menu
- **WHEN** no chemistry routes eligible
- **THEN** ranking returns an empty menu with the routing rationale and no error

### Requirement: Ranking is uncertainty-aware

Candidate ordering SHALL incorporate each prediction's uncertainty, not only its point
estimate. An out-of-distribution prediction (`in_distribution = False`) SHALL be
penalized relative to an otherwise-equal in-distribution one, and a candidate's interval
width and calibration status SHALL influence its rank (for example, ranking an
out-of-distribution candidate on its lower interval bound). The uncertainty inputs SHALL
be surfaced in the per-candidate score breakdown.

#### Scenario: OOD candidate ranks lower
- **WHEN** two candidates are identical except one has `in_distribution = False`
- **THEN** the out-of-distribution candidate ranks below the in-distribution one

#### Scenario: Uncertainty shown in the rationale
- **WHEN** a ranked menu is produced
- **THEN** each candidate's score breakdown reports its efficiency interval and
  out-of-distribution status, not only the point estimate

### Requirement: Per-chemistry truncation preserves the composite optimum

When a per-chemistry candidate cap (`max_candidates_per_chemistry`) is applied, it SHALL
NOT remove a candidate that would rank above a retained candidate under the global
4-objective composite. Truncation SHALL be applied after projecting candidates onto the
shared ranking objectives, or deferred to the global ranker — never applied on a vertical's
local proxy sort before the composite is computed.

#### Scenario: Composite-preferred candidate is lower on a local proxy
- **WHEN** a candidate has modestly lower per-chemistry efficiency but a far better safety
  or cleanliness score, so the composite ranks it above a retained candidate
- **THEN** it survives the per-chemistry cap and appears in the returned menu

#### Scenario: Cap never hides the global best
- **WHEN** a cohort run sets a per-chemistry cap
- **THEN** the returned menu still contains the composite-optimal candidate for each
  eligible chemistry
