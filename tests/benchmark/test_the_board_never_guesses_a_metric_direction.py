"""A rank is a claim about direction, and the board used to guess it.

Two tables in the same package answered "does higher win?" and they answered it by
opposite defaults. `runner.HIGHER_IS_BETTER` is an allowlist: a metric it has not heard
of raises. `leaderboard.LOWER_IS_BETTER` was a hand-written denylist of `{kl, ece}`, so
a metric it had not heard of was *silently* ranked descending.

`primary_metric` is a free-form string on a submitted result. A submission ranking on
`rmse` — where lower is better — therefore ordered the worst model first and printed
`rmse ↑` beside it: the board asserting a direction it did not know, on the surface
whose whole job is comparing models honestly. Nothing failed, and the two tables were
free to drift apart besides.

The fix derives `LOWER_IS_BETTER` from the runner's table and refuses the submission
instead of guessing. These tests pin the refusal, the message that names the valid
metrics, and the completeness of the one remaining table against the shipped tasks.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from alleleforge.benchmark._canon import content_hash
from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.leaderboard import (
    LOWER_IS_BETTER,
    Leaderboard,
    Submission,
    SubmissionError,
    metric_is_descending,
)
from alleleforge.benchmark.runner import (
    HIGHER_IS_BETTER,
    BenchmarkResult,
    ModelInfo,
    reproducibility_digest,
    run_benchmark,
)
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import TASKS, get_task


def _signed_on(metric: str, value: float, name: str, ts: datetime) -> BenchmarkResult:
    """Return a validly signed result that ranks on ``metric`` — as a submitter could."""
    task = get_task("cas9-efficiency")
    split, dataset = load_split("cas9-efficiency")
    base = run_benchmark(
        build_baseline(task, split, dataset), task, split=split, dataset=dataset, timestamp=ts
    )
    fields = base.model_dump()
    fields["model"] = {**fields["model"], "name": name}
    fields["primary_metric"] = metric
    fields["primary_value"] = value
    fields["metrics"] = {**fields["metrics"], metric: value}
    unsigned = BenchmarkResult.model_validate({**fields, "signature": "pending"})
    fields["reproducibility_digest"] = reproducibility_digest(unsigned.scientific_body())
    body = BenchmarkResult.model_validate({**fields, "signature": "pending"}).model_dump(
        mode="json"
    )
    body.pop("signature")
    fields["signature"] = content_hash(body)
    result = BenchmarkResult.model_validate(fields)
    assert result.verify_signature() and result.verify_reproducibility_digest()
    return result


def test_a_submission_on_an_unknown_metric_is_refused(fixed_ts: datetime) -> None:
    """Before the fix this ranked 0.90 above 0.20 and printed `rmse ↑`."""
    result = _signed_on("rmse", 0.90, "worse-model", fixed_ts)
    model = ModelInfo(name="worse-model", version="1", license="MIT", citation="c")
    submission = Submission(submitter="x", model=model, results=(result,), submitted_at=fixed_ts)
    with pytest.raises(SubmissionError, match="unknown metric 'rmse'"):
        Leaderboard().add(submission)


def test_the_refusal_names_the_metrics_it_does_know(fixed_ts: datetime) -> None:
    result = _signed_on("rmse", 0.90, "worse-model", fixed_ts)
    model = ModelInfo(name="worse-model", version="1", license="MIT", citation="c")
    with pytest.raises(SubmissionError) as excinfo:
        Leaderboard().add(
            Submission(submitter="x", model=model, results=(result,), submitted_at=fixed_ts)
        )
    for metric in HIGHER_IS_BETTER:
        assert metric in str(excinfo.value)


def test_ranking_never_guesses() -> None:
    """The direction lookup refuses rather than defaulting to descending."""
    with pytest.raises(SubmissionError, match="unknown ranking metric"):
        metric_is_descending("rmse")


def test_every_shipped_task_ranks_on_a_metric_with_a_known_direction() -> None:
    """The table has to cover the tasks that exist, not the tasks it was written for."""
    for name, task in TASKS.items():
        for metric in task.metrics:
            assert metric in HIGHER_IS_BETTER, (
                f"task {name!r} reports {metric!r}, whose ranking direction is undeclared"
            )


def test_the_two_names_for_one_fact_cannot_disagree() -> None:
    """`LOWER_IS_BETTER` is a view of the runner's table, not a second copy of it."""
    assert LOWER_IS_BETTER == frozenset(m for m, higher in HIGHER_IS_BETTER.items() if not higher)
    assert LOWER_IS_BETTER == frozenset({"kl", "ece"})  # unchanged behaviour for known metrics
