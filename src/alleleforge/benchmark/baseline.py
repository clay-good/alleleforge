"""A reference baseline scorer, fit on the train fold, for every task kind.

CRISPR-Bench is only useful if there is always *something* to run. This module
provides a deterministic, dependency-free reference baseline that satisfies the
:class:`~alleleforge.scoring.base.Scorer` protocol for all five tasks, so
``aforge bench run <task>`` produces a signed result out of the box and the
leaderboard has a floor every real model is measured against.

The baselines are the classic, honest ones:

* **regression** — predict the train-fold mean, with an interval spanning the
  train-fold range (a marginal predictor: zero rank correlation by construction,
  but a calibrated interval);
* **distribution** — predict the train-fold *marginal* outcome distribution;
* **classification** — a transparent ``1 - mismatches / 6`` heuristic on the
  candidate pair (more mismatches ⇒ less likely a real off-target).
"""

from __future__ import annotations

from alleleforge.benchmark.datasets import BenchmarkDataset
from alleleforge.benchmark.splits import Split
from alleleforge.benchmark.tasks import Task, TaskKind
from alleleforge.config import DEFAULT_INTERVAL_LEVEL
from alleleforge.model_zoo.registry import ModelCard
from alleleforge.types.prediction import Prediction, UncertaintyMethod

#: Maximum mismatch count the off-target heuristic normalizes against.
_MAX_MISMATCH = 6.0

BASELINE_CARD = ModelCard(
    name="crispr-bench-baseline",
    version="1.0",
    chemistry=None,
    training_data="The (task, split) train fold marginal — no external weights.",
    metrics={},
    intended_use="A transparent reference baseline and leaderboard floor.",
    out_of_scope_use="Not a design model; never use for real guide selection.",
    license="MIT",
    citation="AlleleForge CRISPR-Bench reference baseline.",
    known_failure_modes=(
        "Predicts the train-fold marginal, so it ignores every sequence feature and "
        "cannot rank guides within a locus.",
        "Has no calibrated uncertainty and no biological signal — it exists only as a "
        "leaderboard floor.",
    ),
)


class BaselineScorer:
    """A marginal / heuristic baseline satisfying the ``Scorer`` protocol."""

    name = "crispr-bench-baseline"

    def __init__(
        self,
        kind: TaskKind,
        *,
        value: float = 0.0,
        interval: tuple[float, float] = (0.0, 1.0),
        distribution: dict[str, float] | None = None,
    ) -> None:
        """Configure the baseline for one task ``kind`` (see :func:`build_baseline`)."""
        self._kind = kind
        self._value = value
        self._interval = interval
        self._distribution = distribution or {}

    def model_card(self) -> ModelCard:
        """Return the shared baseline model card."""
        return BASELINE_CARD

    def score(self, x: object) -> Prediction[object]:
        """Return the baseline prediction appropriate to the task kind."""
        if self._kind is TaskKind.REGRESSION:
            return Prediction[object](
                value=self._value,
                interval=self._interval,
                interval_level=DEFAULT_INTERVAL_LEVEL,
                method=UncertaintyMethod.HEURISTIC,
            )
        if self._kind is TaskKind.DISTRIBUTION:
            return Prediction[object](
                value=dict(self._distribution),
                interval=(0.0, 1.0),
                method=UncertaintyMethod.HEURISTIC,
            )
        mismatches = float(x["mismatches"]) if isinstance(x, dict) else 0.0
        p = max(0.01, min(0.99, 1.0 - mismatches / _MAX_MISMATCH))
        return Prediction[object](
            value=p,
            interval=(0.0, 1.0),
            method=UncertaintyMethod.HEURISTIC,
        )


def build_baseline(task: Task, split: Split, dataset: BenchmarkDataset) -> BaselineScorer:
    """Fit the reference baseline on a (task, split)'s train fold.

    Regression and distribution baselines are fit to the train-fold marginal;
    the classification baseline is a fixed mismatch heuristic and ignores the
    fold. The returned scorer is then evaluated against the *test* fold.
    """
    train = split.examples(dataset, "train")
    if task.kind is TaskKind.REGRESSION:
        labels = [float(e.label) for e in train]
        if labels:
            mean = sum(labels) / len(labels)
            lo, hi = min(labels), max(labels)
            interval = (lo, hi) if hi > lo else (max(0.0, lo - 0.1), hi + 0.1)
        else:  # pragma: no cover - fixtures always have a train fold
            mean, interval = 0.5, (0.0, 1.0)
        mean = min(interval[1], max(interval[0], mean))
        return BaselineScorer(task.kind, value=mean, interval=interval)
    if task.kind is TaskKind.DISTRIBUTION:
        acc: dict[str, float] = {}
        for e in train:
            for cat, mass in dict(e.label).items():
                acc[cat] = acc.get(cat, 0.0) + float(mass)
        total = sum(acc.values())
        marginal = {c: v / total for c, v in acc.items()} if total > 0 else {}
        return BaselineScorer(task.kind, distribution=marginal)
    return BaselineScorer(task.kind)
