## ADDED Requirements

### Requirement: Per-chemistry truncation preserves the composite optimum

When a per-chemistry candidate cap (`max_candidates_per_chemistry`) is applied, it SHALL
NOT remove a candidate that would rank above a retained candidate under the global
4-objective composite. Truncation SHALL be applied after projecting candidates onto the
shared ranking objectives, or deferred to the global ranker — never applied on a vertical's
local proxy sort before the composite is computed.

#### Scenario: Composite-preferred candidate is lower on a local proxy
- **WHEN** a candidate has modestly lower per-chemistry efficiency but a far better safety
  or cleanliness score, so the composite ranks it above a retained candidate
- **THEN** it survives the per-chemistry cap and appears in the returned menu

#### Scenario: Cap never hides the global best
- **WHEN** a cohort run sets a per-chemistry cap
- **THEN** the returned menu still contains the composite-optimal candidate for each
  eligible chemistry
