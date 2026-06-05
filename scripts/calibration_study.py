#!/usr/bin/env python
"""Calibration study: regenerate the CRISPR-Bench calibration report (R5).

Two regenerable, deterministic-from-seed outputs:

1. **Per-task calibration table** — every CRISPR-Bench task's primary metric and
   its **ECE** (the honesty metric required on every task), measured against the
   reference baseline on the frozen splits.
2. **Conformal interval-recalibration demonstration** — on a deliberately
   miscalibrated regression set, the empirical interval coverage *before* and
   *after* :class:`~alleleforge.scoring.uncertainty.ConformalCalibrator` at the
   spec's interval levels, showing the split-conformal guarantee restore coverage
   to its nominal target.

On real weights (R1) the per-task numbers become the published reproduction; the
machinery and the report regenerate identically here on the weight-free splits.

Usage:
    python scripts/calibration_study.py            # print the markdown report
    python scripts/calibration_study.py --out PATH  # also write it to PATH
"""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alleleforge.benchmark import (
    TASKS,
    build_baseline,
    generalization_gap,
    get_task,
    load_split,
    run_benchmark,
)
from alleleforge.scoring.uncertainty import (
    ConformalCalibrator,
    empirical_coverage,
    to_prediction,
)
from alleleforge.types.prediction import UncertaintyMethod

#: Fixed run timestamp so the benchmark provenance is stable across runs.
FIXED_TS = datetime(2024, 5, 1, tzinfo=UTC)

#: Interval levels the recalibration demonstration targets.
LEVELS = (0.80, 0.90)

#: Seed for the synthetic miscalibrated set (deterministic across runs/platforms).
SEED = 20240501


def task_calibration_table() -> list[dict[str, Any]]:
    """Run every task against the baseline and collect its primary metric + ECE."""
    rows: list[dict[str, Any]] = []
    for name in TASKS:
        task = get_task(name)
        split, dataset = load_split(name)
        baseline = build_baseline(task, split, dataset)
        result = run_benchmark(baseline, task, split=split, dataset=dataset, timestamp=FIXED_TS)
        rows.append(
            {
                "task": name,
                "kind": task.kind.value,
                "primary_metric": result.primary_metric,
                "primary_value": round(result.primary_value, 4),
                "ece": round(result.metrics["ece"], 4),
            }
        )
    return rows


def generalization_table() -> list[dict[str, Any]]:
    """Quantify the cross-cell-type generalization gap for each stratified task."""
    rows: list[dict[str, Any]] = []
    for name in TASKS:
        task = get_task(name)
        split, dataset = load_split(name)
        by_id = {e.example_id: e for e in dataset.examples}
        # Only cell-type-stratified tasks have a cross-cell-type gap (off-target is
        # stratified by sequence pair, not cellular context).
        test_contexts = {by_id[i].inputs.get("cell_type") for i in split.test if i in by_id}
        val_contexts = {by_id[i].inputs.get("cell_type") for i in split.val if i in by_id}
        held_out = {c for c in test_contexts - val_contexts if c}
        if not any(test_contexts):
            continue
        baseline = build_baseline(task, split, dataset)
        gap = generalization_gap(baseline, task, split=split, dataset=dataset)
        rows.append(
            {
                "task": name,
                "metric": gap.primary_metric,
                "in_context": round(gap.in_context, 4),
                "held_out": round(gap.held_out, 4),
                "gap": round(gap.gap, 4),
                "held_out_context": ",".join(sorted(held_out)) or "(unlabeled)",
            }
        )
    return rows


def conformal_demo() -> list[dict[str, Any]]:
    """Recalibrate a deliberately-narrow interval set; report coverage before/after."""
    rng = random.Random(SEED)

    def generate(n: int, half: float, sigma: float) -> tuple[list[Any], list[float]]:
        preds, truths = [], []
        for _ in range(n):
            center = rng.uniform(0.0, 1.0)
            truths.append(center + rng.gauss(0.0, sigma))
            # An interval far too narrow for the true spread -> badly under-covers.
            preds.append(
                to_prediction(
                    center, (center - half, center + half), method=UncertaintyMethod.ENSEMBLE
                )
            )
        return preds, truths

    cal_p, cal_y = generate(600, half=0.05, sigma=0.2)
    test_p, test_y = generate(2000, half=0.05, sigma=0.2)
    raw = empirical_coverage(test_p, test_y)
    rows: list[dict[str, Any]] = []
    for level in LEVELS:
        calibrator = ConformalCalibrator(level=level).fit(cal_p, cal_y)
        recalibrated = [calibrator.calibrate(p) for p in test_p]
        rows.append(
            {
                "level": level,
                "raw_coverage": round(raw, 3),
                "recalibrated_coverage": round(empirical_coverage(recalibrated, test_y), 3),
                "scale": round(calibrator.scale, 3),
            }
        )
    return rows


def render_markdown(
    tasks: list[dict[str, Any]], generalization: list[dict[str, Any]], demo: list[dict[str, Any]]
) -> str:
    """Render the calibration report as markdown."""
    lines = [
        "# CRISPR-Bench calibration report",
        "",
        "Regenerated by `scripts/calibration_study.py` from config + seed.",
        "",
        "## Per-task calibration (baseline, frozen splits)",
        "",
        "| Task | Kind | Primary | Value | ECE |",
        "|---|---|---|---:|---:|",
    ]
    for r in tasks:
        lines.append(
            f"| {r['task']} | {r['kind']} | {r['primary_metric']} | "
            f"{r['primary_value']} | {r['ece']} |"
        )
    lines += [
        "",
        "## Cross-cell-type generalization gap",
        "",
        "Primary metric on an in-context fold (a training-seen cell type) vs the",
        "held-out cell type. A positive gap means the model generalizes *worse* to",
        "the unseen context — a field-wide reality, reported, not hidden.",
        "",
        "| Task | Metric | In-context | Held-out | Gap | Held-out context |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in generalization:
        lines.append(
            f"| {r['task']} | {r['metric']} | {r['in_context']} | "
            f"{r['held_out']} | {r['gap']:+} | {r['held_out_context']} |"
        )
    lines += [
        "",
        "## Conformal interval recalibration",
        "",
        "Empirical coverage of a deliberately under-covering interval set, before and",
        "after split-conformal recalibration (synthetic, seeded). Recalibrated coverage",
        "meets the nominal level — the finite-sample guarantee.",
        "",
        "| Target level | Raw coverage | Recalibrated coverage | Width scale |",
        "|---:|---:|---:|---:|",
    ]
    for r in demo:
        lines.append(
            f"| {r['level']:.2f} | {r['raw_coverage']} | "
            f"{r['recalibrated_coverage']} | {r['scale']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Regenerate and print (optionally write) the calibration report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="also write the report to this path")
    args = parser.parse_args(argv)

    report = render_markdown(task_calibration_table(), generalization_table(), conformal_demo())
    if args.out is not None:
        args.out.write_text(report)
        print(f"wrote {args.out}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
