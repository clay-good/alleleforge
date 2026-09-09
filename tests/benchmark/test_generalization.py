"""Tests for the cross-cell-type generalization gap (R5)."""

from __future__ import annotations

import zlib
from typing import Any

import pytest

from alleleforge.benchmark import (
    GeneralizationGap,
    build_baseline,
    evaluate_fold,
    generalization_gap,
    get_task,
    load_split,
)
from alleleforge.model_zoo.registry import ModelCard
from alleleforge.types.prediction import Prediction, UncertaintyMethod


def _card() -> ModelCard:
    return ModelCard(
        name="memorizer",
        version="0",
        chemistry=None,
        training_data="none (test stub)",
        intended_use="generalization-gap testing",
        out_of_scope_use="anything real",
        license="MIT",
        citation="AlleleForge test suite",
        known_failure_modes=("documented test failure mode",),
    )


class _Constant:
    """A scorer that predicts one value for everything, like the shipped baseline."""

    name = "constant"

    def model_card(self) -> ModelCard:
        return _card()

    def score(self, x: Any) -> Prediction[Any]:
        return Prediction[float](
            value=0.5, interval=(0.49, 0.51), method=UncertaintyMethod.HEURISTIC
        )


class _Memorizer:
    """Perfect on memorized contexts, near-useless but *varying* elsewhere.

    It used to answer a flat `0.5` off its memorized fold, which made this file's
    premise unmeasurable: a correlation over constant predictions is undefined, and the
    "large drop on the unseen cell type" it asserted was `1.0 - 0.0` where the `0.0` was
    a placeholder the metric returned for having nothing to say. The held-out answer is
    now a deterministic hash of the input — still ignorant, still terrible, but ordered,
    so the gap it produces is a measurement rather than an arithmetic artefact.
    """

    name = "memorizer"

    def __init__(self, known: dict[str, float]) -> None:
        self._known = known

    def model_card(self) -> ModelCard:
        return _card()

    def score(self, x: Any) -> Prediction[Any]:
        # `hash()` is PYTHONHASHSEED-dependent; this file must not become the one
        # place a benchmark number moves between runs.
        value = self._known.get(x, (zlib.crc32(str(x).encode()) % 1000) / 1000.0)
        return Prediction[float](
            value=value,
            interval=(value - 0.01, value + 0.01),
            method=UncertaintyMethod.HEURISTIC,
        )


def _memorize_fold(split: Any, dataset: Any, fold: str) -> dict[str, float]:
    by_id = {e.example_id: e for e in dataset.examples}
    ids = getattr(split, fold)
    return {by_id[i].inputs["context"]: float(by_id[i].label) for i in ids if i in by_id}


def test_gap_is_positive_when_held_out_is_worse() -> None:
    # A scorer that memorizes the in-context (val) labels but is ignorant on the
    # held-out (test) context must show a positive generalization gap.
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    scorer = _Memorizer(_memorize_fold(split, dataset, "val"))
    gap = generalization_gap(scorer, task, split=split, dataset=dataset)
    assert isinstance(gap, GeneralizationGap)
    assert gap.primary_metric == "spearman" and gap.higher_is_better is True
    assert gap.in_context == pytest.approx(1.0)  # perfect on the memorized fold
    assert gap.gap > 0.5  # large drop on the unseen cell type


def test_a_gap_is_refused_when_a_fold_has_no_number() -> None:
    """`0.0 - 0.0 = +0.0000` was published as a statement about generalization.

    A gap is a subtraction, so both sides must be numbers. A model that predicts one
    constant — which the shipped reference baseline does — has no rank correlation on
    either fold, and the harness used to report a clean zero gap for it.
    """
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    with pytest.raises(ValueError, match="no gap to report") as caught:
        generalization_gap(_Constant(), task, split=split, dataset=dataset)
    assert "constant value" in str(caught.value), caught.value


def test_gap_orientation_for_lower_is_better_metric() -> None:
    # For KL (lower is better) the gap is held_out - in_context, so a model that is
    # worse (higher KL) on the held-out context still yields a positive gap.
    task = get_task("cas9-outcome")
    split, dataset = load_split("cas9-outcome")
    base = build_baseline(task, split, dataset)
    gap = generalization_gap(base, task, split=split, dataset=dataset)
    assert gap.higher_is_better is False
    assert gap.gap == pytest.approx(gap.held_out - gap.in_context)


def test_evaluate_fold_runs_each_fold() -> None:
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    base = build_baseline(task, split, dataset)
    for fold in ("train", "val", "test"):
        metrics = evaluate_fold(base, task, split, dataset, fold)
        assert "spearman" in metrics and "ece" in metrics


def test_custom_folds_are_honored() -> None:
    task = get_task("pe-efficiency")
    split, dataset = load_split("pe-efficiency")
    # Not the shipped baseline: it predicts one constant, so its primary metric is
    # undefined on every fold and this check would be about the refusal rather than
    # about the fold names it claims to be testing.
    scorer = _Memorizer(_memorize_fold(split, dataset, "train"))
    gap = generalization_gap(
        scorer, task, split=split, dataset=dataset, in_context_fold="train", held_out_fold="val"
    )
    assert gap.in_context_fold == "train" and gap.held_out_fold == "val"


def test_loads_split_when_not_given() -> None:
    split, dataset = load_split("cas9-efficiency")
    scorer = _Memorizer(_memorize_fold(split, dataset, "val"))
    gap = generalization_gap(scorer, "cas9-efficiency")  # split/dataset loaded internally
    assert gap.task == "cas9-efficiency"


def test_loads_dataset_when_only_split_given() -> None:
    split, dataset = load_split("cas9-efficiency")
    scorer = _Memorizer(_memorize_fold(split, dataset, "val"))
    gap = generalization_gap(scorer, "cas9-efficiency", split=split)  # dataset resolved from split
    assert gap.in_context == pytest.approx(1.0)
