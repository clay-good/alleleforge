"""The third chemistry's OOD disclosure, which no test had ever raised.

`ood` is the honesty machinery's sharpest label: it says the efficiency point estimate
should not be trusted, and that the candidate was ranked on its lower interval bound
instead. A round found `design/base_editor.py` unable to raise it at all and gave that
chemistry a test; `design/prime.py` has two. `design/cas9.py` writes the flag from the
same `efficiency.in_distribution`, and a statement-deletion sweep removed the
`flags.append("ood")` with the whole suite green — the one vertical of the three with no
case for it.

Nothing is wrong with the line. What was wrong is that two of three chemistries were
pinned and the third was taken on trust, which is how the base-editor gap survived long
enough to be found by a sweep rather than by a reader. The bundled heuristic scorer
reports in-distribution for any guide the enumerator will emit, so the flag is reached
the documented way: `design(cas9_efficiency_scorer=...)` takes any scorer satisfying the
protocol, and a trained model's OOD detector legitimately returns
``in_distribution=False``.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import caveats
from alleleforge.scoring.cas9_efficiency import RuleSet3Scorer
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.prediction import Prediction


class _OutOfDistributionScorer:
    """The bundled scorer, with every prediction marked out of distribution."""

    name = "rule-set-3"

    def __init__(self) -> None:
        self._inner = RuleSet3Scorer()

    def score(self, context: str) -> Prediction[float]:
        inner = self._inner.score(context)
        return inner.model_copy(update={"in_distribution": False})

    def model_card(self) -> object:
        return self._inner.model_card()


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _nuclease_candidates(reference: ReferenceGenome, scorer: object | None) -> list[object]:
    menu = design(
        "chr2:1050:G>A",
        reference=reference,
        intent=EditIntent.KNOCK_OUT,
        run_offtarget=False,
        cas9_efficiency_scorer=scorer,  # type: ignore[arg-type]
    )
    return [c for c in menu.candidates if c.chemistry is Chemistry.CAS9_NUCLEASE]


def test_an_out_of_distribution_candidate_says_so(reference: ReferenceGenome) -> None:
    candidates = _nuclease_candidates(reference, _OutOfDistributionScorer())
    assert candidates, "no nuclease candidate to check"
    for candidate in candidates:
        assert "ood" in candidate.flags, candidate.flags
        assert candidate.efficiency is not None and not candidate.efficiency.in_distribution


def test_the_flag_carries_its_explanation(reference: ReferenceGenome) -> None:
    candidate = _nuclease_candidates(reference, _OutOfDistributionScorer())[0]
    reason = dict(caveats(candidate.flags))["ood"]
    assert "out of distribution" in reason


def test_an_in_distribution_candidate_does_not(reference: ReferenceGenome) -> None:
    """A flag that always appears is not a flag."""
    candidates = _nuclease_candidates(reference, None)
    assert candidates, "no nuclease candidate to check"
    for candidate in candidates:
        assert "ood" not in candidate.flags, candidate.flags
