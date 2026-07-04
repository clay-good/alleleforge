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

The CFD PAM weights SHALL be the published Doench 2016 values; the per-position mismatch
weights default to a transparent monotonic seed-tolerance approximation, with the exact
published 400-value matrix injectable. Which matrix produced a score SHALL be
distinguishable so a consumer is never misled that an approximation is the published CFD.

#### Scenario: Injected published matrix
- **WHEN** the published Doench mismatch table is injected
- **THEN** CFD uses it verbatim

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

### Requirement: Scorers are swappable behind a protocol

All scorers SHALL satisfy a common `OffTargetScorer` protocol so a future ML or
recalibrated scorer drops in without engine changes.

#### Scenario: Custom scorer
- **WHEN** a caller supplies a scorer implementing the protocol
- **THEN** the engine uses it without modification (and disables the reference-only cache)
