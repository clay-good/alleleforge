# candidate-ranking Specification

## Purpose

Assemble a multi-chemistry candidate menu for a variant, then order candidates by a
transparent, deterministic, multi-objective score and expose the Pareto front, so a
researcher sees not just a top pick but why it won and what it trades off.

## Requirements

### Requirement: Routing selects only biologically eligible chemistries

Routing SHALL evaluate a data-driven table of pure predicates and return one decision per
chemistry: nuclease for knockout intents, ABE/CBE for a transition SNV an editor can
install, and prime for a non-knockout precise small edit — SNV, MNV, insertion, deletion,
or delins — whose replaced reference span and written allele both fit the RT template
budgets, each with a rationale. The nuclease SHALL additionally route for a precise edit
**no break-free chemistry can reach**, as an explicit last resort, so such an edit yields
a complete reagent (guide plus HDR donor) rather than an empty menu. Ineligible or unrequested chemistries SHALL be recorded
with a note.

#### Scenario: Knockout intent
- **WHEN** the intent is knockout
- **THEN** only nuclease routes eligible; base and prime are recorded as not eligible

#### Scenario: Small indel correction
- **WHEN** a small insertion or deletion is corrected
- **THEN** prime routes eligible and is the only eligible chemistry

#### Scenario: Allele beyond the RT template budget
- **WHEN** the allele the edit must write exceeds what any in-range RTT can carry
- **THEN** prime is recorded as not eligible

#### Scenario: A precise edit beyond every break-free chemistry
- **WHEN** a precise edit can be reached by neither base nor prime editing
- **THEN** the nuclease routes eligible and is the only eligible chemistry

#### Scenario: A break-free chemistry can serve
- **WHEN** base or prime editing can reach a precise edit
- **THEN** the nuclease is recorded as not eligible, so HDR does not crowd the menu

#### Scenario: No chemistry is eligible
- **WHEN** no chemistry can make the requested edit
- **THEN** the menu rationale states that, and gives each chemistry's own reason for
  declining, rather than a bare list of `no`s

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
weights, validated finite, non-negative, and not all-zero. A non-finite weight (`nan` or
`inf`) SHALL be rejected at construction: it would otherwise pass a bare non-negativity
check and poison normalization — a `nan` weight drives every normalized fraction to `nan`,
an `inf` weight collapses the finite weights to zero — silently corrupting the composite
the order is sorted on.

#### Scenario: Weighted composite
- **WHEN** candidates are ranked
- **THEN** each carries a human-readable score breakdown naming its four objective values

#### Scenario: Non-finite weight rejected
- **WHEN** ranking weights are constructed with a `nan` or `inf` component (e.g. via the
  CLI `--weights` flag or a config file)
- **THEN** construction raises rather than producing a normalized composite of `nan`, and
  the CLI surfaces it as a usage error rather than an uncaught traceback

### Requirement: Safety uses the worst-affected ancestry

The safety objective SHALL use the worst-affected ancestry off-target score, never the
average, with a deterministic tie-break, so a guide dangerous in a single ancestry is
penalized rather than averaged out. A site whose per-ancestry attribution is **not
available** — a reference site, a patient site (carried by this individual, so with no
ancestry frequency), **or** a population site with a known frequency but an empty
per-ancestry breakdown (carried at some frequency, but the stratum is unknown) — SHALL
contribute to the worst case of every ancestry, so a dangerous off-target is never masked
on the safety axis by a benign ancestry-tagged site; the safety score therefore never
understates the genome-wide worst off-target, and the per-ancestry view stays consistent
with the frequency-weighted `expected_burden`, which counts such a site as a real hit.

#### Scenario: Single-ancestry danger
- **WHEN** a guide is dangerous only in one ancestry
- **THEN** its safety score reflects that worst ancestry

#### Scenario: Patient off-target with a benign population site
- **WHEN** a report carries a dangerous patient off-target and a lower-scoring
  ancestry-tagged population site
- **THEN** the safety score reflects the patient off-target, not the benign ancestry site,
  and adding the benign site does not raise safety

#### Scenario: Unattributed population off-target with a benign ancestry-tagged site
- **WHEN** a report carries a dangerous population off-target with a known frequency but no
  per-ancestry breakdown, alongside a lower-scoring ancestry-tagged population site
- **THEN** the safety score reflects the dangerous unattributed site (it floors every
  stratum), not the benign ancestry site, so adding the benign site does not raise safety

### Requirement: Ordering is total, deterministic, and Pareto-aware

Ordering SHALL be total and deterministic (composite, then efficiency, then safety, then
simplicity, then a stable reagent-identity tiebreak — the spacer sequence), so the order
is total independent of the input pool's assembly order, not merely of the enumeration
order. The non-dominated Pareto front over the four objectives SHALL be reported as indices
into the final order.

#### Scenario: Tie resolution
- **WHEN** two candidates tie on the composite
- **THEN** efficiency, then safety, then simplicity break the tie deterministically

#### Scenario: Full objective-vector tie
- **WHEN** two distinct candidates tie on all four objectives
- **THEN** the reagent-identity tiebreak orders them, so the menu is identical regardless of
  how the candidate pool was assembled

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

### Requirement: An unmeasured axis is reported as unmeasured

A cohort summary SHALL distinguish "not measured" from "measured and safe" on every
safety axis. When no candidate carries an off-target report — the search was
skipped — the summary's worst-off-target field SHALL be null, never a numeric
default. A cohort manifest is triaged by scanning a column, and the reassuring
value is the dangerous default.

#### Scenario: Off-target search skipped
- **WHEN** a cohort item is designed with the off-target search disabled
- **THEN** its summary reports a null worst-off-target, not `0.0`

#### Scenario: Off-target search run
- **WHEN** the search runs
- **THEN** the summary reports the measured number, so the two cases are
  distinguishable in the manifest

### Requirement: A menu states when its ordering is finer than its own uncertainty

A ranked list is read as a claim that each place beats the next. When the composite gap
between the leader and the candidates behind it is smaller than the uncertainty already
published for the leader's largest scoring term, that claim is not supported, and the
menu SHALL say so — naming the size of the unseparated leading group and directing the
reader to choose on the reagent rather than the rank.

The test SHALL be a stated inequality over quantities the system already computes, not a
fitted statistic: a hypothesis test here would require an error model the project does
not have, and inventing one repeats the false precision it is meant to expose. It SHALL
be able to report only that candidates are *unseparated*, never that one is better, so an
error makes the menu more cautious.

The ordering SHALL NOT change. A deterministic total order remains useful; it simply must
not be presented as a finding it is not.

#### Scenario: A blurred menu
- **WHEN** several leading candidates lie within the leader's own efficiency uncertainty
- **THEN** the rationale names the size of that group and the order is left unchanged

#### Scenario: A menu that resolves
- **WHEN** the leader is separated from the rest by more than that uncertainty
- **THEN** no such note is added

#### Scenario: A single candidate
- **WHEN** the menu holds one candidate
- **THEN** no note is added — there is no ordering to qualify

### Requirement: An unmeasured safety axis is labelled, not silently maximal

A candidate with no off-target report scores the maximum on safety, because there is
nothing to subtract. That is the reassuring extreme for an axis nobody examined, and it
enters the weighted composite exactly as an earned score would.

Every vertical SHALL flag such a candidate, and the flag SHALL be classified as a hazard
so that every render presents it apart from descriptive annotations. The ranking
arithmetic SHALL NOT be altered to penalise the absence: choosing a penalty is choosing a
number the project has no basis for, and a fabricated weight is worse than a labelled one.

#### Scenario: A design run without an off-target search
- **WHEN** candidates are produced with the off-target search disabled
- **THEN** each carries the not-searched flag, and its safety score is presented as
  unmeasured rather than as a clean result
