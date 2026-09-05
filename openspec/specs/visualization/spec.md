# visualization Specification

## Purpose

Render committed, byte-reproducible SVG figures for the docs and methods preprint from the
weight-free deterministic pipeline, with no plotting-stack dependency, so the calibration
and reference-bias evidence is regenerable and citable.

## Requirements

### Requirement: Figures regenerate byte-for-byte

Figures SHALL regenerate byte-for-byte from config and seed: deterministic number
formatting, no timestamps, no random ids.

#### Scenario: Re-render stability
- **WHEN** a figure is regenerated from the same inputs
- **THEN** its bytes are identical to the committed version

### Requirement: The committed figure set is derived from the benchmark tables

The committed set SHALL be the reference-bias, conformal-coverage, per-task ECE, and
generalization-gap figures, each derived from the same deterministic tables the benchmark
uses, with ECE flagged against its threshold.

#### Scenario: ECE threshold
- **WHEN** the per-task ECE figure is rendered
- **THEN** tasks exceeding the ECE threshold are visually flagged

### Requirement: Chart primitives validate and escape input

`bar_chart` SHALL raise if any series length does not match the category count, escape all
text nodes, and draw an emphasized zero baseline when the value range spans negatives. Every
value that reaches an SVG **attribute** rather than a text node — the `Series`/`ReferenceLine`
`color` — SHALL be validated to a hex code or a bare CSS color name at construction, since the
text-node escaper does not cover attributes: an unvalidated color carrying `"`/`<`/`>`/`&`
would break out of the `fill=`/`stroke=` attribute (the same injection class the text escaping
closes on the text-node surface).

#### Scenario: Length mismatch
- **WHEN** a series length differs from the category count
- **THEN** `bar_chart` raises `ValueError`

#### Scenario: Signed range
- **WHEN** values span negative and positive
- **THEN** an emphasized zero baseline is drawn and negative bars grow downward

#### Scenario: Color with markup is rejected
- **WHEN** a `Series` or `ReferenceLine` is constructed with a color that is not a hex code
  or a bare CSS name (e.g. one containing a quote or `<script>`)
- **THEN** construction raises `ValueError`, so a color can never break out of the SVG
  attribute it is interpolated into

### Requirement: Committed figures are a current render

The SVGs committed under `docs/assets/figures/` are embedded in the README and the
preprint, so a stale one shows numbers the pipeline no longer produces to a reader
with no way to tell. They SHALL be a current render: a test SHALL fail when any
committed figure differs from a fresh one, naming the stale files and the command
that regenerates them. The renderer's determinism is what makes that check
meaningful rather than flaky, and is required for the same reason.

#### Scenario: A figure's inputs change
- **WHEN** the pipeline that produces a figure changes and the committed SVGs are
  not regenerated
- **THEN** the freshness test fails and names the stale files

### Requirement: A figure states where its data came from

A figure travels further from its explanation than any other artifact — into a slide, an
issue, a paper — so a caveat in the surrounding document does not accompany it. Every
committed figure SHALL state in the figure itself whether its numbers come from bundled
synthetic fixtures, a seeded demonstration set, or a constructed locus, and SHALL do so
conditionally on the data actually being such, so the note disappears when real data
arrives rather than becoming permanent furniture.

A figure drawing a reference line SHALL be checked that what the line crosses is on the
same footing as the line: a real threshold across synthetic bars reads as a measurement.

#### Scenario: A chart of fixture metrics
- **WHEN** a figure plots metrics computed on the bundled synthetic datasets
- **THEN** its subtitle says so, and says the figure shows the measurement machinery
  rather than a model's performance
