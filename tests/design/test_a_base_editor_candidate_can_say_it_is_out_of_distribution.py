"""The OOD disclosure could not be raised on one of the three chemistries.

`ood` is the honesty machinery's sharpest label: it says the efficiency point estimate
should not be trusted, and that the candidate was ranked on its lower interval bound
instead. `design/cas9.py` and `design/prime.py` both raise it from
`efficiency.in_distribution`. `design/base_editor.py`'s `_flags` was never handed the
prediction, so no base-editor candidate could carry it — whatever the predictor said.

The ranker was never fooled: it reads `in_distribution` off the prediction directly and
was already demoting such a candidate. So a base-editor candidate could be *ranked* as
untrustworthy and *rendered* as ordinary — the two halves of one fact disagreeing, which
is the shape this project keeps finding.

Reachable through a documented path: `design(base_outcome_predictor=...)` takes any
predictor satisfying the protocol, including the opt-in trained BE-DICT adapter, and a
trained model's OOD detector legitimately returns `in_distribution=False`. (The bundled
baseline's own condition — an `N` in the spacer — is excluded earlier by the enumerator,
which is why nothing noticed.)
"""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import caveats
from alleleforge.scoring.base_outcome import BaseEditOutcomePredictor, WindowOutcome
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import BaseEditWindow


class _OutOfDistributionPredictor:
    """The bundled predictor, with every prediction marked out of distribution."""

    def __init__(self) -> None:
        self._inner = BaseEditOutcomePredictor()

    def predict(self, window: BaseEditWindow, editor: object) -> WindowOutcome:
        outcome = self._inner.predict(window, editor)  # type: ignore[arg-type]
        return dataclasses.replace(
            outcome,
            p_target_edited=outcome.p_target_edited.model_copy(update={"in_distribution": False}),
        )

    def model_card(self) -> object:
        return self._inner.model_card()


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _base_editor_candidates(reference: ReferenceGenome, predictor: object | None):
    menu = design(
        "chr2:1050:G>A",
        reference=reference,
        run_offtarget=False,
        base_outcome_predictor=predictor,  # type: ignore[arg-type]
    )
    return [c for c in menu.candidates if c.chemistry is Chemistry.BASE_ABE]


def test_an_out_of_distribution_candidate_says_so(reference: ReferenceGenome) -> None:
    candidates = _base_editor_candidates(reference, _OutOfDistributionPredictor())
    assert candidates, "no base-editor candidate to check"
    for candidate in candidates:
        assert "ood" in candidate.flags
        assert not candidate.efficiency.in_distribution


def test_the_flag_carries_its_explanation(reference: ReferenceGenome) -> None:
    candidate = _base_editor_candidates(reference, _OutOfDistributionPredictor())[0]
    reason = dict(caveats(candidate.flags))["ood"]
    assert "out of distribution" in reason
    assert "lower interval bound" in reason


def test_an_in_distribution_candidate_does_not(reference: ReferenceGenome) -> None:
    """A flag that always appears is not a flag."""
    candidates = _base_editor_candidates(reference, None)
    assert candidates
    for candidate in candidates:
        assert "ood" not in candidate.flags
