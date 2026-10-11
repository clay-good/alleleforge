"""Scorer boundaries every fixture sat comfortably inside, and three honesty flags.

Each of these is a line the suite executed thousands of times without ever asking it a
question it could get wrong:

* `context_in_distribution` calls a context shorter than `_MIN_CONTEXT_LENGTH` out of
  distribution. Every fixture used a 30-nt Rule-Set-3 context, so the minimum could have
  moved to 21 and a genuine 20-nt context would have been flagged OOD — demoted by the
  ranker and captioned as untrustworthy — with nothing failing.
* The prime baseline's geometry term is documented as "PBS near 13 nt is best". The
  optimum could have moved to 14 while every fixture scored one PBS length.
* The base-editor motif model reads the base 5' of the editable position, which only
  exists from position 2 on. Position 2 is the first position where the motif applies and
  the only one that distinguishes `>= 2` from `>= 3`; no fixture had its target there.
* The window outcome is a frozen dataclass, declares a complete distribution, and its
  member heads refuse an embedding whose width does not match their weights. Nothing
  tested any of the three: a silently truncated dot product is a wrong efficiency, not an
  error, and that is the failure mode a real backbone of the wrong width would produce.
"""

from __future__ import annotations

import dataclasses

import pytest

from alleleforge.enumerate.base_editor import BASE_EDITORS
from alleleforge.enumerate.prime import SCAFFOLD
from alleleforge.scoring.base_outcome import (
    BaseEditOutcomePredictor,
    WindowOutcome,
    _edit_probability,
)
from alleleforge.scoring.cas9_efficiency import (
    EnsembleEfficiencyScorer,
    context_in_distribution,
)
from alleleforge.scoring.prime_efficiency import _OPTIMAL_PBS, PridictScorer
from alleleforge.types.guide import BaseEditWindow, PegRNA, Spacer
from alleleforge.types.sequence import DNASequence

_ABE = next(e for e in BASE_EDITORS if e.name == "ABE8e")


def _peg(pbs_len: int) -> PegRNA:
    """A pegRNA differing from its siblings *only* in PBS length.

    An all-G/C PBS keeps the GC fraction at 1.0 for every length, so the mid-GC term
    in the logit contributes the same amount each time and the length penalty is the
    only thing that moves. Slicing a mixed `ACGT` repeat instead changes GC with
    length, which made a first draft of this test compare two different fixtures and
    fail on a symmetry the code does honor.
    """
    return PegRNA(
        spacer=Spacer(sequence=DNASequence("ACGTACGTACGTACGTACGT")),
        scaffold=DNASequence(SCAFFOLD),
        rtt=DNASequence("ACGTACGTACGTACGT"),
        pbs=DNASequence("GC" * 9)[:pbs_len],
        rtt_homology_3prime=5,
    )


def test_a_context_of_exactly_the_minimum_length_is_in_distribution() -> None:
    assert context_in_distribution("A" * 20), "20 nt is the documented minimum, inclusive"


def test_a_context_one_base_short_is_out_of_distribution() -> None:
    assert not context_in_distribution("A" * 19)


def test_an_ambiguous_base_is_out_of_distribution_at_any_length() -> None:
    """The other clause of the same `and`, so neither can carry the test alone."""
    assert not context_in_distribution("N" + "A" * 29)


# --- the prime geometry optimum -----------------------------------------------------


def test_the_pbs_optimum_is_thirteen_nucleotides() -> None:
    assert _OPTIMAL_PBS == 13, "Anzalone's PBS geometry; the docstring says 'near 13 nt'"


def test_a_pbs_of_thirteen_outscores_its_neighbours_symmetrically() -> None:
    """Built from the logit directly: the penalty is zero at 13 and symmetric around it."""
    scorer = PridictScorer()
    logits = {n: scorer._logit(_peg(n)) for n in (11, 12, 13, 14, 15)}
    assert logits[13] == max(logits.values()), "13 nt must be the peak"
    assert logits[12] == pytest.approx(logits[14]), "the penalty is |len - 13|, symmetric"
    assert logits[11] == pytest.approx(logits[15])
    assert logits[12] > logits[11], "and it grows with the distance"


# --- the base-editor motif boundary -------------------------------------------------


def test_the_motif_neighbour_is_read_from_position_two_onward() -> None:
    """Position 2 is where a 5' neighbour first exists, and where the motif first bites."""
    editor = next(e for e in BASE_EDITORS if e.motif_preference is not None)
    pref = editor.motif_preference
    assert pref is not None
    other = next(b for b in "ACGT" if b != pref)
    window = (1, 8)
    # At position 2 the neighbour is spacer[0]: make it the preferred base in one
    # spacer and a non-preferred base in the other, holding everything else equal.
    preferred = _edit_probability(2, pref + "C" * 24, editor, window)
    against = _edit_probability(2, other + "C" * 24, editor, window)
    assert preferred > against, (
        "the motif preference must already apply at position 2, the first position "
        "that has a 5' neighbour at all"
    )


def test_position_one_has_no_motif_neighbour_to_read() -> None:
    """The negative case: below the boundary the spacer's bases cannot change the score."""
    editor = next(e for e in BASE_EDITORS if e.motif_preference is not None)
    pref = editor.motif_preference
    assert pref is not None
    other = next(b for b in "ACGT" if b != pref)
    window = (1, 8)
    assert _edit_probability(1, pref + "C" * 24, editor, window) == _edit_probability(
        1, other + "C" * 24, editor, window
    )


# --- the honesty flags and the width guard ------------------------------------------


def test_a_window_outcome_cannot_be_retuned_after_scoring() -> None:
    assert dataclasses.fields(WindowOutcome), "no fields discovered"
    assert WindowOutcome.__dataclass_params__.frozen is True


def test_a_scored_window_reports_a_complete_distribution() -> None:
    window = BaseEditWindow(
        spacer=Spacer(sequence=DNASequence("TTTAAACGTTTTTTTTTTTT")),
        editor="ABE8e",
        window=(4, 8),
        target_positions=(6,),
        bystander_positions=(4, 5),
    )
    scored = BaseEditOutcomePredictor().predict(window, _ABE)
    assert scored.outcome.partial is False, (
        "the window distribution enumerates every subset of editable positions, so it "
        "covers the whole space and must not be marked partial"
    )
    assert sum(a.probability for a in scored.outcome.alleles) == pytest.approx(1.0)


def test_an_ensemble_head_refuses_an_embedding_of_the_wrong_width() -> None:
    """Truncating silently would return a plausible, wrong efficiency."""
    head = EnsembleEfficiencyScorer()._member_head([0.5, -0.5, 0.25])
    with pytest.raises(ValueError, match="argument 2 is shorter|zip"):
        head((0.1, 0.2))


def test_the_ensembles_disagreement_band_stays_inside_zero_to_one() -> None:
    """An efficiency is a fraction, so neither bound may leave [0, 1].

    The ensemble's band is the spread of its members' disagreement, which is wide
    enough to run off both ends of the domain: these two contexts clamp at 1.0 and at
    0.0 respectively. Every prior fixture scored a middling guide whose band fitted
    inside the domain on its own, so the clamp decided nothing and could be widened to
    1.1 — publishing an efficiency interval that claims more than certainty — with the
    suite green.
    """
    scorer = EnsembleEfficiencyScorer()
    at_the_top = scorer.score("CATGCGGGTGTGCACGCCACTAAGACGAAA")
    assert at_the_top.interval[1] == 1.0, "this fixture must reach the ceiling"
    at_the_bottom = scorer.score("GCGGTGTTAAGTGTCGAGCTACATCACTTC")
    assert at_the_bottom.interval[0] == 0.0, "and this one the floor"
    for prediction in (at_the_top, at_the_bottom):
        low, high = prediction.interval
        assert 0.0 <= low <= prediction.value <= high <= 1.0
