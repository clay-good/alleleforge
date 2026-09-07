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

Every artifact SHALL carry the core research-use sentence, and SHALL carry only the
further sentences that describe *it*. A caveat that does not describe the thing it is
attached to is noise, and reusing one verbatim across artifacts is how that happens: the
ranked-candidates sentence belongs to a menu, the off-target-validation sentence to a
surface that nominates sites.

#### Scenario: A surface with neither candidates nor nominations
- **WHEN** a liveness or status response carries the disclaimer
- **THEN** it carries the core sentence alone

#### Scenario: A surface that nominates sites but ranks nothing
- **WHEN** the standalone off-target command or endpoint carries the disclaimer
- **THEN** it carries the validation sentence and not the ranked-candidates one

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
downstream consumer can detect a field addition or reordering. Every flat export SHALL
also carry the report's disclaimer and provenance in whatever channel its format
provides — comment lines for TSV, file metadata for Parquet — because the flat table is
the surface a result is forwarded in, and a specificity with no caveat attached is the
one thing the human renders never ship.

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

#### Scenario: Both flat formats state the same provenance
- **WHEN** the same report is written as TSV and as Parquet
- **THEN** the disclaimer, reference build and coordinate convention appear in both —
  as `#` comment lines in the TSV and as file-level key/value metadata in the Parquet —
  drawn from one source, so two tables of identical numbers cannot disagree about which
  genome they are against

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

### Requirement: A mixed-matrix report names the matrix behind its headline number

A report carries no per-site rows: it summarises, and the lossless export holds the sites.
When a candidate's off-target table mixes scoring matrices, the effective matrix names
both and cannot say which produced the worst-case score — the number that drives the
safety axis, the ancestry table and the triage decision. The report SHALL name the matrix
that scored the worst site, and SHALL NOT repeat it when every site shares one matrix.

#### Scenario: A mixed table
- **WHEN** a candidate's reported sites were scored by more than one matrix
- **THEN** every render names the matrix that produced the worst score

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

Each heading in that rationale SHALL be true of every line beneath it. The declined list
and the run outcomes are different claims — "not the right chemistry for this edit" and
"the right chemistry, no site here" send a reader somewhere different — and share a
bullet format.

#### Scenario: A chemistry that ran
- **WHEN** a chemistry produced candidates
- **THEN** its outcome appears under the run-notes heading, never under the heading for
  chemistries that declined

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
defaulting to "descriptive" silently demotes a hazard. Conversely, every classified
flag SHALL be one the system can actually emit: a written explanation for a condition
no candidate can carry reads as coverage while providing none.

#### Scenario: A classified flag nothing attaches
- **WHEN** a flag has a caveat sentence but no code path attaches it to a candidate
- **THEN** the build fails, because the sentence is a promise rather than a safeguard

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

### Requirement: The machine-readable export qualifies its own numbers

The flat candidate export is consumed by code, which cannot notice that a number is
unqualified and cannot go looking. It SHALL therefore carry the same qualifications the
human renders do: alongside the nominated-site count, the aggregate specificity, the
scorer and effective weight matrix, and the search settings the count is conditional on;
and alongside the flag list, the hazard subset, so a filter need not hard-code which flag
names are hazards.

Adding, removing or reinterpreting a column SHALL bump the export schema version, which
leads every row so a consumer can branch before parsing.

#### Scenario: A pipeline filtering on off-target risk
- **WHEN** a candidate was searched
- **THEN** its row carries the site count, the specificity, the scoring basis and the
  search settings together

### Requirement: A truncated outcome table declares its truncation

The predicted outcome distribution is shown top-first and capped, while `P(intended)` is
computed over the whole distribution. Presented together without a note the two figures
read as an arithmetic error rather than as a summary. A capped outcome table SHALL state
how many alleles the distribution holds and how much probability mass the shown rows
account for, so the difference between the table and the total is explained rather than
apparent.

A table showing every allele SHALL add no such note.

#### Scenario: An NHEJ spectrum
- **WHEN** a knock-out candidate's distribution holds more alleles than the table shows
- **THEN** the render states the count and the shown probability mass

### Requirement: A cohort row records which safety sources screened it

A cohort is scanned row by row, and two variants screened against different sources
produce identical-looking rows — the candidate counts do not move when a haplotype panel
or patient VCF is absent. Each row SHALL record which supplied sources contributed for
that variant, so a per-item difference in screening is visible where the reader is
looking.

#### Scenario: A panel that reached only some items
- **WHEN** items in one cohort were screened against different sources
- **THEN** their rows differ in the recorded sources rather than appearing identical

### Requirement: A design at an assembly-ambiguous locus discloses it

A locus overlapping a segmental duplication, a centromere, or another known-difficult
region of the current build is one where a read cannot be placed uniquely — so the
off-target search under-reports there and the on-target coordinates are less certain.
The resolver already detects this. Every candidate designed at such a locus SHALL carry
the ambiguity as a caveat flag naming the region kind, alongside the recommended
alternative build, and every render SHALL explain what it means for the result rather
than only naming the geography.

#### Scenario: A design inside a segmental duplication
- **WHEN** the resolved variant's working interval overlaps a segdup
- **THEN** every candidate carries `ambiguous-region:segdup` and the recommended build,
  and the caveat states that the off-target search under-reports there

### Requirement: A report states the coordinate base of its loci

Every rendered report SHALL state, once, the coordinate convention its loci are in.
AlleleForge is uniformly 0-based half-open at both human boundaries — a typed
`--region` locus in, every printed locus out — and a bare coordinate is read by a
genome browser as 1-based inclusive, so the same digits name a different base.

#### Scenario: A printed cut site
- **WHEN** a report renders a candidate's cut site, nick site, or off-target interval
- **THEN** the report footer states that coordinates are 0-based half-open and that a
  genome browser reads the same locus as 1-based inclusive

### Requirement: A scoring function is cited in the output, not only in the source

Every specificity scorer the engine can be configured with SHALL carry the published
method it implements, and that citation SHALL appear in the rendered report and the
flat export alongside the scorer name. "Cite everything" covers datasets, models
**and scoring functions**, and a citation that lives only in a module docstring does
not travel with the result a lab shares.

#### Scenario: A report scored with the published CFD matrix
- **WHEN** a candidate's off-target sites were scored by CFD
- **THEN** the report names the scorer, the weight source, and Doench et al. 2016

### Requirement: The intended allele is always shown

A capped outcome table SHALL include the intended allele even when it falls outside the
top N by probability, and the reported shown-mass SHALL account for the rows actually
shown. A base editor with in-window bystanders routinely ranks the requested edit
outside the top few, and a table that omits it answers "what will happen" without
answering "will I get what I asked for".

#### Scenario: The intended edit is a low-probability outcome
- **WHEN** the intended allele ranks below the display cap
- **THEN** it is shown anyway, marked intended, and counted in the shown mass

### Requirement: A reagent whose likeliest outcome is not the requested edit says so

A candidate SHALL carry a caveat when an intended allele exists and some other allele
is more likely, on every chemistry, naming `P(intended)`. This is a comparison the
predicted distribution already makes, not a threshold: no defensible cutoff separates
an acceptable `P(intended)` from an unacceptable one, and the fact a reader needs is
that something else will happen more often than what they asked for.

#### Scenario: A bystander-only edit is the modal outcome
- **WHEN** the highest-probability allele is not the intended one
- **THEN** the candidate carries `intended-not-modal:<P(intended)>` and the report
  renders it as a caveat

### Requirement: A placed candidate states where in the genome it edits

Every candidate whose reagent has a genomic placement SHALL carry a contig-qualified
locus, together with the cut or nick site where the chemistry defines one, on every
human-readable surface and in the flat export. A coordinate without its contig cannot be
opened in a genome browser and is not unique in a cohort report spanning several genes.
The locus SHALL be read from the placement, never synthesized: an unplaced candidate
states no locus rather than naming a contig it does not have.

#### Scenario: A prime-editing report
- **WHEN** a report is rendered for placed pegRNA candidates
- **THEN** each names its contig, interval and nick site, rather than describing the
  reagent with no genomic position at all


### Requirement: A hazard is not typeset as a footnote

On a human-facing render, a caveat or an ordering hazard SHALL be visually separated from
the routine notes around it — pagination counts, flag lists, protocol reminders — and
SHALL NOT be rendered in the class the page uses to de-emphasize. On the printable sheet
it SHALL precede the sequences it condemns.

The rule is about the relationship, not a colour: a hazard may not be smaller or greyer
than the body it sits among.

#### Scenario: A candidate with a caveat and an ordering hazard
- **WHEN** the HTML report renders that candidate
- **THEN** the caveat and the warning are set apart, and the pagination and flag notes
  remain de-emphasized


### Requirement: A summarised count says where its detail is

The report summarises: it carries counts, aggregates and the settings behind them, not
per-site or per-allele rows. Every count whose rows the report withholds SHALL name the
export that holds them, and that export is the **ranked menu**, not the report export —
`report_to_json` serializes the same summary the page shows.

The off-target site count is the case that matters most: a safety number a reader acts on
and, without the rows, cannot check.

A note SHALL appear only where there is something to point at — no sites nominated, no
note.

#### Scenario: A candidate with nominated off-target sites
- **WHEN** a render states the site count
- **THEN** it names the ranked menu as where the site rows are

#### Scenario: A candidate with no nominated sites
- **WHEN** the count is zero or the search did not run
- **THEN** no such note is rendered


### Requirement: A caveat does not say where to look

A caveat is positioned by whichever surface renders it, and the same reasons are read on
the HTML page and on the printable sheet. A reason SHALL describe the thing it is about
rather than its location, and SHALL NOT point a reader up or down the page.

The rule is about *deictic* use. A caveat may say a score is "at or above the triage
band"; it may not say "the table below".

#### Scenario: A caveat about the outcome distribution
- **WHEN** a nuclease candidate's outcome is the NHEJ spectrum
- **THEN** the caveat names the distribution without saying where on the page it is


### Requirement: No block moves the page sideways

Content wider than the column SHALL be bounded by its own container. Prose — the
rationale — SHALL wrap; a DNA block SHALL keep its lines and scroll inside its own box,
because a spacer broken across two lines is one someone mis-copies into an order form.
Neither SHALL cause the document to scroll horizontally.

#### Scenario: A long rationale
- **WHEN** the report renders a rationale wider than the column
- **THEN** it wraps, and the document does not scroll sideways


### Requirement: The printable sheet fits the paper

Line breaking in the PDF SHALL be measured against the font's advance widths, not counted
in characters: Helvetica is proportional, and a fixed character count that suits lowercase
prose overflows for upper-case DNA. No emitted line SHALL exceed the text column.

A token wider than the column — an HDR donor is a single unbroken token — SHALL be broken
at the last character that fits and SHALL reassemble exactly across its lines. A wrapped
sequence is recoverable; a truncated one is a mis-ordered reagent.

#### Scenario: A long HDR donor on the order sheet
- **WHEN** the printable sheet renders a donor longer than one line
- **THEN** every line fits the column and the sequence reassembles across them

#### Scenario: A section rule
- **WHEN** a horizontal rule is drawn
- **THEN** it fills the column without exceeding it


### Requirement: The chart scales with its container

The charts are inlined SVG and carry their own `width`/`height` attributes, which outrank
any rule on the wrapper. The stylesheet SHALL therefore style the SVG element: full width,
automatic height, aspect ratio from the `viewBox`. No fixed pixel width or height SHALL be
imposed on the figure or its box.

A fixed box height around a taller drawing paints the chart over the content beneath it,
and a fixed pixel width makes the document scroll sideways on a viewport narrower than the
figure.

#### Scenario: A narrow viewport
- **WHEN** the report is opened on a viewport narrower than the chart's intrinsic width
- **THEN** the chart scales down and the document does not scroll sideways


### Requirement: A sequence is not divided by a page break

A wrapped nucleotide sequence SHALL be kept on one page. A run that would straddle a
break is moved whole to the next page; prose still flows across breaks, since holding it
back would waste pages, and a run longer than a whole page is emitted as it comes.

Pagination SHALL lose no line and SHALL NOT over-fill a page.

#### Scenario: A donor that would straddle a break
- **WHEN** a wrapped sequence would begin near the foot of a page
- **THEN** the whole run starts on the next page
