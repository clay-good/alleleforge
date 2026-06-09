"""Deterministic calibration & generalization computations for CRISPR-Bench (R5).

Three regenerable, deterministic-from-seed result tables, shared by the markdown
report (`scripts/calibration_study.py`) and the SVG figures (`alleleforge.viz`):

1. :func:`task_calibration_table` — every task's primary metric and its **ECE**
   (the honesty metric required on every task), against the reference baseline on
   the frozen splits.
2. :func:`generalization_table` — the **cross-cell-type generalization gap** for
   each cell-type-stratified task (in-context vs held-out cellular context).
3. :func:`conformal_demo` — empirical interval coverage *before* and *after*
   :class:`~alleleforge.scoring.uncertainty.ConformalCalibrator` on a deliberately
   miscalibrated regression set, at the spec's interval levels.

On real weights (R1) the per-task numbers become the published reproduction; the
machinery regenerates identically here on the weight-free splits.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any

from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.runner import generalization_gap, run_benchmark
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import TASKS, get_task
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
