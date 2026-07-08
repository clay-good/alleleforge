## ADDED Requirements

### Requirement: Every render carries the cloning oligos

Every report render — HTML and PDF — SHALL include each candidate's cloning oligos (the
top/bottom sequences and the scheme), so the printable leave-behind is a complete wet-lab
deliverable a scientist can order reagents from. The PDF render SHALL NOT omit the oligos that
the HTML render includes.

#### Scenario: PDF includes the oligos
- **WHEN** a candidate with cloning oligos is rendered to PDF
- **THEN** the PDF contains that candidate's oligo sequences and scheme, not only its summary

#### Scenario: Reagent-free candidate
- **WHEN** a candidate needs no synthesized oligo
- **THEN** the render states that no cloning oligos are required rather than omitting the
  section silently
