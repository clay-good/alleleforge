## ADDED Requirements

### Requirement: The genome-wide aggregate covers the full nominated set

The single-number genome-wide `specificity_score` SHALL aggregate over the full set of
nominated in-budget off-target sites, including sites below the reporting threshold — or,
if it is computed only over reporting-threshold survivors, it SHALL be documented and
labeled as such so it is not read as the CRISPOR/Hsu aggregate it resembles. The intent
is that a guide with a large sub-threshold off-target tail cannot report the same
specificity as a clean guide.

#### Scenario: Two guides differ only in their sub-threshold tail
- **WHEN** two guides have identical above-threshold hits but one has many additional
  near-threshold off-targets
- **THEN** the promiscuous guide reports a lower genome-wide specificity, not an identical one

### Requirement: Published CFD requires a 20-nt spacer

The default published-CFD scorer SHALL require a 20-nt spacer and protospacer and SHALL
raise (or record CFD as inapplicable) for any other length, rather than silently scoring
an off-length input — where a position ≥20 falls outside the published matrix and returns
weight 0.0, collapsing CFD, or a truncated guide is scored in the wrong PAM-relative
register. When CFD is inapplicable, the recorded matrix identity SHALL reflect that the
published matrix could not be applied, so a non-20-nt score is never labeled as the
published CFD.

#### Scenario: Off-length spacer
- **WHEN** CFD is requested for a 19-nt or 21-nt spacer
- **THEN** the scorer raises or marks CFD inapplicable, and the result is not labeled
  `doench-2016-cfd`

### Requirement: A frequency-aware aggregate accompanies the frequency-blind worst-case

The off-target report SHOULD expose a frequency-aware aggregate — an expected off-target
burden weighting each non-reference site by its carrying-population frequency — alongside
the existing frequency-blind `worst_score` and `specificity_score`, so a rare-variant
off-target and a universal one are distinguishable in the summary numbers.

#### Scenario: Rare versus universal off-target
- **WHEN** one off-target is present at the MAF floor (0.001) and another is a universal
  reference site
- **THEN** the frequency-aware aggregate weights them differently, while the
  frequency-blind worst-case still reports the higher raw score
