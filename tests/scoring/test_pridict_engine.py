"""Tests for the PRIDICT2.0 sequence-level engine adapter.

The CSV-parsing + gate behaviour is exercised in CI on a fixture (no model); the
real PRIDICT2 run + golden parity is the opt-in `real_weights` test, which needs a
local PRIDICT2 checkout via $ALLELEFORGE_PRIDICT2_REPO.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alleleforge.model_zoo.registry import ConsentError
from alleleforge.scoring.pridict_engine import (
    PridictDesign,
    PridictEngineAdapter,
)
from alleleforge.types.prediction import UncertaintyMethod

_FIXTURE = Path(__file__).parent / "fixtures" / "pridict2_sample.csv"

# The exact sequence whose top-HEK design scored 78.854 (the golden), captured
# from the real PRIDICT2 run. Used by the opt-in real_weights test.
_GOLDEN_SEQUENCE = (
    "GACGCATCTGCCGCCTGTGCTTGGCTCTAGCTTTCTGCAGACTCCTGCAGCTTCGTGGCAGCTCTTGAGGGCCAAGG"
    "CCTGCAGGAACTTGGAGACGCAGTTGGCCAAGTTGGCTCTGGCT(A/G)GGCTGGAGCTGGTGGCGTAGGCTTGGCC"
    "TTGGCTCTGGCAGGCCTGTGGCTGGAGCTGGTGGCGTAGGCTTGGCCTTGGCAGGCCTGCTGGAGCTGGTGGCGTAGG"
)
_GOLDEN_TOP_HEK = 0.78854  # PRIDICT2 HEK score 78.854 / 100


# -- pure CSV parsing + Prediction contract (CI) ------------------------------


def test_parse_predictions_ranks_by_hek() -> None:
    designs = PridictEngineAdapter._parse_predictions(_FIXTURE, cell_line="HEK", top_n=3)
    assert len(designs) == 3
    assert all(isinstance(d, PridictDesign) for d in designs)
    # Sorted by efficiency, highest first.
    assert designs[0].efficiency.value >= designs[1].efficiency.value >= designs[2].efficiency.value
    top = designs[0]
    assert top.cell_line == "HEK"
    assert top.editing_position == 8 and top.pbs_length == 14 and top.rt_length == 17
    assert abs(top.efficiency.value - _GOLDEN_TOP_HEK) < 1e-3


def test_parse_predictions_cell_line_changes_ranking() -> None:
    hek = PridictEngineAdapter._parse_predictions(_FIXTURE, cell_line="HEK", top_n=1)[0]
    k562 = PridictEngineAdapter._parse_predictions(_FIXTURE, cell_line="K562", top_n=1)[0]
    # The two cell lines do not agree on the single best design in the fixture.
    assert (hek.pbs_length, hek.rt_length) != (k562.pbs_length, k562.rt_length)
    assert k562.cell_line == "K562"


def test_parse_predictions_respects_top_n() -> None:
    assert len(PridictEngineAdapter._parse_predictions(_FIXTURE, cell_line="HEK", top_n=2)) == 2


def test_parse_predictions_invalid_cell_line() -> None:
    with pytest.raises(ValueError, match="cell_line"):
        PridictEngineAdapter._parse_predictions(_FIXTURE, cell_line="HeLa", top_n=1)


def test_efficiency_prediction_contract() -> None:
    pred = PridictEngineAdapter._efficiency(78.854, cell_line="HEK")
    assert abs(pred.value - 0.78854) < 1e-9
    assert pred.interval[0] <= pred.value <= pred.interval[1]
    assert pred.interval_level == 0.80
    assert pred.method is UncertaintyMethod.HEURISTIC  # the interval is heuristic
    assert pred.calibrated is False
    assert pred.in_distribution is True  # HEK/K562 are the training distribution


def test_efficiency_prediction_clamps() -> None:
    assert PridictEngineAdapter._efficiency(0.0, cell_line="HEK").value == 0.0
    assert PridictEngineAdapter._efficiency(100.0, cell_line="HEK").value == 1.0
    assert PridictEngineAdapter._efficiency(140.0, cell_line="HEK").value == 1.0  # clamped
    assert PridictEngineAdapter._efficiency(-50.0, cell_line="HEK").value == 0.0  # clamped


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_efficiency_rejects_non_finite_score(bad: float) -> None:
    # A non-finite score is corruption, not a prediction. `max(0.0, nan)` is `0.0`, so a NaN
    # cell in the PRIDICT2 output CSV would silently become a confident "won't edit" 0.0
    # (indistinguishable from a real low score) and `inf` a perfect 1.0. Fail closed, like
    # the module-wide finiteness contract — finite out-of-range values still clamp above.
    with pytest.raises(ValueError, match="not finite"):
        PridictEngineAdapter._efficiency(bad, cell_line="HEK")


def test_efficiency_ood_computed_from_cell_line_not_hardcoded() -> None:
    # The trained PRIDICT2 path computes its OOD flag from the cell context — at
    # least as honest as the heuristic baseline — rather than hardcoding True.
    assert PridictEngineAdapter._efficiency(78.854, cell_line="HEK").in_distribution is True
    assert PridictEngineAdapter._efficiency(78.854, cell_line="HeLa").in_distribution is False


# -- model-zoo gate (CI) ------------------------------------------------------


def test_pridict_engine_model_card_is_mit() -> None:
    card = PridictEngineAdapter().model_card()
    assert card.name == "pridict2"
    assert card.license == "MIT"  # permits research and commercial use


def test_pridict_engine_requires_consent() -> None:
    # PRIDICT2's card has no pinned hash -> the authorize gate refuses without consent.
    with pytest.raises(ConsentError):
        PridictEngineAdapter().resolve_weights()


def test_pridict_engine_consent_records_provenance() -> None:
    adapter = PridictEngineAdapter(consent=True)
    assert adapter.resolve_weights() is None  # hub-resolved, no pinned artifact
    checkpoint = adapter.model_checkpoint()
    assert checkpoint is not None and checkpoint.license == "MIT"


def test_pridict_engine_design_rejects_invalid_cell_line() -> None:
    # Validated before any subprocess / model load.
    with pytest.raises(ValueError, match="cell_line"):
        PridictEngineAdapter(consent=True).design("ACGT(A/G)ACGT", cell_line="HeLa")


# -- opt-in: real PRIDICT2 run, golden parity ---------------------------------


@pytest.mark.real_weights
def test_pridict_engine_golden(tmp_path: Path) -> None:
    """The adapter reproduces PRIDICT2's top-design HEK efficiency on the golden seq.

    Opt-in: set $ALLELEFORGE_PRIDICT2_REPO to a PRIDICT2 checkout and
    $ALLELEFORGE_PRIDICT2_PYTHON to an interpreter with its dependencies. Skipped
    otherwise, so CI stays weight-free.
    """
    repo = os.environ.get("ALLELEFORGE_PRIDICT2_REPO")
    if not repo or not (Path(repo) / "pridict2_pegRNA_design.py").exists():
        pytest.skip("set ALLELEFORGE_PRIDICT2_REPO to a PRIDICT2 checkout")
    adapter = PridictEngineAdapter(repo_dir=repo, consent=True)
    designs = adapter.design(_GOLDEN_SEQUENCE, sequence_name="af_golden", cell_line="HEK", top_n=3)
    assert designs, "PRIDICT2 returned no designs"
    assert abs(designs[0].efficiency.value - _GOLDEN_TOP_HEK) < 5e-3
