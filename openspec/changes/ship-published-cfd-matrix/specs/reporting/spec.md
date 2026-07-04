# reporting (delta)

## ADDED Requirements

### Requirement: Off-target scorer and matrix provenance are shown

The design report SHALL name the off-target scorer and the specificity matrix used
(published CFD versus the labeled approximation) alongside the off-target table, so a
reader can tell which scoring basis produced the numbers without inspecting the code.

#### Scenario: Report names the matrix
- **WHEN** a report with an off-target section is rendered
- **THEN** it states the scorer and matrix identity used for the reported scores
