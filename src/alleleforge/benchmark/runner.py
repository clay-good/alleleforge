"""CRISPR-Bench runner — score any ``Scorer`` against a (task, split) pair.

The runner is the join point between AlleleForge's uncertainty contract and the
benchmark: it feeds each test example to a :class:`~alleleforge.scoring.base.Scorer`,
collects the calibrated :class:`~alleleforge.types.prediction.Prediction` it
returns (never a bare float — the contract is enforced at the seam), computes the
task's metric battery plus the required calibration metric, and emits a
**signed, provenance-stamped** :class:`BenchmarkResult`.

"Signed" means content-addressed: the ``signature`` is a SHA-256 over the whole
result body (model card, metrics, split version, provenance) minus the signature
field itself, so any later edit to a published result is detectable. With a fixed
seed and timestamp the signature is reproducible, which is the point.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from alleleforge._version import __version__
from alleleforge.benchmark._canon import content_hash
from alleleforge.benchmark.datasets import BenchmarkDataset, load_dataset
from alleleforge.benchmark.metrics import (
    expected_calibration_error,
    interval_calibration_error,
    kl_divergence,
    pearson,
    pr_auc,
    roc_auc,
    spearman,
    topk_accuracy,
)
from alleleforge.benchmark.splits import Split, load_split
from alleleforge.benchmark.tasks import Example, Task, TaskKind, get_task
from alleleforge.config import DEFAULT_SEED
from alleleforge.model_zoo.registry import ModelCard
from alleleforge.scoring.base import ensure_prediction
from alleleforge.types.prediction import Prediction
from alleleforge.types.provenance import Provenance


@runtime_checkable
class BenchScorer(Protocol):
    """A scorer the benchmark can evaluate on any task kind.

    Broader than the library's efficiency-only
    :class:`~alleleforge.scoring.base.Scorer` (which fixes ``Prediction[float]``):
    a benchmark scorer may return a ``Prediction`` whose value is a float
    (regression / classification) or an outcome distribution (a category→mass
    mapping). Every efficiency scorer in AlleleForge already conforms.
    """

    name: str

    def model_card(self) -> ModelCard:
        """Return the model card documenting this scorer."""
        ...

    def score(self, x: Any) -> Prediction[Any]:
        """Return a calibrated prediction for input ``x``."""
        ...


class ModelInfo(BaseModel):
    """The minimal model-card facts a leaderboard entry must carry."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    license: str
    citation: str
    chemistry: str | None = None


class BenchmarkResult(BaseModel):
    """A signed, provenance-stamped evaluation of one model on one (task, split).

    Attributes:
        task: The task name.
        split_version: The frozen split version evaluated against.
        dataset: The dataset the split partitions.
        n_test: Number of test-fold examples scored.
        metrics: Metric name → value, including ``"ece"``.
        primary_metric: The task's ranking metric.
        primary_value: The value of the primary metric.
        n_out_of_distribution: How many predictions the model self-flagged OOD.
        model: The evaluated model's card facts.
        provenance: The full reproducibility block.
        signature: Content hash over this record (minus the signature itself).
    """

    model_config = ConfigDict(frozen=True)

    task: str
    split_version: str
    dataset: str
    n_test: int
    metrics: dict[str, float]
    primary_metric: str
    primary_value: float
    n_out_of_distribution: int
    model: ModelInfo
    provenance: Provenance
    signature: str

    def verify_signature(self) -> bool:
        """Return ``True`` if the stored signature matches the recomputed one."""
        body = self.model_dump(mode="json")
        body.pop("signature", None)
        return content_hash(body) == self.signature


def _regression_metrics(
    predictions: list[Prediction[Any]], labels: list[float]
) -> dict[str, float]:
    """Compute Spearman, Pearson, and interval-calibration ECE for regression.

    Interval calibration is only well-defined against a single nominal level, so
    the predictions are grouped by their ``interval_level`` and the ECE is the
    count-weighted mean of the per-level calibration error. A homogeneous batch —
    the common case, every scorer using the settings interval level — is one
    group and reduces exactly to the single-nominal computation; a scorer that
    mixes levels in one batch is now scored correctly instead of silently
    comparing every interval against the first prediction's level.
    """
    preds = [float(p.value) for p in predictions]
    by_level: dict[float, tuple[list[tuple[float, float]], list[float]]] = {}
    for p, y in zip(predictions, labels, strict=True):
        ivals, truths = by_level.setdefault(p.interval_level, ([], []))
        ivals.append(p.interval)
        truths.append(float(y))
    ece = (
        sum(
            len(truths) * interval_calibration_error(ivals, truths, nominal=level)
            for level, (ivals, truths) in by_level.items()
        )
        / len(predictions)
        if predictions
        else 0.0
    )
    return {
        "spearman": spearman(labels, preds),
        "pearson": pearson(labels, preds),
        "ece": ece,
    }


def _classification_metrics(
    predictions: list[Prediction[Any]], labels: list[int]
) -> dict[str, float]:
    """Compute AUROC, AUPRC, and binned ECE for binary classification."""
    scores = [float(p.value) for p in predictions]
    confidences: list[float] = []
    correct: list[int] = []
    for s, y in zip(scores, labels, strict=True):
        pred_class = 1 if s >= 0.5 else 0
        confidences.append(s if pred_class == 1 else 1.0 - s)
        correct.append(1 if pred_class == y else 0)
    return {
        "auroc": roc_auc(scores, labels),
        "auprc": pr_auc(scores, labels),
        "ece": expected_calibration_error(confidences, correct),
    }


def _distribution_metrics(
    predictions: list[Prediction[Any]], labels: list[dict[str, float]]
) -> dict[str, float]:
    """Compute mean KL, top-1 mode accuracy, and predicted-mode reliability ECE."""
    kls: list[float] = []
    top1s: list[float] = []
    confidences: list[float] = []
    correct: list[int] = []
    for p, observed in zip(predictions, labels, strict=True):
        predicted: dict[str, float] = dict(p.value)
        kls.append(kl_divergence(observed, predicted))
        top1s.append(topk_accuracy(predicted, observed, k=1))
        if predicted and observed:
            mode = max(sorted(predicted), key=lambda c: predicted[c])
            confidences.append(predicted[mode])
            true_mode = max(sorted(observed), key=lambda c: observed[c])
            correct.append(1 if mode == true_mode else 0)
    n = len(kls)
    return {
        "kl": sum(kls) / n if n else 0.0,
        "top1": sum(top1s) / n if n else 0.0,
        "ece": expected_calibration_error(confidences, correct),
    }


def _compute_metrics(
    task: Task, predictions: list[Prediction[Any]], examples: list[Example]
) -> dict[str, float]:
    """Dispatch to the metric battery for ``task.kind``."""
    if task.kind is TaskKind.REGRESSION:
        return _regression_metrics(predictions, [float(e.label) for e in examples])
    if task.kind is TaskKind.CLASSIFICATION:
        return _classification_metrics(predictions, [int(e.label) for e in examples])
    return _distribution_metrics(predictions, [dict(e.label) for e in examples])


#: Whether each metric ranks better when larger. Lower-is-better metrics (an
#: error or a divergence) flip the generalization-gap orientation so a positive
#: gap always means *worse* held-out performance.
HIGHER_IS_BETTER: dict[str, bool] = {
    "spearman": True,
    "pearson": True,
    "auroc": True,
    "auprc": True,
    "top1": True,
    "kl": False,
    "ece": False,
}


def evaluate_fold(
    scorer: BenchScorer,
    task: Task | str,
    split: Split,
    dataset: BenchmarkDataset,
    fold: str,
) -> dict[str, float]:
    """Run ``scorer`` over a split ``fold`` and return the task's metric battery.

    The shared evaluation primitive behind :func:`run_benchmark` (which scores the
    ``"test"`` fold) and :func:`generalization_gap` (which scores an in-context and
    a held-out fold). Each prediction is contract-checked to be a ``Prediction``.
    """
    task_obj = task if isinstance(task, Task) else get_task(task)
    examples = list(split.examples(dataset, fold))
    predictions = [
        ensure_prediction(scorer.score(ex.scorer_input(task_obj.input_key)), who=scorer.name)
        for ex in examples
    ]
    return _compute_metrics(task_obj, predictions, examples)


class GeneralizationGap(BaseModel):
    """The drop in a model's primary metric from an in-context to a held-out fold.

    Cross-cell-type generalization is a field-wide reality: a model tuned on one
    cellular context usually predicts a held-out context worse. This quantifies it
    on CRISPR-Bench's cross-context splits — the in-context fold (a cell type seen
    in training, by default ``"val"``) vs the held-out fold (a cell type held out
    entirely, by default ``"test"``).

    Attributes:
        task: The task name.
        primary_metric: The task's ranking metric the gap is measured on.
        in_context_fold / held_out_fold: The folds compared.
        in_context / held_out: The primary-metric value on each fold.
        gap: The signed gap, oriented so **positive means worse** held-out
            generalization (``in_context - held_out`` for higher-is-better metrics,
            negated for lower-is-better ones).
        higher_is_better: Whether the primary metric ranks better when larger.
    """

    model_config = ConfigDict(frozen=True)

    task: str
    primary_metric: str
    in_context_fold: str
    held_out_fold: str
    in_context: float
    held_out: float
    gap: float
    higher_is_better: bool


def generalization_gap(
    scorer: BenchScorer,
    task: Task | str,
    *,
    split: Split | None = None,
    dataset: BenchmarkDataset | None = None,
    split_version: str = "v1",
    in_context_fold: str = "val",
    held_out_fold: str = "test",
) -> GeneralizationGap:
    """Quantify ``scorer``'s cross-context generalization gap on a task.

    Args:
        scorer: The scorer to evaluate (same protocol as :func:`run_benchmark`).
        task: The task, or its name.
        split: A pre-loaded, pre-verified split (loaded from disk if omitted).
        dataset: A pre-loaded dataset (loaded from the fixture if omitted).
        split_version: Which frozen split version to load when ``split`` is None.
        in_context_fold: The fold drawn from a training-seen context (default
            ``"val"``).
        held_out_fold: The fold drawn from the held-out context (default ``"test"``).

    Returns:
        A :class:`GeneralizationGap` with the per-fold metric values and the
        orientation-corrected gap.
    """
    task_obj = task if isinstance(task, Task) else get_task(task)
    if split is None:
        split, dataset = load_split(task_obj.name, version=split_version, dataset=dataset)
    elif dataset is None:
        dataset = load_dataset(split.dataset)

    pm = task_obj.primary_metric
    in_value = evaluate_fold(scorer, task_obj, split, dataset, in_context_fold)[pm]
    held_value = evaluate_fold(scorer, task_obj, split, dataset, held_out_fold)[pm]
    higher_is_better = HIGHER_IS_BETTER[pm]
    gap = (in_value - held_value) if higher_is_better else (held_value - in_value)
    return GeneralizationGap(
        task=task_obj.name,
        primary_metric=pm,
        in_context_fold=in_context_fold,
        held_out_fold=held_out_fold,
        in_context=in_value,
        held_out=held_value,
        gap=gap,
        higher_is_better=higher_is_better,
    )


def run_benchmark(
    scorer: BenchScorer,
    task: Task | str,
    *,
    split: Split | None = None,
    dataset: BenchmarkDataset | None = None,
    split_version: str = "v1",
    seed: int = DEFAULT_SEED,
    timestamp: datetime | None = None,
) -> BenchmarkResult:
    """Evaluate ``scorer`` on a task's frozen test split and return a signed result.

    Args:
        scorer: Any object satisfying the :class:`~alleleforge.scoring.base.Scorer`
            protocol; its output is contract-checked to be a ``Prediction``.
        task: The task, or its name.
        split: A pre-loaded, pre-verified split (loaded from disk if omitted).
        dataset: A pre-loaded dataset (loaded from the fixture if omitted).
        split_version: Which frozen split version to load when ``split`` is None.
        seed: The seed recorded in provenance.
        timestamp: An explicit timestamp for a reproducible signature (tests).

    Returns:
        A signed, provenance-stamped :class:`BenchmarkResult`.
    """
    task_obj = task if isinstance(task, Task) else get_task(task)
    if split is None:
        split, dataset = load_split(task_obj.name, version=split_version, dataset=dataset)
    else:
        if dataset is None:
            dataset = load_dataset(split.dataset)
        split.verify(dataset)

    examples = list(split.examples(dataset, "test"))
    predictions = [
        ensure_prediction(scorer.score(ex.scorer_input(task_obj.input_key)), who=scorer.name)
        for ex in examples
    ]
    metrics = _compute_metrics(task_obj, predictions, examples)
    n_ood = sum(1 for p in predictions if not p.in_distribution)

    card = scorer.model_card()
    provenance = Provenance.capture(
        alleleforge_version=__version__,
        seed=seed,
        timestamp=timestamp,
        datasets=(dataset.dataset_version(),),
        models=(card.to_checkpoint(),),
        config_snapshot={"task": task_obj.name, "split_version": split.split_version},
    )
    model_info = ModelInfo(
        name=card.name,
        version=card.version,
        license=card.license,
        citation=card.citation,
        chemistry=card.chemistry,
    )

    body: dict[str, Any] = {
        "task": task_obj.name,
        "split_version": split.split_version,
        "dataset": dataset.name,
        "n_test": len(examples),
        "metrics": metrics,
        "primary_metric": task_obj.primary_metric,
        "primary_value": metrics[task_obj.primary_metric],
        "n_out_of_distribution": n_ood,
        "model": model_info.model_dump(mode="json"),
        "provenance": provenance.model_dump(mode="json"),
    }
    signature = content_hash(body)
    return BenchmarkResult(**body, signature=signature)
