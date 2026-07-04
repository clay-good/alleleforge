# candidate-ranking (delta)

## ADDED Requirements

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
