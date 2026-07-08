## ADDED Requirements

### Requirement: Correction-intent guides are enumerated against the carried allele

For a CORRECT, REVERT, or INSTALL intent — where the target genome carries the alternate
allele — the Cas9 enumerator SHALL substitute the carried allele onto the local window
before enumerating protospacers and PAMs, so guides are enumerated against the sequence
the target genome actually contains, consistent with the base-editor and prime enumerators.
A PAM the alternate allele destroys SHALL NOT be emitted; a PAM the alternate allele
creates SHALL be found; and on-/off-target scoring SHALL run on the carried 20-mer.

#### Scenario: Alt allele destroys the reference PAM
- **WHEN** a CORRECT intent's alternate allele removes a PAM present in the reference
- **THEN** no guide is emitted at that PAM, because it does not exist in the target genome

#### Scenario: Alt allele creates a PAM
- **WHEN** the alternate allele creates a PAM absent from the reference
- **THEN** the corresponding guide is enumerated and scored on the carried sequence

### Requirement: An HDR donor is not a substrate for re-cutting

When `hdr_donor` proposes an HDR template for a precise correction, it SHALL introduce a
PAM- or seed-blocking silent mutation so the corrected allele is not re-cleaved by the
guide, or SHALL explicitly report that no blocking mutation is available — never silently
emit a donor whose corrected product the guide still matches.

#### Scenario: Guide still matches the corrected allele
- **WHEN** the correcting edit leaves the guide's PAM and seed intact
- **THEN** the donor carries a reported PAM/seed-blocking mutation, or the result states
  that none is available, rather than shipping a re-cuttable donor
