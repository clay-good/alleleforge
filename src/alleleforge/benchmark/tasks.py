"""CRISPR-Bench task contracts — the five standardized prediction tasks.

A :class:`Task` fixes the *contract* a model is scored against: which dataset it
draws from, how an :class:`Example` becomes a scorer input, what shape the label
takes, and which metrics decide the ranking. Tasks are pure data (pydantic
models) so they serialize into a result's provenance and a leaderboard entry.

The five tasks span every chemistry AlleleForge designs for, plus off-target:

======================  ============  =================================  =====================
Task                    Kind          Label                              Primary metric
======================  ============  =================================  =====================
``cas9-efficiency``     regression    float cleavage efficiency [0, 1]   Spearman
``cas9-outcome``        distribution  indel outcome frequencies          KL divergence (↓)
``be-outcome``          distribution  base-edit outcome frequencies      KL divergence (↓)
``pe-efficiency``       regression    float pegRNA efficiency [0, 1]      Spearman
``offtarget-class``     classification 0/1 bona-fide off-target          AUROC
======================  ============  =================================  =====================

Calibration (``ece``) is reported on **every** task regardless of kind — the
honesty metric is not optional.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class TaskKind(StrEnum):
    """The label shape of a task, which selects its metric battery."""

    REGRESSION = "regression"
    DISTRIBUTION = "distribution"
    CLASSIFICATION = "classification"


class Example(BaseModel):
    """One scored row: an id, the scorer input(s), and the ground-truth label.

    Attributes:
        example_id: Stable identifier, referenced by frozen splits.
        inputs: Named inputs; the task's ``input_key`` selects what is passed to
            :meth:`~alleleforge.scoring.base.Scorer.score`.
        label: The ground truth — a float (regression), a 0/1 int
            (classification), or a category→frequency mapping (distribution).
    """

    model_config = ConfigDict(frozen=True)

    example_id: str
    inputs: dict[str, Any]
    label: Any

    def scorer_input(self, input_key: str) -> Any:
        """Return the value passed to a scorer for ``input_key``.

        Raises:
            KeyError: If ``input_key`` is absent from :attr:`inputs`.
        """
        if input_key not in self.inputs:
            raise KeyError(f"example {self.example_id!r} has no input {input_key!r}")
        return self.inputs[input_key]


class Task(BaseModel):
    """A frozen task contract binding a dataset, input shape, and metrics.

    Attributes:
        name: The task identifier (e.g. ``"cas9-efficiency"``).
        kind: The label shape, which selects the metric battery.
        description: One-line human description.
        chemistry: The chemistry the task probes (``None`` for off-target).
        dataset: The benchmark dataset name the examples are drawn from.
        input_key: The :attr:`Example.inputs` key passed to a scorer.
        metrics: The metric keys reported, ordered with the primary first.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    kind: TaskKind
    description: str
    chemistry: str | None
    dataset: str
    input_key: str
    metrics: tuple[str, ...]

    @property
    def primary_metric(self) -> str:
        """Return the metric the leaderboard ranks by (the first listed)."""
        return self.metrics[0]


#: The five canonical CRISPR-Bench tasks, keyed by name. ``ece`` is appended to
#: every metric tuple because calibration is required on every task.
TASKS: dict[str, Task] = {
    "cas9-efficiency": Task(
        name="cas9-efficiency",
        kind=TaskKind.REGRESSION,
        description="Predict SpCas9 on-target cleavage efficiency from guide context.",
        chemistry="cas9_nuclease",
        dataset="rs3-validation",
        input_key="context",
        metrics=("spearman", "pearson", "ece"),
    ),
    "cas9-outcome": Task(
        name="cas9-outcome",
        kind=TaskKind.DISTRIBUTION,
        description="Predict the SpCas9 repair-outcome (indel) distribution at a cut site.",
        chemistry="cas9_nuclease",
        dataset="forecast-outcomes",
        input_key="context",
        metrics=("kl", "top1", "ece"),
    ),
    "be-outcome": Task(
        name="be-outcome",
        kind=TaskKind.DISTRIBUTION,
        description="Predict the base-editing outcome distribution within the edit window.",
        chemistry="base_abe",
        dataset="be-hive-outcomes",
        input_key="context",
        metrics=("kl", "top1", "ece"),
    ),
    "pe-efficiency": Task(
        name="pe-efficiency",
        kind=TaskKind.REGRESSION,
        description="Predict prime-editing efficiency from pegRNA + target features.",
        chemistry="prime",
        dataset="pridict2-library",
        input_key="context",
        metrics=("spearman", "pearson", "ece"),
    ),
    "offtarget-classification": Task(
        name="offtarget-classification",
        kind=TaskKind.CLASSIFICATION,
        description="Classify candidate sites as bona-fide off-targets (GUIDE-seq validated).",
        chemistry=None,
        dataset="guideseq-offtarget",
        input_key="pair",
        metrics=("auroc", "auprc", "ece"),
    ),
}


def get_task(name: str) -> Task:
    """Return the task named ``name``.

    Raises:
        KeyError: If no task by that name is defined.
    """
    if name not in TASKS:
        raise KeyError(f"unknown task {name!r}; known: {tuple(sorted(TASKS))}")
    return TASKS[name]
