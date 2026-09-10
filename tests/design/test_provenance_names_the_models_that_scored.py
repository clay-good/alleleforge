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
