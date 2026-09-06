"""The intended-allele probability must ship with its uncertainty, like its neighbours.

Design principle 2: "No scorer returns a bare float. Every numeric prediction ships
with a calibrated interval, a method tag, a calibrated flag, and an OOD flag."

A candidate carries three predicted quantities. Two of them honoured that:

    efficiency         Prediction[float]   0.45 [0.30, 0.60]  calibrated=False  in_dist=True
    bystander_burden   Prediction[float]
    p_intended         float               0.61

`p_intended` is the probability the edit produces the allele that was asked for — of
the three, the one a reader is most likely to act on — and it reached every surface as
a bare number.

It was not missing upstream. `PrimeOutcomePredictor.predict` returns a
`PrimeOutcome` whose `p_intended` **is** a `Prediction[float]`, and
`prime.py` dropped it in one line by passing `outcome=outcome.outcome`; base editing
computes `p_intended_exact: Prediction[float]` and never put it on the candidate. The
honest number was computed, then recomputed without its envelope as a plain sum over
the allele distribution.

SpCas9 nuclease is the case that keeps this honest: its outcome predictor produces no
such `Prediction`, so for a nuclease candidate `p_intended` genuinely *is* a derived
sum with no calibrated interval behind it. The rule cannot be "always show an interval"
— it has to be "never show a number whose status is unclear", so a candidate with no
prediction carries `None` and the surfaces say the figure is derived rather than
inventing a band for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.prediction import Prediction


@pytest.fixture
def prime_reference(tmp_path: Path) -> ReferenceGenome:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _prime_candidate(reference: ReferenceGenome) -> DesignCandidate:
    menu = design(
        "chr2:71:A>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        max_candidates_per_chemistry=1,
    )
    candidate = next(c for c in menu.candidates if c.chemistry is Chemistry.PRIME)
    return candidate


def test_the_candidate_carries_the_prediction_the_scorer_made(
    prime_reference: ReferenceGenome,
) -> None:
    candidate = _prime_candidate(prime_reference)
    assert isinstance(candidate.p_intended, Prediction)


def test_it_agrees_with_the_distribution_it_summarizes(
    prime_reference: ReferenceGenome,
) -> None:
    """The envelope must wrap the same number, not a second opinion."""
    candidate = _prime_candidate(prime_reference)
    assert candidate.p_intended is not None
    assert candidate.outcome is not None
    assert candidate.p_intended.value == pytest.approx(candidate.outcome.p_intended, abs=1e-9)


def test_it_carries_the_honesty_flags_its_neighbours_carry(
    prime_reference: ReferenceGenome,
) -> None:
    candidate = _prime_candidate(prime_reference)
    prediction = candidate.p_intended
    assert prediction is not None
    low, high = prediction.interval
    assert low <= prediction.value <= high
    assert isinstance(prediction.calibrated, bool)
    assert isinstance(prediction.in_distribution, bool)
    assert prediction.method


def test_a_chemistry_with_no_such_prediction_says_none(prime_reference: ReferenceGenome) -> None:
    """SpCas9's outcome predictor makes no `p_intended` prediction, so there is none.

    Inventing an interval here would be the failure this field exists to prevent.
    """
    assert "p_intended" in DesignCandidate.model_fields
    field = DesignCandidate.model_fields["p_intended"]
    assert field.default is None
    assert "None" in str(field.annotation)


@pytest.fixture
def abe_reference(tmp_path: Path) -> ReferenceGenome:
    """A locus an adenine base editor can install A>G at."""
    pad = "T" * 20
    fasta = tmp_path / "abe.fa"
    fasta.write_text(">chr2\n" + pad + "TTTAAACGTTTTTTTTTTTT" + "TGG" + pad + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_base_editing_carries_it_too(abe_reference: ReferenceGenome) -> None:
    """`p_intended_exact` is the base editor's name for the same quantity."""
    menu = design(
        "chr2:26:A>G",
        reference=abe_reference,
        intent=EditIntent.INSTALL,
        max_candidates_per_chemistry=1,
    )
    candidate = next(c for c in menu.candidates if c.chemistry is Chemistry.BASE_ABE)
    assert isinstance(candidate.p_intended, Prediction)


@pytest.mark.parametrize("chemistry", [Chemistry.PRIME, Chemistry.BASE_ABE])
def test_the_prediction_and_the_distribution_never_disagree(
    prime_reference: ReferenceGenome,
    abe_reference: ReferenceGenome,
    chemistry: Chemistry,
) -> None:
    """Two numbers for one quantity in one report is the failure to avoid.

    The renders show the prediction's `value`; the TSV column and the allele table
    come from the distribution. They are the same quantity by construction — the
    intended allele is the exact-clean one — and this is what keeps them so.
    """
    if chemistry is Chemistry.PRIME:
        menu = design(
            "chr2:71:A>C",
            reference=prime_reference,
            intent=EditIntent.INSTALL,
            max_candidates_per_chemistry=1,
        )
    else:
        menu = design(
            "chr2:26:A>G",
            reference=abe_reference,
            intent=EditIntent.INSTALL,
            max_candidates_per_chemistry=1,
        )
    candidate = next(c for c in menu.candidates if c.chemistry is chemistry)
    assert candidate.p_intended is not None
    assert candidate.outcome is not None
    assert candidate.p_intended.value == pytest.approx(candidate.outcome.p_intended, abs=1e-9)
