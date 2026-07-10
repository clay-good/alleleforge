# offtarget-scoring Specification

## Purpose

Rank each nominated off-target site by published single-guide specificity scores (CFD
primary, MIT/Hsu secondary) behind a swappable scorer protocol, and aggregate them into
a genome-wide, ancestry-stratified specificity so a design's off-target risk is a single
auditable, per-ancestry number.

## Requirements

### Requirement: Sites are scored with CFD and thresholded transparently

The system SHALL score each candidate with a primary scorer (default CFD) and retain any
site clearing CFD ≥ 0.20 OR MIT ≥ 0.10, reporting both scores. CFD SHALL be the product
of per-position mismatch weights and a PAM-dinucleotide weight in `[0, 1]`.

#### Scenario: Perfect match
- **WHEN** the spacer equals the protospacer with a canonical PAM
- **THEN** CFD and MIT are both 1.0

#### Scenario: Retained by MIT alone
- **WHEN** a site clears the MIT threshold but not the CFD threshold
- **THEN** it is retained and both scores are recorded

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

#### Scenario: Injected published matrix
- **WHEN** the published Doench mismatch table is injected
- **THEN** CFD uses it verbatim

#### Scenario: Standalone off-target surfaces expose the effective matrix
- **WHEN** a report whose reported sites all fell back to the approximation is rendered by
  the `aforge offtarget` CLI or the `/api/offtarget` endpoint
- **THEN** the surface exposes the reconciled effective matrix (the per-site truth), not only
  the nominal configured `score_matrix`, so a consumer reading the top-level label is never
  misled into treating an all-approximation table as published CFD — the same honesty the
  design report already applies via `effective_matrix()`

### Requirement: MIT/Hsu is exact and length-guarded

The MIT/Hsu score SHALL implement the published Hsu 2013 formula (position-weight
product, pairwise-spacing term, and `1/n²` count term) and SHALL require exactly-20-nt
equal-length sequences; bulged or non-20-nt sites SHALL record no MIT score and be
treated as 0.0 for thresholding.

#### Scenario: Wrong length
- **WHEN** MIT is asked to score sequences that are not both 20 nt
- **THEN** it raises `ValueError`

#### Scenario: Bulged site
- **WHEN** a site was found via a bulge alignment
- **THEN** its MIT score is recorded as absent, not fabricated

### Requirement: Scores validate to [0, 1] and aggregate per ancestry

Every site score SHALL validate into `[0, 1]` and every non-reference site SHALL carry a
causal allele. The report SHALL expose the worst score, a genome-wide specificity score
`1/(1 + Σ sᵢ)`, and a per-ancestry worst-case stratification.

#### Scenario: Ancestry stratification
- **WHEN** a guide is dangerous only in one ancestry
- **THEN** the report's per-ancestry worst score reflects that ancestry

### Requirement: The genome-wide aggregate covers the full nominated set

The genome-wide `specificity_score` SHALL aggregate over the full set of nominated
in-budget off-target sites, including sites below the reporting threshold: the engine
SHALL carry the best per-placement score of each sub-threshold nomination into the
aggregate (the sub-threshold tail) so a guide with a large near-threshold tail cannot
report the same specificity as a clean guide, matching the CRISPOR/Hsu aggregate that
sums over all candidate sites rather than only the reporting-threshold survivors.

#### Scenario: Two guides differ only in their sub-threshold tail
- **WHEN** two guides have identical above-threshold hits but one has additional
  near-threshold off-targets that do not clear the reporting threshold
- **THEN** the guide with the larger sub-threshold tail reports a lower genome-wide
  specificity, not an identical one

### Requirement: The guide's own on-target is excluded from the aggregate

The reference always contains the guide's own protospacer, so a genome-wide scan nominates
it as a perfect (score 1.0) match. It is the *intended* target, not an off-target: the
CRISPOR/Hsu aggregate excludes it, and counting it would peg every guide's `worst_score`
at 1.0 (an inert safety axis) and cap `specificity_score` at 0.5 for even a perfectly clean
guide. When a design pass supplies the guide's on-target locus, the engine SHALL exclude
the single site at exactly that locus (naming-aware on the contig) from both the reported
sites and the sub-threshold tail. The exclusion SHALL be exact, not by overlap or by
perfect-score: a *paralogous* perfect match at any other locus is a real off-target and
SHALL be retained. A bare off-target scan with no on-target supplied reports the on-target
like any other match. Because `on_target` changes the report, the cross-run reference cache
SHALL fold it into the content-addressed key (naming-aware, exactly as the exclusion match
is), so a bare scan and an on-target-excluding scan never collide on one entry and get
served the other's report — which would silently either count the self-match or hide a
perfect-score off-target.

#### Scenario: Clean guide reports full specificity
- **WHEN** a guide's only genomic match is its own on-target locus and the design pass
  supplies that locus
- **THEN** the report nominates zero off-target sites, `specificity_score` is 1.0, and
  `worst_score` is 0.0

#### Scenario: Paralogous perfect match survives on-target exclusion
- **WHEN** the guide's protospacer also occurs verbatim at a second, distinct locus
- **THEN** the on-target locus is excluded but the paralog is retained as a perfect-score
  off-target

#### Scenario: On-target locus keys the cross-run cache
- **WHEN** the same guide is searched against the same reference once as a bare scan and
  once with an on-target locus supplied, sharing one cache root
- **THEN** the two searches key distinct cache entries — the on-target-excluding scan is
  not served the bare scan's report (which still counts the self-match), nor vice versa

### Requirement: Published CFD requires a 20-nt spacer

The published Doench 2016 CFD matrix is indexed by absolute position 0–19, so `cfd_score`
SHALL raise when a fixed-position mismatch matrix is supplied for any non-20-nt alignment,
rather than scoring in the wrong register or silently collapsing to 0 at a position ≥ 20.
The length-relative approximation is defined for any length and is exempt. The default
`CfdScorer` SHALL NOT raise on a bulge-collapsed or off-length alignment (that would gut
recall); it SHALL instead fall back to the approximation for that site and record the
approximation as the site's matrix, so a non-20-nt score is never labeled published CFD.

#### Scenario: Off-length published CFD
- **WHEN** `cfd_score` is asked to score a 19-nt or 21-nt alignment with the published
  mismatch matrix
- **THEN** it raises `ValueError`

#### Scenario: Bulge-collapsed site is honestly labeled
- **WHEN** the engine scores an RNA-bulge site (a 19-nt collapsed alignment) with the
  default published scorer
- **THEN** the site is still nominated and its recorded matrix is the approximation, not
  `doench-2016-cfd`

### Requirement: A frequency-aware aggregate accompanies the worst-case

The report SHALL expose a frequency-aware `expected_burden` — the sum of each site's score
weighted by the probability a genome carries it (reference and patient sites weight 1.0, a
population site weights its carrying-population frequency) — alongside the frequency-blind
`worst_score` and `specificity_score`, so a rare-variant off-target and a universal one
are distinguishable in the summary numbers.

#### Scenario: Rare versus universal off-target
- **WHEN** one off-target is present at the MAF floor (0.001) and another is a universal
  reference site of the same raw score
- **THEN** the expected burden weights them a thousandfold apart while the frequency-blind
  worst-case reports the same raw score for both

### Requirement: Scorers are swappable behind a protocol

All scorers SHALL satisfy a common `OffTargetScorer` protocol so a future ML or
recalibrated scorer drops in without engine changes.

#### Scenario: Custom scorer
- **WHEN** a caller supplies a scorer implementing the protocol
- **THEN** the engine uses it without modification (and disables the reference-only cache)
