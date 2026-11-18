"""A refused model was still recorded as one this run used.

`_collect_model_checkpoints` stamps a card for every *eligible* chemistry's scorers, and
its docstring says the block "names the model that actually scored the candidates rather
than the default it replaced ... otherwise a re-run from the stamped provenance would
reproduce different numbers". A chemistry can be eligible and never run: `_run_chemistry`
catches an expected failure, writes a `skipped` note and returns no candidates — and the
commonest such failure is the trained model itself being turned away, by the licence gate,
a missing extra, or an unverifiable checkpoint.

So the artifact said both things. Three lines of rationale: "prime: skipped (LicenseError:
license 'research-only' forbids commercial use of model 'deepprime')". The provenance
block below it: `models: [deepprime, ...]`. A reader who checks what a result was scored by
— which is the whole purpose of that block, and what `aforge verify` reads — was told the
model was there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.cache import CacheIntegrityError
from alleleforge.design.designer import design
from alleleforge.design.prime import PrimeEfficiencyScorer
from alleleforge.errors import MissingDependencyError
from alleleforge.genome.reference import ReferenceGenome


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta, build="hg38")


class _RefusingScorer(PrimeEfficiencyScorer):  # type: ignore[misc]
    """A trained scorer that cannot load — the licence gate's shape, without a network.

    `MissingDependencyError` is in `_EXPECTED_DESIGN_FAILURES` exactly as `LicenseError`
    is: both mean "the model you asked for is not going to score this run".
    """

    def __init__(self) -> None:
        pass

    def model_checkpoints(self) -> tuple[Any, ...]:
        raise MissingDependencyError("the trained prime model is not installed here")

    def score(self, *args: Any, **kwargs: Any) -> Any:
        raise MissingDependencyError("the trained prime model is not installed here")


def _names(menu: Any) -> list[str]:
    return [m.name for m in menu.provenance.models]


def test_a_run_that_scores_records_its_models(reference: ReferenceGenome) -> None:
    """The floor: without this the assertion below passes on an empty block."""
    menu = design("chr2:71:A>C", reference=reference, run_offtarget=False)
    assert menu.candidates, "no candidates; this fixture cannot show anything"
    assert "pridict2-baseline" in _names(menu)


def test_a_chemistry_that_never_ran_stamps_no_model(reference: ReferenceGenome) -> None:
    menu = design(
        "chr2:71:A>C",
        reference=reference,
        run_offtarget=False,
        prime_efficiency_scorer=_RefusingScorer(),
    )
    assert not menu.candidates, "prime was supposed to be the only eligible chemistry"
    assert "skipped" in menu.rationale, menu.rationale
    assert _names(menu) == [], (
        "the provenance names a model for a chemistry that raised before scoring "
        f"anything: {_names(menu)}"
    )


def test_the_rationale_still_says_what_happened(reference: ReferenceGenome) -> None:
    """Removing the card must not remove the explanation — that would be worse."""
    menu = design(
        "chr2:71:A>C",
        reference=reference,
        run_offtarget=False,
        prime_efficiency_scorer=_RefusingScorer(),
    )
    assert "MissingDependencyError" in menu.rationale
    assert "not installed here" in menu.rationale


@pytest.mark.parametrize(
    ("failure", "marker"),
    [
        (CacheIntegrityError("the entry is not the bytes that were written"), "integrity"),
        (RuntimeError("an outright defect"), "defect"),
    ],
)
def test_a_chemistry_that_raised_stamps_no_model_whichever_way_it_raised(
    reference: ReferenceGenome,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    marker: str,
) -> None:
    """Three `except` arms each drop the chemistry from the models block; one was tested.

    `_run_chemistry` catches an altered store, an expected design failure, and anything
    else, and every arm does the same two things: write a note, and add the chemistry to
    the `failed` set that `_collect_model_checkpoints` subtracts. Only the middle arm —
    the expected failure, exercised by the refusing scorer above — had a test, so the
    `failed.update(...)` in the other two could be deleted and the suite stayed green.

    The consequence is the one this whole file is about, arriving by two other doors: a
    run whose prime vertical died on a tampered cache entry, or on a genuine bug, still
    records `pridict2-baseline` as a model that scored it. `aforge verify` reads that
    block to decide whether a result is reproducible, and nothing scored anything.
    """
    from alleleforge.design import designer as designer_module

    def explode(*args: object, **kwargs: object) -> object:
        raise failure

    monkeypatch.setattr(designer_module, "design_prime", explode)
    menu = design("chr2:71:A>C", reference=reference, run_offtarget=False)

    assert not menu.candidates, "prime was supposed to be the only eligible chemistry"
    assert _names(menu) == [], f"a {marker} failure left a model in the provenance: {_names(menu)}"
    assert "prime" in menu.rationale, menu.rationale
