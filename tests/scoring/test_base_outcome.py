"""Tests for base-editing window-outcome prediction."""

from __future__ import annotations

import math

import pytest

from alleleforge.enumerate.base_editor import BASE_EDITORS
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


def test_behive_card_now_bundled() -> None:
    # BE-Hive ships a bundled, license-gated card (research-only).
    assert BeHiveAdapter().model_card().name == "be-hive"


def test_base_outcome_adapter_predict_requires_consent() -> None:
    from alleleforge.model_zoo.registry import ConsentError

    w = _window("TTTAAACGTTTTTTTTTTTT", target=6, bystanders=(4, 5))
    with pytest.raises(ConsentError, match="consent"):
        BeDictAdapter().predict(w, _ABE)


def test_base_outcome_adapter_blocks_commercial_use() -> None:
    from alleleforge.model_zoo.registry import LicenseError, ModelUse

    # The trained adapters are research-only; commercial use is refused.
    with pytest.raises(LicenseError, match="commercial"):
        BeHiveAdapter(use=ModelUse.COMMERCIAL, consent=True).resolve_weights()


# -- trained BE-DICT adapter --------------------------------------------------

_EVO = next(e for e in BASE_EDITORS if e.name == "evoCDA1")


def test_assemble_window_outcome_from_explicit_probs() -> None:
    # The shared allele math: trained probabilities flow through identically.
    from alleleforge.scoring.base_outcome import _assemble_window_outcome

    w = _window("ACACACACACTTAGAATCTG", target=5, bystanders=(7,), editor="ABE8e")
    probs = {5: 0.8, 7: 0.5}
    out = _assemble_window_outcome(w, _ABE, probs)
    assert math.isclose(sum(a.probability for a in out.outcome.alleles), 1.0, abs_tol=1e-9)
    assert math.isclose(out.p_intended_exact.value, 0.8 * (1 - 0.5), abs_tol=1e-9)
    assert math.isclose(out.bystander_burden.value, 0.5, abs_tol=1e-9)


def test_bedict_supported_editor() -> None:
    assert BeDictAdapter().supported_editor(_ABE) is True  # ABE8e -> ABE8e
    assert BeDictAdapter().supported_editor(_CBE) is True  # CBE4max -> BE4max
    assert BeDictAdapter().supported_editor(_EVO) is False  # no BE-DICT model


def test_bedict_card_is_mit() -> None:
    assert BeDictAdapter().model_card().license == "MIT"  # permits research + commercial


def test_bedict_unsupported_editor_raises_before_gate() -> None:
    # An unsupported editor is rejected before any weight resolution.
    w = _window("TTTTCACGTTTTTTTTTTTT", target=5, editor="evoCDA1")
    with pytest.raises(ValueError, match="no trained model"):
        BeDictAdapter(consent=True).predict(w, _EVO)


@pytest.mark.real_weights
def test_bedict_golden() -> None:
    """The adapter reproduces BE-DICT's per-position probabilities + maps positions.

    Opt-in: set $ALLELEFORGE_BEDICT_REPO to a BE-DICT checkout in a torch env.
    Skipped otherwise, so CI stays weight-free.
    """
    import importlib.util
    import os
    from pathlib import Path

    repo = os.environ.get("ALLELEFORGE_BEDICT_REPO")
    if not repo or not (Path(repo) / "criscas").exists():
        pytest.skip("set ALLELEFORGE_BEDICT_REPO to a BE-DICT checkout")
    if importlib.util.find_spec("torch") is None:
        pytest.skip("torch not installed")

    adapter = BeDictAdapter(repo_dir=repo, consent=True)
    probs = adapter.edit_probabilities("ACACACACACTTAGAATCTG", _ABE)  # ABE8e
    assert abs(probs[4] - 0.77622) < 5e-3  # window peak (golden)
    assert abs(probs[6] - 0.57672) < 5e-3

    # Full predict pins the 1-based(AlleleForge) <-> 0-based(BE-DICT) mapping: the
    # target at AlleleForge pos 5 must pick up base_pos 4 (the peak), not a neighbor.
    w = _window("ACACACACACTTAGAATCTG", target=5, bystanders=(7,), editor="ABE8e")
    out = adapter.predict(w, _ABE)
    assert abs(out.p_intended_exact.value - 0.77622 * (1 - 0.57672)) < 1e-2
