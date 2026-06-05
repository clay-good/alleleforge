"""CRISPR-Bench (Phase 14): the standardized guide-design benchmark.

CRISPR-Bench is AlleleForge's sister deliverable and a field-level contribution:
versioned datasets, **frozen, content-hashed splits**, a fixed five-task contract,
a metric battery with **calibration (ECE) required on every task**, a runner that
scores any :class:`~alleleforge.scoring.base.Scorer` into a *signed* result, and a
model-card-gated leaderboard. It is valuable on its own — a common yardstick for
the field — independent of the rest of AlleleForge.

The package is intentionally **pure-Python and dependency-light** so it runs in
the same CI as the core library. The datasets shipped in the repository are small
**synthetic fixtures**; the real public corpora (Rule Set 3, FORECasT, BE-Hive,
PRIDICT2, GUIDE-seq) are fetched at runtime through the consent-gated registry.

Note on layout: the spec sketches a top-level ``benchmark/`` tree. It lives here
as :mod:`alleleforge.benchmark` instead so it is installed with the package,
importable by ``aforge bench``, and held to the same ``mypy --strict`` / ruff /
coverage gates as the rest of the library.
"""

from __future__ import annotations

from alleleforge.benchmark.baseline import BaselineScorer, build_baseline
from alleleforge.benchmark.datasets import BenchmarkDataset, load_dataset
from alleleforge.benchmark.leaderboard import (
    Leaderboard,
    Submission,
    SubmissionError,
)
from alleleforge.benchmark.runner import (
    HIGHER_IS_BETTER,
    BenchmarkResult,
    BenchScorer,
    GeneralizationGap,
    ModelInfo,
    evaluate_fold,
    generalization_gap,
    run_benchmark,
)
from alleleforge.benchmark.splits import Split, SplitIntegrityError, load_split
from alleleforge.benchmark.tasks import TASKS, Example, Task, TaskKind, get_task

__all__ = [
    "HIGHER_IS_BETTER",
    "TASKS",
    "BaselineScorer",
    "BenchScorer",
    "BenchmarkDataset",
    "BenchmarkResult",
    "Example",
    "GeneralizationGap",
    "Leaderboard",
    "ModelInfo",
    "Split",
    "SplitIntegrityError",
    "Submission",
    "SubmissionError",
    "Task",
    "TaskKind",
    "build_baseline",
    "evaluate_fold",
    "generalization_gap",
    "get_task",
    "load_dataset",
    "load_split",
    "run_benchmark",
]
