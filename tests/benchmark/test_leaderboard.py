"""The leaderboard gates on a model card and ranks honestly (Phase 14)."""

from __future__ import annotations

from datetime import datetime

import pytest

from alleleforge.benchmark.baseline import build_baseline
from alleleforge.benchmark.leaderboard import (
    Leaderboard,
    Submission,
    SubmissionError,
    metric_is_descending,
)
from alleleforge.benchmark.runner import BenchmarkResult, ModelInfo, run_benchmark
from alleleforge.benchmark.splits import load_split
from alleleforge.benchmark.tasks import get_task


def _baseline_result(task_name: str, ts: datetime) -> BenchmarkResult:
    """Run the reference baseline and return its signed result."""
    task = get_task(task_name)
    split, dataset = load_split(task_name)
    baseline = build_baseline(task, split, dataset)
    return run_benchmark(baseline, task, split=split, dataset=dataset, timestamp=ts)


def _model() -> ModelInfo:
    return ModelInfo(
        name="crispr-bench-baseline", version="1.0", license="MIT", citation="AlleleForge"
    )


def test_metric_direction() -> None:
    assert metric_is_descending("spearman")
    assert metric_is_descending("auroc")
    assert not metric_is_descending("kl")
    assert not metric_is_descending("ece")


def test_valid_submission_admits(fixed_ts: datetime) -> None:
    result = _baseline_result("cas9-efficiency", fixed_ts)
    sub = Submission(
        submitter="alleleforge", model=_model(), results=(result,), submitted_at=fixed_ts
    )
    lb = Leaderboard()
    lb.add(sub)
    assert lb.tasks == ("cas9-efficiency",)
    ranking = lb.rankings("cas9-efficiency")
    assert len(ranking) == 1 and ranking[0].model_name == "crispr-bench-baseline"


def test_submission_requires_model_card(fixed_ts: datetime) -> None:
    result = _baseline_result("cas9-efficiency", fixed_ts)
    bad_model = ModelInfo(name="x", version="1", license="", citation="")
    sub = Submission(submitter="x", model=bad_model, results=(result,), submitted_at=fixed_ts)
    with pytest.raises(SubmissionError, match="model card"):
        Leaderboard().add(sub)


def test_submission_requires_a_result(fixed_ts: datetime) -> None:
    sub = Submission(submitter="x", model=_model(), results=(), submitted_at=fixed_ts)
    with pytest.raises(SubmissionError, match="at least one result"):
        Leaderboard().add(sub)


def test_submission_rejects_tampered_signature(fixed_ts: datetime) -> None:
    result = _baseline_result("cas9-efficiency", fixed_ts)
    tampered = result.model_copy(update={"primary_value": 1.0})
    sub = Submission(submitter="x", model=_model(), results=(tampered,), submitted_at=fixed_ts)
    with pytest.raises(SubmissionError, match="signature"):
        Leaderboard().add(sub)


def test_submission_rejects_model_name_mismatch(fixed_ts: datetime) -> None:
    result = _baseline_result("cas9-efficiency", fixed_ts)
    other = ModelInfo(name="other", version="1", license="MIT", citation="c")
    sub = Submission(submitter="x", model=other, results=(result,), submitted_at=fixed_ts)
    with pytest.raises(SubmissionError, match="does not match"):
        Leaderboard().add(sub)


def test_rankings_order_by_direction(fixed_ts: datetime) -> None:
    # Two synthetic KL entries: lower KL must rank first.
    base = _baseline_result("cas9-outcome", fixed_ts)
    good = base.model_copy(update={"primary_value": 0.1, "metrics": {**base.metrics, "kl": 0.1}})
    bad = base.model_copy(update={"primary_value": 0.9, "metrics": {**base.metrics, "kl": 0.9}})
    good = good.model_copy(update={"signature": _resign(good)})
    bad = bad.model_copy(update={"signature": _resign(bad)})
    lb = Leaderboard()
    lb.add(
        Submission(
            submitter="a",
            model=_model(),
            results=(good,),
            submitted_at=fixed_ts,
        )
    )
    lb.add(
        Submission(
            submitter="b",
            model=_model(),
            results=(bad,),
            submitted_at=fixed_ts,
        )
    )
    ranked = lb.rankings("cas9-outcome")
    assert ranked[0].primary_value == 0.1  # lower KL wins


def test_render_markdown_and_html(fixed_ts: datetime) -> None:
    result = _baseline_result("cas9-efficiency", fixed_ts)
    lb = Leaderboard()
    lb.add(
        Submission(
            submitter="alleleforge", model=_model(), results=(result,), submitted_at=fixed_ts
        )
    )
    md = lb.render_markdown()
    assert "CRISPR-Bench Leaderboard" in md and "cas9-efficiency" in md and "ECE" in md
    html = lb.render_html()
    assert "<table>" in html and "crispr-bench-baseline" in html


def test_empty_leaderboard_renders() -> None:
    lb = Leaderboard()
    assert "No submissions yet" in lb.render_markdown()
    assert "No submissions yet" in lb.render_html()
    assert lb.rankings("cas9-efficiency") == []


def _resign(result: BenchmarkResult) -> str:
    """Recompute a result's signature after an in-test edit."""
    from alleleforge.benchmark._canon import content_hash

    body = result.model_dump(mode="json")
    body.pop("signature", None)
    return content_hash(body)


def test_leaderboard_escapes_submitter_markup(fixed_ts: datetime) -> None:
    # A submitter handle is attacker-controlled text: markup must be escaped in
    # the HTML board and a pipe must be escaped in the Markdown table.
    result = _baseline_result("cas9-efficiency", fixed_ts)
    evil = "<script>alert(1)</script> a|b"
    lb = Leaderboard()
    lb.add(Submission(submitter=evil, model=_model(), results=(result,), submitted_at=fixed_ts))
    html_out = lb.render_html()
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out
    md_out = lb.render_markdown()
    assert "a\\|b" in md_out  # the pipe is escaped so it cannot break the table
    assert "a|b" not in md_out


def test_duplicate_task_in_submission_rejected(fixed_ts: datetime) -> None:
    # One model may not carry two results for the same task in a submission —
    # otherwise it would occupy two ranked rows for the same task.
    result = _baseline_result("cas9-efficiency", fixed_ts)
    sub = Submission(
        submitter="x", model=_model(), results=(result, result), submitted_at=fixed_ts
    )
    with pytest.raises(SubmissionError, match="two results for task"):
        Leaderboard().add(sub)
