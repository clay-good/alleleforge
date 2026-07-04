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
lazily and raise a clear directive error if it is absent.

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
