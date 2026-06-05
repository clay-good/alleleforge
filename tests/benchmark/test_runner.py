"""The runner scores stub models end to end and signs the result (Phase 14)."""

from __future__ import annotations

from datetime import datetime

import pytest

from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.datasets import load_dataset
from alleleforge.benchmark.runner import run_benchmark
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import TASKS, get_task

from .conftest import StubClassifierScorer, StubDistributionScorer, StubRegressionScorer


def test_regression_task_end_to_end(fixed_ts: datetime) -> None:
    result = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    assert result.task == "cas9-efficiency"
    assert result.n_test > 0
    assert set(result.metrics) == {"spearman", "pearson", "ece"}
    assert result.primary_metric == "spearman"
    assert result.verify_signature()
    # Provenance carries the dataset and the model checkpoint.
    assert result.provenance.datasets and result.provenance.models
    assert result.model.name == "stub-regression"


def test_classification_task_end_to_end(fixed_ts: datetime) -> None:
    result = run_benchmark(StubClassifierScorer(), "offtarget-classification", timestamp=fixed_ts)
    assert set(result.metrics) == {"auroc", "auprc", "ece"}
    assert 0.0 <= result.metrics["auroc"] <= 1.0
    assert result.verify_signature()


def test_distribution_task_end_to_end(fixed_ts: datetime) -> None:
    # Predict the dataset marginal so KL is finite and top1 is meaningful.
    ds = load_dataset("forecast-outcomes")
    cats = sorted({c for e in ds.examples for c in dict(e.label)})
    uniform = {c: 1.0 / len(cats) for c in cats}
    result = run_benchmark(StubDistributionScorer(uniform), "cas9-outcome", timestamp=fixed_ts)
    assert set(result.metrics) == {"kl", "top1", "ece"}
    assert result.metrics["kl"] >= 0.0
    assert result.verify_signature()


def test_signature_is_reproducible(fixed_ts: datetime) -> None:
    a = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    b = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    assert a.signature == b.signature


def test_tampered_result_fails_signature(fixed_ts: datetime) -> None:
    result = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    tampered = result.model_copy(update={"primary_value": 0.999})
    assert not tampered.verify_signature()


def test_out_of_distribution_count_is_reported(fixed_ts: datetime) -> None:
    result = run_benchmark(
        StubRegressionScorer(in_distribution=False), "cas9-efficiency", timestamp=fixed_ts
    )
    assert result.n_out_of_distribution == result.n_test


def test_run_accepts_task_object_and_preloaded_split(fixed_ts: datetime) -> None:
    task = get_task("pe-efficiency")
    split, dataset = load_split("pe-efficiency")
    result = run_benchmark(
        StubRegressionScorer(), task, split=split, dataset=dataset, timestamp=fixed_ts
    )
    assert result.dataset == dataset.name


@pytest.mark.parametrize("task_name", list(TASKS))
def test_reference_baseline_runs_on_every_task(task_name: str, fixed_ts: datetime) -> None:
    task = get_task(task_name)
    split, dataset = load_split(task_name)
    baseline = build_baseline(task, split, dataset)
    result = run_benchmark(baseline, task, split=split, dataset=dataset, timestamp=fixed_ts)
    assert "ece" in result.metrics  # calibration on every task
    assert result.model.name == "crispr-bench-baseline"
    assert result.verify_signature()
