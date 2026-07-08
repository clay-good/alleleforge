## MODIFIED Requirements

### Requirement: PE3b nicking guides are preferred

A default pegRNA SHALL attach a tevopreQ1 epegRNA 3' motif; when a nicking guide is
requested, a seed-disrupting PE3b guide SHALL be preferred over an in-range PE3 guide, and
a candidate with no available nicking guide SHALL be flagged accordingly. A guide SHALL be
classified PE3b only when the edit falls in the nicking guide's **PAM-proximal seed** —
measured from the PAM-proximal protospacer end (for a frame-minus guide,
`edit - protospacer_start < seed_length`), the region whose disruption actually prevents
the guide from nicking the edited strand — never from the PAM-distal end.

#### Scenario: PE3b available
- **WHEN** a seed-disrupting nicking guide spanning the edit exists
- **THEN** it is chosen over a plain PE3 guide

#### Scenario: Edit in the PAM-proximal seed
- **WHEN** the edit lies within the nicking guide's PAM-proximal seed and changes the base
- **THEN** the guide is classified PE3b and preferred

#### Scenario: Edit in the PAM-distal region only
- **WHEN** the edit lies in the protospacer but outside the PAM-proximal seed
- **THEN** the guide is NOT classified PE3b, so the `pe3b` label never advertises
  seed disruption that does not hold
