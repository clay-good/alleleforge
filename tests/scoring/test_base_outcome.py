"""Tests for base-editing window-outcome prediction."""

from __future__ import annotations

import math

import pytest

from alleleforge.enumerate.base_editor import BASE_EDITORS
from alleleforge.model_zoo.registry import CardError
from alleleforge.scoring.base_outcome import (
    BaseEditOutcomePredictor,
    BeDictAdapter,
    BeHiveAdapter,
    WindowOutcome,
    recommend_window,
)
from alleleforge.types.guide import BaseEditWindow, Spacer
from alleleforge.types.prediction import UncertaintyMethod
from alleleforge.types.sequence import DNASequence

_ABE = next(e for e in BASE_EDITORS if e.name == "ABE8e")
_CBE = next(e for e in BASE_EDITORS if e.name == "CBE4max")


def _window(
    spacer: str, *, target: int, bystanders: tuple[int, ...] = (), editor: str = "ABE8e"
) -> BaseEditWindow:
    return BaseEditWindow(
        spacer=Spacer(sequence=DNASequence(spacer)),
        editor=editor,
        window=(4, 8),
        target_positions=(target,),
        bystander_positions=bystanders,
    )


def test_distribution_normalized_and_methods() -> None:
    w = _window("TTTAAACGTTTTTTTTTTTT", target=6, bystanders=(4, 5))
    result = BaseEditOutcomePredictor().predict(w, _ABE)
    assert math.isclose(sum(a.probability for a in result.outcome.alleles), 1.0, abs_tol=1e-9)
    assert result.p_intended_exact.method is UncertaintyMethod.HEURISTIC
    assert result.p_intended_exact.interval_level == 0.80


def test_clean_window_has_high_exact_probability() -> None:
    clean = _window("TTTTTACGTTTTTTTTTTTT", target=6)  # only the target A in-window
    bystander = _window("TTTAAACGTTTTTTTTTTTT", target=6, bystanders=(4, 5))
    p_clean = BaseEditOutcomePredictor().predict(clean, _ABE).p_intended_exact.value
    p_bys = BaseEditOutcomePredictor().predict(bystander, _ABE).p_intended_exact.value
    assert p_clean > p_bys  # bystanders reduce the exact-intended probability


def test_bystander_burden_counts_bystanders() -> None:
    no_bys = BaseEditOutcomePredictor().predict(_window("TTTTTACGTTTTTTTTTTTT", target=6), _ABE)
    with_bys = BaseEditOutcomePredictor().predict(
        _window("TTTAAACGTTTTTTTTTTTT", target=6, bystanders=(4, 5)), _ABE
    )
    assert no_bys.bystander_burden.value == 0.0
    assert with_bys.bystander_burden.value > 0.0


def test_intended_allele_marked() -> None:
    w = _window("TTTTTACGTTTTTTTTTTTT", target=6)
    result = BaseEditOutcomePredictor().predict(w, _ABE)
    intended = [a for a in result.outcome.alleles if a.is_intended]
    assert len(intended) == 1
    assert intended[0].allele == "A6G"


def test_motif_preference_raises_cbe_editing() -> None:
    # APOBEC1 (CBE4max) prefers a 5' T: a TC context edits more than an AC one.
    tc = _window("TTTTCACGTTTTTTTTTTTT", target=5, editor="CBE4max")  # T before C
    ac = _window("TTTACACGTTTTTTTTTTTT", target=5, editor="CBE4max")  # A before C
    predictor = BaseEditOutcomePredictor()
    assert _edit_prob(predictor.predict(tc, _CBE)) > _edit_prob(predictor.predict(ac, _CBE))


def _edit_prob(result: WindowOutcome) -> float:
    return next(a.probability for a in result.outcome.alleles if a.allele == "C5T")


def test_model_card() -> None:
    assert BaseEditOutcomePredictor().model_card().name == "be-dict"


# -- recommendation -----------------------------------------------------------


def test_recommend_prefers_clean_window() -> None:
    predictor = BaseEditOutcomePredictor()
    clean = _window("TTTTTACGTTTTTTTTTTTT", target=6)
    bystander = _window("TTTAAACGTTTTTTTTTTTT", target=6, bystanders=(4, 5))
    scored = [
        (clean, predictor.predict(clean, _ABE)),
        (bystander, predictor.predict(bystander, _ABE)),
    ]
    best = recommend_window(scored)
    assert best is not None and best[0] is clean


def test_recommend_empty() -> None:
    assert recommend_window([]) is None


# -- adapters -----------------------------------------------------------------


def test_bedict_adapter_interface() -> None:
    assert BeDictAdapter().name == "BE-DICT"
    assert BeDictAdapter().model_card().name == "be-dict"


def test_behive_card_missing() -> None:
    with pytest.raises(CardError, match="no model card"):
        BeHiveAdapter().model_card()  # no 'be-hive' card is bundled
