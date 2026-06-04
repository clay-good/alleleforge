# Reporting & oligo output

Phase 11 turns a ranked design menu into the artifacts users actually consume:
cloning-ready oligos, a structured report model, machine-readable exports, an
interactive HTML page, and a static print-ready PDF. Every render **leads with
the research-use disclaimer and ends with full provenance**.

!!! note "Dependency-free by design"
    The whole phase ships in pure Python. HTML charts are **interactive Plotly**
    pulled from a CDN with each figure's spec inlined as JSON — no Python
    plotting dependency, and no sequence data ever leaves the page. The PDF is a
    small, self-contained writer (no weasyprint / reportlab). Only Parquet
    export has an optional dependency (`polars`), imported lazily.

## Cloning oligos

`oligos_for(candidate)` dispatches by chemistry to produce annealed oligo
duplexes ready to order. The cardinal invariant, enforced on construction and by
`reconstruct()`, is that **round-tripping the oligos recovers the intended
spacer / RTT / PBS**.

| Chemistry | Oligos | Default scheme |
|---|---|---|
| SpCas9 sgRNA | one duplex (5' overhangs + U6 `G`) | `LENTIGUIDE_BSMBI` |
| Base-editor sgRNA | one duplex (same as sgRNA) | `LENTIGUIDE_BSMBI` |
| pegRNA | spacer duplex + 3' extension duplex (RTT + PBS + epegRNA motif) + ngRNA duplex | `PEGRNA_GG_BSAI` |

::: alleleforge.report.oligos

## Report model

::: alleleforge.report.builder

## Machine-readable export

JSON is lossless (the full report, or the underlying ranked menu validated
against the Phase 1 schemas); TSV is one flat row per candidate; Parquet is the
columnar batch form.

::: alleleforge.report.export

## HTML render

::: alleleforge.report.html

## PDF render

::: alleleforge.report.pdf
