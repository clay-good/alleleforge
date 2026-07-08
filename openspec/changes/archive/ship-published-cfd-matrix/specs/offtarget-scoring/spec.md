# offtarget-scoring (delta)

## MODIFIED Requirements

### Requirement: Scoring-matrix provenance is explicit

The CFD PAM weights SHALL be the published Doench 2016 values, and the per-position
mismatch weights SHALL default to the published Doench 2016 CFD matrix (vendored with its
citation). The transparent monotonic approximation SHALL remain available only behind an
explicit, labeled option for offline/deterministic-fallback use. Every score SHALL record
which matrix produced it, so a consumer is never misled that an approximation is the
published CFD.

#### Scenario: Default reproduces published CFD
- **WHEN** CFD scores a site with the default weights
- **THEN** the score matches the published Doench 2016 CFD for that mismatch pattern

#### Scenario: Approximation is opt-in and labeled
- **WHEN** the approximation weights are selected
- **THEN** the score records that the approximation, not the published matrix, produced it

### Requirement: Scores validate to [0, 1] and aggregate per ancestry

Every site score SHALL be clamped or validated into `[0, 1]` inside the scorer, at scoring
time, with a clear message when an input weight is out of range — never surfaced as a
downstream site-construction abort. Every non-reference site SHALL carry a causal allele,
and the report SHALL expose the worst score, a genome-wide specificity score, and a
per-ancestry worst-case stratification.

#### Scenario: Out-of-range weight
- **WHEN** an injected mismatch weight would drive a score above 1.0
- **THEN** the scorer clamps or rejects it at scoring time with a clear message
