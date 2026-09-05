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
off-target table sorted worst-first, cloning oligos, flags, and rationale — on **every**
human-readable surface (HTML and PDF alike), so the printable leave-behind is not missing a
field the on-screen report shows. A candidate that was **not** off-target-searched
(`n_offtarget_sites is None`) SHALL NOT be plotted in the worst-case-by-ancestry figure as a
`0.0` (best) score — "risk unknown" must never render as "safest," which would flip a visual
ranking toward the least-evidenced guide; a *searched* candidate with zero sites legitimately
plots `0.0`.

#### Scenario: Out-of-distribution candidate
- **WHEN** a candidate is out of distribution
- **THEN** the HTML and PDF renders annotate it explicitly

#### Scenario: Uncalibrated interval marked nominal
- **WHEN** a candidate's efficiency or bystander interval is not calibrated (`calibrated=False`,
  so its `interval_level` is a nominal target, not measured coverage)
- **THEN** the HTML and PDF renders qualify the interval as nominal — coverage not measured — so a
  reader cannot mistake it for an achieved-coverage band; a calibrated interval carries no such qualifier

#### Scenario: Rationale on every surface
- **WHEN** a candidate carries a ranking rationale
- **THEN** it appears on the PDF as well as the HTML and JSON — no human-readable surface
  silently drops it

#### Scenario: Unsearched candidate not drawn as safest
- **WHEN** the menu mixes off-target-searched and unsearched candidates
- **THEN** the ancestry off-target chart plots only the searched ones, so an unsearched
  candidate is never drawn as a `0.0` best-in-class bar

#### Scenario: No candidates
- **WHEN** the menu has no candidates
- **THEN** the render states so rather than emitting an empty body

### Requirement: A capped render states the cap and keeps the Pareto front

A human-facing render (HTML or PDF) MAY cap how many ranked candidates it draws, because a single prime
design routinely yields several hundred. When it does, it SHALL state on the page
how many candidates exist, how many are shown, and where the rest can be found;
and it SHALL render **every Pareto-front candidate** whatever its rank. The
lossless exports SHALL be unaffected by the cap.

#### Scenario: Pareto-front candidate ranked past the cap
- **WHEN** a candidate on the Pareto front ranks below the display cap
- **THEN** it is rendered anyway, in rank order with the rest

#### Scenario: Candidates withheld
- **WHEN** the cap withholds candidates
- **THEN** the page states the shown and total counts and points at the export

#### Scenario: Nothing withheld
- **WHEN** the report has no more candidates than the cap
- **THEN** no truncation note is rendered

#### Scenario: The two renders agree
- **WHEN** the same report is rendered to HTML and to PDF under the same cap
- **THEN** both draw the same candidate set, through one shared selection helper

#### Scenario: The cap is reachable from every surface
- **WHEN** a caller uses the CLI or the web API
- **THEN** the cap can be set there, and setting it never changes the lossless
  JSON/TSV export

### Requirement: A reagent line names the edit, not only the geometry

The one-line reagent summary SHALL identify what the reagent *does*, not only its
dimensions. For a pegRNA it SHALL state how many bases the RT template writes
alongside the PBS/RTT lengths, so a design correcting a small deletion is not
indistinguishable on the page from one installing a substitution.

#### Scenario: pegRNA restoring a deleted allele
- **WHEN** a pegRNA whose RT template writes more than one base is summarized
- **THEN** the reagent line states the number of bases written

### Requirement: HTML is self-contained and injection-safe

The HTML render SHALL inline all figure specs, load no sequence-bearing external
resources, HTML-escape all user-derived text, and guard embedded script specs against
markup breakout.

#### Scenario: Untrusted text
- **WHEN** a candidate field contains markup characters
- **THEN** they are escaped in the rendered HTML

### Requirement: Exports are lossless or fixed-schema

JSON SHALL be the lossless form; TSV SHALL follow a fixed column order, one row per
candidate, with every row/column delimiter — tabs, carriage returns, and line feeds —
stripped from cells so a user-influenced value (an ancestry label, a candidate flag)
cannot smuggle a row or column break; Parquet SHALL import its backend lazily and raise a
clear directive error if it is absent. Every export SHALL carry a schema version so a
downstream consumer can detect a field addition or reordering.

#### Scenario: Export schema version
- **WHEN** a TSV or Parquet export is produced
- **THEN** it carries a schema version identifying its column layout

#### Scenario: Calibration is a flat-export column
- **WHEN** a candidate is scored
- **THEN** the flat TSV/Parquet export carries a `calibrated` column alongside `in_distribution`, so a
  machine consumer can tell a calibrated band from a nominal heuristic one without parsing the JSON form

#### Scenario: Cell delimiters are neutralized
- **WHEN** a TSV cell value contains a tab, a carriage return, or a line feed (e.g. an
  ancestry label or flag carrying `\r`)
- **THEN** the delimiter is replaced so the row stays a single physical line that a
  standard CSV/TSV reader parses to the fixed column count

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

### Requirement: A report explains how its menu was assembled

A report SHALL carry the **menu-level** rationale — which chemistries routed and
why, which ran, and any that were skipped or failed — and every render SHALL show
it. The designer degrades gracefully when one chemistry fails and records the reason
there, so a report that drops it can be empty with no explanation anywhere in it,
which is the least useful artifact this layer can produce.

#### Scenario: A chemistry fails
- **WHEN** a chemistry's vertical is skipped or errors
- **THEN** the reason reaches the report and appears in the rendered page

#### Scenario: An empty menu
- **WHEN** no candidate is produced
- **THEN** the render still states which chemistries routed and what became of them

### Requirement: The menu states what the database says about the target

When the target variant carries a clinical assertion, the menu-level rationale SHALL lead
with it, and SHALL add a note when the requested intent and the classification pull in
different directions — correcting a benign variant or a variant of uncertain
significance, or installing a pathogenic allele.

These SHALL annotate only. A design SHALL NOT be refused on the basis of a
classification: correcting a benign variant can be legitimate (a research control, a
pending reclassification), and the system's job is to ensure it is not done by accident.
A design whose intent and classification agree SHALL produce no such note, so the note
carries information rather than appearing on every report.

#### Scenario: Intent disagrees with the classification
- **WHEN** a correction targets a variant classified benign
- **THEN** the rationale states the classification and notes the tension, and the menu is
  still produced

#### Scenario: Intent agrees with the classification
- **WHEN** a correction targets a pathogenic variant
- **THEN** the rationale states the classification and adds no caution

### Requirement: The menu states the target's predicted consequence

When an effect predictor annotates the target variant, the menu-level rationale SHALL
state the predicted consequence, its impact tier, the gene and protein change where
known, and the transcript it is reported against — explicitly noting when that transcript
is not the canonical one, since the same variant is missense on one transcript and
intronic on another.

A correcting intent against a variant of modifier impact SHALL be noted, and SHALL NOT be
refused: a variant with no predicted protein consequence may still be a splice or
regulatory target, and the prediction speaks for one transcript only.

#### Scenario: Annotated target
- **WHEN** a design runs with an effect predictor supplied
- **THEN** the rationale states the consequence, impact, gene, protein change and transcript

#### Scenario: Non-canonical transcript
- **WHEN** the consequence is reported against a non-canonical transcript
- **THEN** the rationale says so

### Requirement: Hazard flags are rendered apart from descriptive ones

A candidate's flags mix facts that merely describe it with facts that change what a
reader should do. Rendered as one flat list they carry identical weight, so a nick pair
close enough to act as a double-strand break reads like the name of a 3' motif. Every
human-facing render SHALL present the hazard flags separately and ahead of the flat
list, each with a one-line statement of why it matters, while the complete flag list is
still shown — separated, not filtered.

Every flag the system emits SHALL be classified as either a hazard or a description.
An unclassified flag SHALL fail the build rather than default to either, since
defaulting to "descriptive" silently demotes a hazard.

#### Scenario: A candidate with a close nick
- **WHEN** a candidate carries `close-nick`
- **THEN** the render states it on its own line with the reason, and also lists it among
  the candidate's flags

#### Scenario: A candidate with nothing wrong
- **WHEN** no flag on a candidate is a hazard
- **THEN** no caveat line is rendered at all

### Requirement: A cohort row's summary numbers describe one candidate

The per-variant summary is read by scanning columns across hundreds of rows, so its
fields SHALL all describe the **recommended** candidate. Mixing a menu-wide aggregate
with a top-candidate figure in one row makes them contradict each other and reports a
risk carried by a reagent the reader would never use.

#### Scenario: A clean recommendation beside a poor alternative
- **WHEN** the top candidate has no off-target site and a low-ranked alternative has a
  perfect one
- **THEN** the row's worst-off-target and specificity both describe the top candidate
