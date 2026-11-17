"""A real benchmark corpus had no supported way in, so nothing could notice one arriving.

`scripts/release_readiness.py` reports R1+R5 as *0/5 benchmark datasets are real corpora
— blocked: the bundled corpora are synthetic stand-ins*, and its own docstring says the
point of measuring a blocked criterion is that it "will notice the day one of them stops
being blocked".

For this criterion it could not. `load_dataset` took a `fixtures_dir` argument documented
"(tests)"; nothing in `src/` ever passed it and `aforge bench` had no option for it. A
maintainer holding the real PRIDICT2 library could not run the benchmark on it without
editing files inside the installed package, and the readiness report read the bundled
fixtures unconditionally — so the day real data arrived, the report would still have said
zero.

Two directories are supplied, not one, and the second is not optional: a frozen split
records its dataset's content hash and `verify` refuses a mismatch, so a bundled split
over replaced data fails its integrity check. That is the correct failure and a dead end,
which is why `ALLELEFORGE_BENCH_SPLITS` exists beside `ALLELEFORGE_BENCH_DATASETS`.

The corpus below is still synthetic — this is a test, and CI does not fetch real data.
What it demonstrates is the *path*: a dataset marked `synthetic: false` in a supplied
directory is found, loaded, scored against its own frozen split, and counted by the
criterion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.benchmark.datasets import (
    DATASETS_DIR_ENV,
    FIXTURES_DIR,
    available_datasets,
    datasets_dir,
    load_dataset,
)
from alleleforge.benchmark.splits import (
    SPLITS_DIR,
    SPLITS_DIR_ENV,
    load_split,
    splits_root,
)

_TASK = "cas9-efficiency"
#: The dataset that task draws from; a corpus file is named for the dataset, a split
#: file for the task that scores on it.
_DATASET = "rs3-validation"


@pytest.fixture
def supplied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A corpus directory holding one dataset that is *not* a stand-in, plus its split."""
    corpora, splits = tmp_path / "corpora", tmp_path / "splits"
    corpora.mkdir()
    splits.mkdir()

    bundled = load_dataset(_DATASET, fixtures_dir=FIXTURES_DIR)
    # Real data, not a relabelled stand-in: `content_hash` covers the examples and not
    # the `synthetic` flag, so flipping the flag alone leaves a hash-identical corpus
    # that the bundled split still verifies. A measured label is what actually differs
    # about a real corpus, so one is changed here — the ids are untouched, which is what
    # keeps the split's membership hash valid while its dataset hash moves.
    rows = list(bundled.examples)
    rows[0] = rows[0].model_copy(update={"label": 0.4242})
    real = bundled.model_copy(update={"synthetic": False, "examples": tuple(rows)})
    assert real.content_hash() != bundled.content_hash(), "the corpus must really differ"
    (corpora / f"{_DATASET}.json").write_text(real.model_dump_json())

    # The split has to be re-minted: it pins the dataset's content hash, and the copy
    # above changed a field that hash covers.
    bundled_split, _ = load_split(_TASK, splits_dir=SPLITS_DIR)
    rebound = bundled_split.model_copy(update={"dataset_sha256": real.content_hash()})
    # `membership_hash` covers `dataset_sha256`, so rebinding the split to new data
    # invalidates its own self-integrity hash too. Both are recomputed — which is what
    # minting a split *is*, and why `verify` tells an editor to mint a new version
    # rather than edit one.
    minted = rebound.model_copy(update={"split_sha256": rebound.membership_hash()})
    (splits / f"{_TASK}.{minted.split_version}.json").write_text(minted.model_dump_json())

    monkeypatch.setenv(DATASETS_DIR_ENV, str(corpora))
    monkeypatch.setenv(SPLITS_DIR_ENV, str(splits))
    return corpora


def test_the_bundled_corpora_are_still_the_default() -> None:
    """The premise, and the thing that must not change for anyone who sets nothing."""
    assert datasets_dir() == FIXTURES_DIR
    assert load_dataset(_DATASET).synthetic is True


def test_a_supplied_directory_is_where_the_corpora_come_from(supplied: Path) -> None:
    assert datasets_dir() == supplied
    assert available_datasets() == (_DATASET,)
    assert load_dataset(_DATASET).synthetic is False


def test_an_explicit_directory_still_wins_over_the_environment(supplied: Path) -> None:
    """A caller who names a directory is not asking about the environment."""
    assert load_dataset(_DATASET, fixtures_dir=FIXTURES_DIR).synthetic is True


def test_a_supplied_corpus_is_scored_against_its_own_split(supplied: Path) -> None:
    """The reason both variables exist: a bundled split over replaced data cannot verify."""
    split, dataset = load_split(_TASK)
    assert dataset.synthetic is False
    assert split.dataset_sha256 == dataset.content_hash()
    assert splits_root() != SPLITS_DIR


def test_a_bundled_split_over_supplied_data_is_refused(
    supplied: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure that makes the splits variable necessary rather than a convenience."""
    from alleleforge.benchmark.splits import SplitIntegrityError

    monkeypatch.delenv(SPLITS_DIR_ENV)
    with pytest.raises(SplitIntegrityError, match="the data changed"):
        load_split(_TASK)


def test_the_readiness_report_notices_a_real_corpus(supplied: Path) -> None:
    """The whole point. Before this, R1 could not stop being blocked.

    One supplied corpus is enough to flip the criterion here because the supplied
    directory holds one dataset and every dataset in it is real — which is exactly what
    the criterion asks.
    """
    from scripts import release_readiness

    r1 = next(c for c in release_readiness.criteria() if c.track == "R1+R5")
    assert r1.met is True, r1.detail
    assert not r1.blocked_by, r1.blocked_by


def test_the_readiness_report_still_reports_the_bundled_truth() -> None:
    """And with nothing supplied it says what it has always said."""
    from scripts import release_readiness

    r1 = next(c for c in release_readiness.criteria() if c.track == "R1+R5")
    assert r1.met is False
    assert "synthetic" in r1.blocked_by


def test_a_supplied_corpus_keeps_its_declared_provenance(supplied: Path) -> None:
    """A real corpus is only usable if it still carries a citation and a licence."""
    dataset = load_dataset(_DATASET)
    version = dataset.dataset_version()
    assert version.sha256 == dataset.content_hash()
    assert version.citation and version.license
    raw = json.loads((supplied / f"{_DATASET}.json").read_text())
    assert raw["synthetic"] is False
