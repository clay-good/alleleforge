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
