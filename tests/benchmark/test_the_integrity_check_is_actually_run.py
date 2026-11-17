"""`Split.verify` is thoroughly tested, and nothing checked that anybody calls it.

`tests/benchmark/test_splits.py` exercises every way the check can fail — a tampered
membership hash, a drifted dataset, overlapping folds, an id absent from the data — by
invoking `split.verify(dataset)` directly. It is a good test of the function.

A statement-deletion sweep removed the two statements that *call* it — in `load_split`
and in `run_benchmark` — and the whole suite stayed green for both. Every one of those
failure cases would still have raised if asked; nothing was asking. A benchmark whose
whole claim is "this board ranks on the split it says it does" would have loaded an
edited split file and scored against drifted data without a word.

The same shape as a round a few ago, from the other end: there the guarantee was the
function's and the caller happened to provide it; here the function provides it and the
callers were the only thing standing between a user and the check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.benchmark.datasets import load_dataset
from alleleforge.benchmark.runner import run_benchmark
from alleleforge.benchmark.splits import Split, SplitIntegrityError, load_split
from alleleforge.benchmark.tasks import get_task

_TASK = "cas9-efficiency"


@pytest.fixture
def tampered_dir(tmp_path: Path) -> Path:
    """A splits directory holding one split whose membership hash no longer matches."""
    split, _ = load_split(_TASK)
    tampered = split.model_copy(update={"test": split.test + ("rs3-not-a-real-id",)})
    path = tmp_path / f"{_TASK}.{split.split_version}.json"
    path.write_text(tampered.model_dump_json())
    return tmp_path


def test_the_fixture_is_a_split_that_would_fail_its_own_check(tampered_dir: Path) -> None:
    """The premise: the file on disk is one `verify` rejects."""
    raw = json.loads((tampered_dir / f"{_TASK}.v1.json").read_text())
    split = Split.model_validate(raw)
    with pytest.raises(SplitIntegrityError):
        split.verify(load_dataset(split.dataset))


def test_loading_a_tampered_split_refuses_it(tampered_dir: Path) -> None:
    """`load_split` is where every caller in the project gets its split."""
    with pytest.raises(SplitIntegrityError, match="membership hash mismatch"):
        load_split(_TASK, splits_dir=tampered_dir)


def test_running_a_benchmark_on_a_supplied_split_checks_it_against_the_data() -> None:
    """The second door: a caller who already has a split hands it in with the dataset.

    `load_split` cannot help here — it was never called — so the runner does the check
    itself. A split paired with data it was not minted against is the exact situation a
    frozen split exists to prevent.
    """
    split, dataset = load_split(_TASK)
    rows = list(dataset.examples)
    drifted = dataset.model_copy(
        update={"examples": (rows[0].model_copy(update={"label": 0.123456}), *rows[1:])}
    )
    task = get_task(_TASK)
    from alleleforge.benchmark.baseline import build_baseline

    model = build_baseline(task, split, dataset)
    with pytest.raises(SplitIntegrityError, match="the data changed"):
        run_benchmark(model, task, split=split, dataset=drifted)


def test_a_matching_split_and_dataset_still_run() -> None:
    """The negative case: the check must not refuse the honest pairing."""
    split, dataset = load_split(_TASK)
    task = get_task(_TASK)
    from alleleforge.benchmark.baseline import build_baseline

    result = run_benchmark(build_baseline(task, split, dataset), task, split=split, dataset=dataset)
    assert result.split_version == split.split_version
