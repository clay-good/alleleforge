# reporting (delta)

## MODIFIED Requirements

### Requirement: Exports are lossless or fixed-schema

JSON SHALL be the lossless form; TSV SHALL follow a fixed column order, one row per
candidate, with tabs and newlines stripped from cells; Parquet SHALL import its backend
lazily and raise a clear directive error if it is absent. Every export SHALL carry a
schema version so a downstream consumer can detect a field addition or reordering.

#### Scenario: Export schema version
- **WHEN** a TSV or Parquet export is produced
- **THEN** it carries a schema version identifying its column layout

## ADDED Requirements

### Requirement: Leaderboard cells are escaped

The leaderboard HTML and Markdown renders SHALL escape all submitter-supplied cell content
(model name, submitter, task), so markup in a submitter handle cannot inject into the
static board and a table-delimiter character cannot break the layout.

#### Scenario: Markup in a handle
- **WHEN** a submission's model name or submitter contains markup or a table delimiter
- **THEN** it is escaped in the rendered leaderboard
