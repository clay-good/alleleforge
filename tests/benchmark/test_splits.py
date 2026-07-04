"""Frozen splits are stable, content-hashed, and integrity-checked (Phase 14)."""

from __future__ import annotations

import pytest

from alleleforge.benchmark.datasets import load_dataset
from alleleforge.benchmark.splits import Split, SplitIntegrityError, load_split
from alleleforge.benchmark.tasks import TASKS


def test_every_task_split_loads_and_verifies() -> None:
    for name in TASKS:
        split, dataset = load_split(name)
        assert split.split_version == "v1"
        assert split.test  # a non-empty held-out fold
        # Folds are disjoint and reference real example ids.
        ids = set(dataset.by_id())
        folds = [set(split.train), set(split.val), set(split.test)]
        assert set().union(*folds) <= ids
        assert not (folds[0] & folds[1]) and not (folds[0] & folds[2])


def test_split_membership_hash_is_self_consistent() -> None:
    split, _ = load_split("cas9-efficiency")
    assert split.membership_hash() == split.split_sha256


def test_tampered_membership_is_rejected() -> None:
    split, dataset = load_split("cas9-efficiency")
    tampered = split.model_copy(update={"test": split.test + ("rs3-999",)})
    with pytest.raises(SplitIntegrityError, match="membership hash mismatch"):
        tampered.verify(dataset)


def test_drifted_dataset_is_rejected() -> None:
    split, dataset = load_split("cas9-efficiency")
    # Mutate one label so the dataset content hash no longer matches the split.
    rows = list(dataset.examples)
    drifted = dataset.model_copy(
        update={"examples": (rows[0].model_copy(update={"label": 0.123456}), *rows[1:])}
    )
    with pytest.raises(SplitIntegrityError, match="the data changed"):
        split.verify(drifted)


def test_cross_context_test_fold_holds_out_a_cell_type() -> None:
    split, dataset = load_split("cas9-efficiency")
    index = dataset.by_id()
    test_contexts = {index[i].inputs["cell_type"] for i in split.test}
    train_contexts = {index[i].inputs["cell_type"] for i in split.train}
    # The held-out context never appears in train (a real generalization split).
    assert test_contexts and not (test_contexts & train_contexts)


def test_examples_fold_accessor() -> None:
    split, dataset = load_split("cas9-efficiency")
    test = split.examples(dataset, "test")
    assert len(test) == len(split.test)
    with pytest.raises(ValueError, match="unknown fold"):
        split.examples(dataset, "holdout")


def test_unknown_split_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_split("cas9-efficiency", version="v999")


def test_load_split_accepts_preloaded_dataset() -> None:
    ds = load_dataset("rs3-validation")
    split, returned = load_split("cas9-efficiency", dataset=ds)
    assert returned is ds
    assert isinstance(split, Split)


def test_overlapping_folds_are_rejected() -> None:
    # A hash-valid split with a train id also in test must be rejected as leakage.
    split, dataset = load_split("cas9-efficiency")
    leaky = split.model_copy(update={"test": split.test + (split.train[0],)})
    leaky = leaky.model_copy(update={"split_sha256": leaky.membership_hash()})
    with pytest.raises(SplitIntegrityError, match="leaks .* between train and test|disjoint"):
        leaky.verify(dataset)


def test_dangling_split_id_is_rejected() -> None:
    # A hash-valid split referencing an id absent from the dataset is rejected
    # up front, not as a later KeyError in examples().
    split, dataset = load_split("cas9-efficiency")
    dangling = split.model_copy(update={"test": split.test + ("no-such-id-xyz",)})
    dangling = dangling.model_copy(update={"split_sha256": dangling.membership_hash()})
    with pytest.raises(SplitIntegrityError, match="absent from dataset"):
        dangling.verify(dataset)
