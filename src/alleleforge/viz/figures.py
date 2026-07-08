"""Reproducible SVG figures for the AlleleForge docs and methods preprint.

Each figure is computed from the **weight-free, deterministic** pipeline — the
same code paths the acceptance suite and CRISPR-Bench exercise — and rendered to a
committed SVG by :mod:`alleleforge.viz.svg`. Nothing here needs real weights, a
network, or a plotting library, so the figures regenerate byte-for-byte from
config plus seed (``python scripts/figures.py``).

Four figures:

* :func:`reference_bias_figure` — the headline: a reference-only off-target scan
  finds nothing where a population-aware scan nominates a high-CFD site.
* :func:`conformal_coverage_figure` — split-conformal recalibration restores
  interval coverage to its nominal target.
* :func:`task_ece_figure` — per-task calibration error (ECE) across CRISPR-Bench.
* :func:`generalization_gap_figure` — the cross-cell-type generalization gap.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from alleleforge.benchmark.calibration import (
    conformal_demo,
    generalization_table,
    task_calibration_table,
)
from alleleforge.config import get_settings
from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.viz.svg import PALETTE, ReferenceLine, Series, bar_chart

#: The calibration error above which a task's intervals are flagged miscalibrated.
ECE_THRESHOLD = 0.10


def reference_bias_data() -> tuple[int, int, float, dict[str, float]]:
    """Reproduce the rs114518452-style reference-bias case (weight-free, in-memory).

    Returns ``(reference_only_sites, population_aware_sites, cfd_score,
    per_ancestry_frequency)`` for the de-novo PAM the minor allele creates — the
    same scenario the acceptance suite pins in ``test_reference_bias_case_reproduced``.
    """
    import tempfile

    spacer = "GACCATGCAACCTTGAACGT"  # no internal NRG PAM: it never self-matches
    pad = "T" * 10
    ngg = PAM(pattern="NGG")
    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "refbias.fa"
        fasta.write_text(f">chr2\n{pad}{spacer}CGT{pad}\n")  # no NGG after the protospacer
        reference = ReferenceGenome(fasta, build="hg38")

        reference_only = search(spacer, ngg, reference=reference).n_sites
        allele = PopulationFrequency(
            chrom="chr2",
            pos=32,
            ref="T",
            alt="G",
            overall_af=0.03,
            populations={"afr": 0.105, "amr": 0.012, "eas": 0.0, "nfe": 0.001, "sas": 0.0},
        )
        report = search(spacer, ngg, reference=reference, gnomad=GnomadDB([allele]))
        site = report.sites[0]
        return reference_only, report.n_sites, round(site.score, 3), dict(site.ancestries)


def reference_bias_figure() -> str:
    """Render the reference-bias headline figure."""
    ref_only, pop_aware, cfd, ancestries = reference_bias_data()
    afr = ancestries.get("afr", 0.0)
    return bar_chart(
        title="Reference bias, reproduced (rs114518452-style)",
        subtitle=(
            f"Reference-only finds nothing; the population-aware scan nominates a "
            f"CFD-{cfd:g} site (AFR allele freq {afr * 100:g}%)."
        ),
        categories=("Reference-only scan", "Population-aware scan"),
        series=(Series("Off-target sites found", (float(ref_only), float(pop_aware)), PALETTE[0]),),
        y_label="Sites nominated",
        y_max=2.0,
    )


def conformal_coverage_figure() -> str:
    """Render the split-conformal coverage-restoration figure."""
    rows = conformal_demo(get_settings().rng())
    categories = tuple(f"{r['level'] * 100:g}% interval" for r in rows)
    raw = tuple(round(float(r["raw_coverage"]) * 100, 1) for r in rows)
    recal = tuple(round(float(r["recalibrated_coverage"]) * 100, 1) for r in rows)
    targets = tuple(round(float(r["level"]) * 100, 1) for r in rows)
    return bar_chart(
        title="Split-conformal recalibration restores interval coverage",
        subtitle=(
            "Coverage of a deliberately under-covering interval set, before vs after "
            "recalibration. Dashed: nominal target."
        ),
        categories=categories,
        series=(
            Series("Raw coverage", raw, PALETTE[1]),
            Series("Recalibrated coverage", recal, PALETTE[2]),
        ),
        y_label="Empirical coverage",
        y_max=100.0,
        value_suffix="%",
        reference_lines=tuple(ReferenceLine(t, f"target {t:g}%") for t in dict.fromkeys(targets)),
    )


def task_ece_figure() -> str:
    """Render the per-task calibration-error (ECE) figure across CRISPR-Bench."""
    rows = task_calibration_table()
    categories = tuple(str(r["task"]) for r in rows)
    values = tuple(round(float(r["ece"]), 4) for r in rows)
    return bar_chart(
        title="Per-task calibration error (ECE) — CRISPR-Bench baseline",
        subtitle=(
            "Expected calibration error per task on the frozen weight-free splits. "
            "Dashed: the flag threshold."
        ),
        categories=categories,
        series=(Series("ECE", values, PALETTE[3]),),
        y_label="Expected calibration error",
        y_max=max(0.4, *values),
        reference_lines=(ReferenceLine(ECE_THRESHOLD, f"flag ≥ {ECE_THRESHOLD:g}"),),
    )


def generalization_gap_figure() -> str:
    """Render the cross-cell-type generalization-gap figure."""
    rows = generalization_table()
    categories = tuple(str(r["task"]) for r in rows)
    values = tuple(round(float(r["gap"]), 4) for r in rows)
    held_out = next((str(r["held_out_context"]) for r in rows), "")
    return bar_chart(
        title="Cross-cell-type generalization gap",
        subtitle=(
            f"Metric drop from a training-seen to the held-out cell type ({held_out}). "
            f"Positive = worse generalization."
        ),
        categories=categories,
        series=(Series("Generalization gap", values, PALETTE[4]),),
        y_label="Gap (held-out − in-context)",
        y_min=-0.1,
        y_max=0.1,
    )


#: The committed figure set: filename stem -> builder.
FIGURES: dict[str, Callable[[], str]] = {
    "reference_bias": reference_bias_figure,
    "conformal_coverage": conformal_coverage_figure,
    "task_ece": task_ece_figure,
    "generalization_gap": generalization_gap_figure,
}


def render_all_figures(outdir: str | Path) -> dict[str, Path]:
    """Render every figure to ``outdir`` as ``<stem>.svg``; return the written paths."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for stem, builder in FIGURES.items():
        path = out / f"{stem}.svg"
        path.write_text(builder())
        written[stem] = path
    return written
