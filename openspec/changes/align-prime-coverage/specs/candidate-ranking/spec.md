# candidate-ranking (delta)

## MODIFIED Requirements

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
