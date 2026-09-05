## MODIFIED Requirements

### Requirement: Routing selects only biologically eligible chemistries

Routing SHALL evaluate a data-driven table of pure predicates and return one decision per
chemistry: nuclease for knockout intents, ABE/CBE for a transition SNV an editor can
install, and prime for a non-knockout precise small edit — SNV, MNV, insertion, deletion,
or delins — whose replaced reference span and written allele both fit the RT template
budgets, each with a rationale. Ineligible or unrequested chemistries SHALL be recorded
with a note.

#### Scenario: Knockout intent
- **WHEN** the intent is knockout
- **THEN** only nuclease routes eligible; base and prime are recorded as not eligible

#### Scenario: Small indel correction
- **WHEN** a small insertion or deletion is corrected
- **THEN** prime routes eligible and is the only eligible chemistry

#### Scenario: Allele beyond the RT template budget
- **WHEN** the allele the edit must write exceeds what any in-range RTT can carry
- **THEN** prime is recorded as not eligible
