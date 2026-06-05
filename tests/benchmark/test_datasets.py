"""Bundled benchmark datasets load, hash stably, and carry provenance (Phase 14)."""

from __future__ import annotations

import pytest

from alleleforge.benchmark.datasets import available_datasets, load_dataset
from alleleforge.benchmark.tasks import TASKS


def test_every_task_has_a_loadable_dataset() -> None:
    available = set(available_datasets())
    for task in TASKS.values():
        assert task.dataset in available
        ds = load_dataset(task.dataset)
        assert ds.examples  # non-empty
        assert ds.name == task.dataset


def test_content_hash_is_stable_across_reloads() -> None:
    a = load_dataset("rs3-validation").content_hash()
    b = load_dataset("rs3-validation").content_hash()
    assert a == b and len(a) == 64


def test_dataset_version_carries_license_and_citation() -> None:
    dv = load_dataset("rs3-validation").dataset_version()
    assert dv.license and dv.citation
    assert dv.sha256 == load_dataset("rs3-validation").content_hash()
    # The shipped corpora are synthetic stand-ins, never vendored as real data.
    assert dv.redistributable is False


def test_by_id_round_trips() -> None:
    ds = load_dataset("rs3-validation")
    index = ds.by_id()
    assert len(index) == len(ds.examples)
    first = ds.examples[0]
    assert index[first.example_id] is first


def test_unknown_dataset_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_dataset("does-not-exist")
