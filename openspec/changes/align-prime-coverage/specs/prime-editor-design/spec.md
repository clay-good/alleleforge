# prime-editor-design (delta)

## MODIFIED Requirements

### Requirement: Enumeration coverage is stated honestly

Routing SHALL advertise prime editing only for edit classes that enumeration can currently
produce (a feasibility check), and SHALL state a specific reason when it declines an edit
it cannot yet enumerate — not a generic "no actionable candidate" note. The supported edit
classes SHALL be documented.

#### Scenario: Unsupported edit class
- **WHEN** an insertion or deletion is requested and prime enumeration does not yet support
  it
- **THEN** routing either declines with a specific "not yet supported" reason or enumerates
  a valid pegRNA — never silently returns an empty menu with only a generic note

## ADDED Requirements

### Requirement: Pol-III transcription constraints are enforced and inspectable

pegRNA enumeration SHALL apply Pol-III (U6) transcription constraints — reject spacers
containing a `TTTT` terminator, enforce or annotate the 5'-G transcription start, and
apply a spacer-GC band — and SHALL expose each rejection as a stated reason rather than a
silent omission.

#### Scenario: Terminator in the spacer
- **WHEN** a candidate spacer contains a `TTTT` Pol-III terminator
- **THEN** it is rejected with a stated reason
