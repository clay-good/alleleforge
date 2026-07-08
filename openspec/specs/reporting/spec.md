# reporting Specification

## Purpose

Flatten a ranked candidate menu into a self-contained, serializable design report that
leads with a research-use disclaimer and ends with provenance, then render it to HTML,
PDF, JSON, TSV, and Parquet with no business logic in the renderers and no sequence data
leaving the page.

## Requirements

### Requirement: Reports lead with a disclaimer and carry the full design

Every report SHALL lead with the research-use disclaimer and carry, per candidate, the
reagent summary, calibrated efficiency, top outcome alleles, an ancestry-stratified
off-target table sorted worst-first, cloning oligos, flags, and rationale.

#### Scenario: Out-of-distribution candidate
- **WHEN** a candidate is out of distribution
- **THEN** the HTML and PDF renders annotate it explicitly

#### Scenario: No candidates
- **WHEN** the menu has no candidates
- **THEN** the render states so rather than emitting an empty body

### Requirement: HTML is self-contained and injection-safe

The HTML render SHALL inline all figure specs, load no sequence-bearing external
resources, HTML-escape all user-derived text, and guard embedded script specs against
markup breakout.

#### Scenario: Untrusted text
- **WHEN** a candidate field contains markup characters
- **THEN** they are escaped in the rendered HTML

### Requirement: Exports are lossless or fixed-schema

JSON SHALL be the lossless form; TSV SHALL follow a fixed column order, one row per
candidate, with tabs and newlines stripped from cells; Parquet SHALL import its backend
lazily and raise a clear directive error if it is absent. Every export SHALL carry a
schema version so a downstream consumer can detect a field addition or reordering.

#### Scenario: Export schema version
- **WHEN** a TSV or Parquet export is produced
- **THEN** it carries a schema version identifying its column layout

#### Scenario: Missing Parquet backend
- **WHEN** Parquet export runs without its backend installed
- **THEN** it raises a clear `RuntimeError` naming the missing dependency

#### Scenario: Cell with a tab
- **WHEN** a TSV cell value contains a tab
- **THEN** the tab is stripped so the grid stays intact

### Requirement: Every render ends with provenance

Every render SHALL end with the provenance block so a report is self-contained for audit.

#### Scenario: Provenance footer
- **WHEN** a report is rendered
- **THEN** its footer carries the provenance block

### Requirement: Every render carries the cloning oligos

Every report render — HTML and PDF — SHALL include each candidate's cloning oligos (the
top/bottom sequences and the scheme), so the printable leave-behind is a complete wet-lab
deliverable a scientist can order reagents from. The PDF render SHALL NOT omit the oligos
that the HTML render includes.

#### Scenario: PDF includes the oligos
- **WHEN** a candidate with cloning oligos is rendered to PDF
- **THEN** the PDF contains that candidate's oligo sequences and scheme, not only its summary

#### Scenario: Reagent-free candidate
- **WHEN** oligos were requested but a candidate needs no synthesized oligo
- **THEN** the render states that no cloning oligos are required rather than omitting the
  section silently

### Requirement: Off-target scorer and matrix provenance are shown

The design report SHALL name the off-target scorer and the specificity matrix used
(published CFD versus the labeled approximation) alongside the off-target table, so a
reader can tell which scoring basis produced the numbers without inspecting the code.

#### Scenario: Report names the matrix
- **WHEN** a report with an off-target section is rendered
- **THEN** it states the scorer and matrix identity used for the reported scores

### Requirement: Leaderboard cells are escaped

The leaderboard HTML and Markdown renders SHALL escape all submitter-supplied cell content
(model name, submitter, task), so markup in a submitter handle cannot inject into the
static board and a table-delimiter character cannot break the layout.

#### Scenario: Markup in a handle
- **WHEN** a submission's model name or submitter contains markup or a table delimiter
- **THEN** it is escaped in the rendered leaderboard
