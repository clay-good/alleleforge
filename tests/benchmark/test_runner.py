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


def test_regression_ece_groups_by_interval_level() -> None:
    # Interval calibration is per nominal level. With mixed levels in one batch,
    # pooling every interval against a single nominal (the old behavior) is wrong:
    # A's 80% interval covers its truth, B's 50% interval does not, so pooling
    # gives |0.5 - 0.8| = 0.3, while the correct per-level count-weighted error is
    # (|1.0 - 0.8| + |0.0 - 0.5|) / 2 = 0.35.
    from alleleforge.benchmark.runner import _regression_metrics
    from alleleforge.types.prediction import Prediction, UncertaintyMethod

    def _pred(value: float, interval: tuple[float, float], level: float) -> Prediction[float]:
        return Prediction[float](
            value=value,
            interval=interval,
            interval_level=level,
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=True,
            calibrated=False,
        )

    # The point value sits inside its own interval; the label (5.0) is the truth
    # whose coverage is tested — inside A's (0, 10) but outside B's (0, 1).
    preds = [_pred(5.0, (0.0, 10.0), 0.8), _pred(0.5, (0.0, 1.0), 0.5)]
    assert _regression_metrics(preds, [5.0, 5.0])["ece"] == pytest.approx(0.35)


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


def test_empty_distribution_scorer_reports_undefined_ece(fixed_ts: datetime) -> None:
    # A scorer that emits {} for every example expresses no calibrated belief, so
    # its ECE is undefined (None) -- not a perfect 0.0 it never earned.
    result = run_benchmark(StubDistributionScorer({}), "cas9-outcome", timestamp=fixed_ts)
    assert result.metrics["ece"] is None
    assert result.verify_signature()


def test_signature_is_reproducible(fixed_ts: datetime) -> None:
    a = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    b = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    assert a.signature == b.signature


def test_config_snapshot_is_the_full_resolved_settings(fixed_ts: datetime) -> None:
    # The benchmark config_snapshot must be the full resolved settings (like the
    # design path), not a hand-built 2-key subset — so interval_level, which drives
    # the regression ECE the leaderboard ranks honesty by, is recorded.
    result = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    snapshot = result.provenance.config_snapshot
    assert "interval_level" in snapshot
    assert snapshot != {"task": "cas9-efficiency", "split_version": "v1"}


def test_provenance_seed_matches_config_snapshot_seed(fixed_ts: datetime) -> None:
    # A non-default seed must appear identically in both the top-level provenance seed
    # and the config_snapshot — capturing the singleton verbatim recorded the default
    # seed while provenance.seed said otherwise, a self-contradictory, non-re-derivable
    # provenance block on a signed result. The design path holds this invariant.
    result = run_benchmark(
        StubRegressionScorer(), "cas9-efficiency", seed=777, timestamp=fixed_ts
    )
    assert result.provenance.seed == 777
    assert result.provenance.config_snapshot["seed"] == 777


def test_result_binds_the_split_membership_hash(fixed_ts: datetime) -> None:
    # The result binds the exact frozen fold (split_sha256), not just the "v1"
    # label — so a re-cut split over the same rows is detectable.
    split, dataset = load_split("cas9-efficiency")
    result = run_benchmark(
        StubRegressionScorer(), "cas9-efficiency", split=split, dataset=dataset, timestamp=fixed_ts
    )
    assert result.split_sha256 == split.split_sha256
    assert result.verify_signature()


def test_reproducibility_digest_is_stable_across_timestamp(fixed_ts: datetime) -> None:
    # The reproducibility digest covers only the scientific body (metrics, model
    # facts, task, split identity, dataset) with floats rounded — NOT the wall-clock
    # timestamp or package version. So the same model on the same (task, split)
    # yields the identical digest even when the timestamp (and, by construction, the
    # release) differs, which the timestamp-sealing signature cannot confirm.
    from datetime import timedelta

    a = run_benchmark(StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts)
    b = run_benchmark(
        StubRegressionScorer(), "cas9-efficiency", timestamp=fixed_ts + timedelta(days=1)
    )
    assert a.reproducibility_digest == b.reproducibility_digest  # scientific body identical
    assert a.signature != b.signature  # but the tamper seal reflects the changed timestamp


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
