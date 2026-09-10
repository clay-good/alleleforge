# Reporting & oligo output

Phase 11 turns a ranked design menu into the artifacts users actually consume:
cloning-ready oligos, a structured report model, machine-readable exports, an
interactive HTML page, and a static print-ready PDF. Every render **leads with
the research-use disclaimer and ends with full provenance**.

!!! note "Dependency-free by design"
    The whole phase ships in pure Python. HTML charts are **inlined SVG** from
    AlleleForge's own dependency-free renderer — no Python plotting dependency,
    and a rendered report makes no network request at all. The PDF is a
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
| SpCas9 sgRNA for a **precise** intent | the duplex **plus** the HDR repair template as a single-stranded `DonorOligo` | `LENTIGUIDE_BSMBI` |

A precise nuclease candidate is ordered as a *pair*: the break alone corrects
nothing, so the donor rides on `SgRnaOligos.donor` and its ordering hazards are
promoted into the same prominent `warnings` list the guide's use — a donor longer
than a vendor synthesizes as one oligo (order it as a dsDNA fragment instead), or a
repaired product still cuttable by its own guide. A donor containing an ambiguous
base is refused rather than ordered: unlike a spacer, a repair template's bases are
written into the genome permanently.

::: alleleforge.report.oligos

## Report model

::: alleleforge.report.builder

## Machine-readable export

There are two JSON forms and the difference matters. `menu_to_json` writes the ranked
menu and is the **lossless** one: everything the design produced, including each
candidate's full outcome spectrum and its off-target site rows (`aforge design --json`
writes it). `report_to_json` writes the report, which is a *summary* — every candidate,
with counts and aggregates in place of those rows — so it is complete as a serialization
of the report and is not where to look for detail the report withheld; the renders say so
wherever they withhold something. Both validate against the Phase 1 schemas. TSV is one
flat row per candidate; Parquet is the columnar batch form.

::: alleleforge.report.precision

::: alleleforge.report.export

## HTML render

Both human-facing renders draw the top `max_candidates` (default 50) **plus every
Pareto-front candidate whatever its rank**, and state on the page how many were
withheld and where the full set is. The cap exists because one prime design
routinely yields several hundred candidates — every PBS × RTT-homology × PAM
combination is a distinct pegRNA — and an uncapped page runs to megabytes. The
Pareto exception is not a nicety: the front is the report's whole answer to *"I
weight the objectives differently from your defaults"*, so a candidate optimal on
safety but 200th on the composite score is exactly the one such a reader opened the
report for. The two renders share
[`visible_candidates`][alleleforge.report.builder.visible_candidates] so they cannot
drift apart on that guarantee. This cap shapes the render only: every candidate *in the
menu* is in the JSON, TSV and Parquet forms whatever it is set to. The separate
`max_candidates_per_chemistry` cap is a data one — it removes candidates before the menu
exists, so they are in no export either, and the rationale says how many.

::: alleleforge.report.html

## PDF render

::: alleleforge.report.pdf
