# offtarget-nomination (delta)

## MODIFIED Requirements

### Requirement: Single-bulge alignment within budget

At each PAM anchor the system SHALL consider every in-budget alignment (ungapped, a
single DNA bulge, a single RNA bulge) and SHALL report the alignment that maximizes the
specificity score (edit-minimal), with a deterministic tie-break — never merely the first
in-budget alignment found. A site is still never given both bulge types at once.

#### Scenario: Best alignment wins at an anchor
- **WHEN** an anchor admits both a 4-mismatch ungapped alignment and a 1-bulge,
  0-mismatch alignment
- **THEN** the higher-scoring (edit-minimal) alignment is reported, so the site's risk is
  not under-stated

#### Scenario: Bulge only when budgeted
- **WHEN** the DNA-bulge budget is zero
- **THEN** no site is nominated that requires a DNA bulge

## ADDED Requirements

### Requirement: Indel variants are placed at correct genomic coordinates

When a population, haplotype, or patient variant changes the length of the local window
(an insertion or deletion), nominated hits 3' of the indel SHALL be reindexed back to
their true genomic coordinates through a local coordinate lift, and the ref-vs-alt
created/strengthened comparison SHALL remain correct across the shift.

#### Scenario: Deletion-derived hit
- **WHEN** a variant deletes bases and a downstream created site is nominated on the
  alternate allele
- **THEN** the site is reported at its correct genomic locus, not shifted by the deletion
  length

### Requirement: A haplotype's non-clashing variants are still applied

When one variant in a haplotype clashes with the reference, the system SHALL apply the
remaining non-clashing variants rather than discarding the whole haplotype, and SHALL
record which variants were skipped.

#### Scenario: One clashing variant
- **WHEN** a haplotype carries one ref-clashing variant and one PAM-creating variant
- **THEN** the created site is still nominated, and the skipped variant is recorded
