## ADDED Requirements

### Requirement: The ranking efficiency axis is target-base activity

The base-editor vertical SHALL populate the ranking efficiency objective with the
target-base editing **activity** — P(the target position is edited), independent of
bystander editing — and SHALL reserve the clean-edit fraction (target edited with no
bystander) for the cleanliness objective. The efficiency axis SHALL NOT be set to the
clean-edit probability, so it measures the same quantity (raw activity) that the Cas9 and
prime verticals place on the efficiency axis and a base editor is comparable to them.

#### Scenario: Active editor with an obligate bystander
- **WHEN** a base-editor candidate has high target-base activity but a co-edited bystander
- **THEN** it reports high efficiency and lower cleanliness — not one identical number on
  both axes — so its activity is not understated and the bystander is not charged twice

#### Scenario: Cross-chemistry comparability
- **WHEN** a base-editor candidate and a Cas9 or prime candidate are ranked in one menu
- **THEN** both efficiency axes denote editing activity, so the composite compares
  like with like
