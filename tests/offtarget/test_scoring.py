"""Tests for CFD, MIT, and the Cas12a CFD-analog scorers."""

from __future__ import annotations

import pytest

from alleleforge.offtarget.scoring import (
    CFD_PAM_WEIGHTS,
    Cas12aCfdScorer,
    CfdScorer,
    MitScorer,
    cas12a_cfd_score,
    cfd_score,
    mit_score,
    published_cfd_mismatch_weights,
)

_SP = "GACCATGCAACCTTGAACGT"  # 20 nt


def _sub(seq: str, pos: int, base: str) -> str:
    return seq[:pos] + base + seq[pos + 1 :]


# -- MIT / Hsu ----------------------------------------------------------------


def test_mit_perfect_match_is_one() -> None:
    assert mit_score(_SP, _SP) == 1.0


def test_mit_distal_mismatch_tolerated() -> None:
    # position 0 (PAM-distal) has weight 0.0 -> no penalty
    assert mit_score(_SP, _sub(_SP, 0, "T" if _SP[0] != "T" else "A")) == 1.0


def test_mit_proximal_single_mismatch_worked_value() -> None:
    # position 19 (PAM-proximal) weight 0.583 -> score 1 - 0.583 = 0.417
    other = "A" if _SP[19] != "A" else "C"
    assert mit_score(_SP, _sub(_SP, 19, other)) == pytest.approx(0.417, abs=1e-3)


def test_mit_two_mismatch_worked_value() -> None:
    seq = _sub(_sub(_SP, 18, "A" if _SP[18] != "A" else "C"), 19, "A" if _SP[19] != "A" else "C")
    # (1-0.685)(1-0.583) * 1/(((19-1)/19)*4+1) * 1/4 = 0.006857
    assert mit_score(_SP, seq) == pytest.approx(0.006857, abs=1e-5)


def test_mit_length_guard() -> None:
    with pytest.raises(ValueError, match="20-nt"):
        mit_score("ACGT", "ACGT")


# -- CFD ----------------------------------------------------------------------


def test_cfd_perfect_ngg_is_one() -> None:
    assert cfd_score(_SP, _SP, "TGG") == 1.0


def test_cfd_pam_weights_applied() -> None:
    assert cfd_score(_SP, _SP, "TAG") == pytest.approx(CFD_PAM_WEIGHTS["AG"])
    assert cfd_score(_SP, _SP, "TGA") == pytest.approx(CFD_PAM_WEIGHTS["GA"])
    assert cfd_score(_SP, _SP, "TAA") == 0.0  # AA PAM -> no activity


def test_cfd_seed_mismatch_penalized_more_than_distal() -> None:
    distal = cfd_score(_SP, _sub(_SP, 0, "A" if _SP[0] != "A" else "C"), "TGG")
    seed = cfd_score(_SP, _sub(_SP, 19, "A" if _SP[19] != "A" else "C"), "TGG")
    assert distal > seed
    assert 0.0 < seed < 1.0 < distal + 1e-9


def test_cfd_accepts_published_table_injection() -> None:
    seq = _sub(_SP, 5, "A" if _SP[5] != "A" else "C")
    weights = {(_SP[5], seq[5], 5): 0.5}
    assert cfd_score(_SP, seq, "TGG", mismatch_weights=weights) == pytest.approx(0.5)


def test_cfd_length_guard() -> None:
    with pytest.raises(ValueError, match="same length"):
        cfd_score("ACGT", "ACG", "TGG")


# -- Cas12a -------------------------------------------------------------------


def test_cas12a_pam_and_seed() -> None:
    assert cas12a_cfd_score(_SP, _SP, "TTTA") == 1.0  # TTTV
    assert cas12a_cfd_score(_SP, _SP, "AAAA") == pytest.approx(0.05)  # non-canonical PAM
    # Cas12a seed is at the 5' end: a mismatch at position 0 hurts more than at 19
    proximal = cas12a_cfd_score(_SP, _sub(_SP, 0, "A" if _SP[0] != "A" else "C"), "TTTA")
    distal = cas12a_cfd_score(_SP, _sub(_SP, 19, "A" if _SP[19] != "A" else "C"), "TTTA")
    assert proximal < distal


# -- scorer classes -----------------------------------------------------------


def test_mit_unequal_length_guard() -> None:
    with pytest.raises(ValueError, match="same length"):
        mit_score("A" * 20, "A" * 19)


def test_cas12a_length_guard() -> None:
    with pytest.raises(ValueError, match="same length"):
        cas12a_cfd_score("ACGT", "ACG", "TTTA")


def test_cas12a_injected_weights() -> None:
    target = _sub(_SP, 0, "A" if _SP[0] != "A" else "C")
    weights = {(_SP[0], target[0], 0): 0.3}
    assert cas12a_cfd_score(_SP, target, "TTTA", mismatch_weights=weights) == pytest.approx(0.3)


def test_scorer_classes_dispatch() -> None:
    assert CfdScorer().score(_SP, _SP, "TGG") == 1.0
    assert MitScorer().score(_SP, _SP, "TGG") == 1.0
    assert Cas12aCfdScorer().score(_SP, _SP, "TTTA") == 1.0
    assert CfdScorer().name == "CFD"
    assert MitScorer().method.value == "mit"


# -- scoring-time weight validation -------------------------------------------


def test_out_of_range_mismatch_weight_caught_at_scoring_time() -> None:
    # A supplied weight above 1.0 would drive the score out of [0, 1] and only
    # fail later in the OffTargetSite validator; catch it here with a clear message.
    sp = _sub(_SP, 5, "A")  # a real A->C mismatch at position 5
    proto = _sub(sp, 5, "C")
    with pytest.raises(ValueError, match=r"CFD mismatch .* outside \[0, 1\]"):
        cfd_score(sp, proto, "TGG", mismatch_weights={("A", "C", 5): 1.3})


def test_negative_mismatch_weight_rejected() -> None:
    sp = _sub(_SP, 5, "A")
    proto = _sub(sp, 5, "C")
    with pytest.raises(ValueError, match=r"outside \[0, 1\]"):
        cfd_score(sp, proto, "TGG", mismatch_weights={("A", "C", 5): -0.1})


def test_valid_injected_weight_still_scores() -> None:
    sp = _sub(_SP, 5, "A")
    proto = _sub(sp, 5, "C")
    score = cfd_score(sp, proto, "TGG", mismatch_weights={("A", "C", 5): 0.5})
    assert 0.0 <= score <= 1.0


# -- scorer matrix identity (honest labeling) ---------------------------------


def test_cfd_scorer_reports_matrix_identity() -> None:
    # The default is now the published Doench 2016 matrix; the approximation is opt-in.
    assert CfdScorer().matrix == "doench-2016-cfd"
    assert CfdScorer(approximate=True).matrix == "doench-2016-seed-tolerance-approximation"
    # injecting a custom table changes the recorded identity
    assert CfdScorer({("A", "C", 5): 0.5}).matrix == "custom-mismatch-matrix"
    assert CfdScorer(matrix="doench-2016-published").matrix == "doench-2016-published"


def test_cas12a_scorer_matrix_is_flagged_unvalidated() -> None:
    assert "unvalidated" in Cas12aCfdScorer().matrix


def test_mit_scorer_matrix_identity() -> None:
    assert MitScorer().matrix == "hsu-2013-position-weights"


# -- published CFD matrix (Doench 2016) ---------------------------------------


def test_published_cfd_matrix_has_expected_anchor_values() -> None:
    # The vendored matrix is the Doench 2016 CFD table, cross-verified byte-for-byte
    # against CRISPOR and CRISPRitz. Pin a few authoritative anchor weights so a
    # corrupted or swapped data file is caught. Keys are (spacer, target, 0-based pos).
    table = published_cfd_mismatch_weights()
    assert len(table) == 240  # 12 mismatch types x 20 positions
    assert table[("C", "A", 0)] == pytest.approx(1.0)  # PAM-distal pos 1: fully tolerated
    assert table[("T", "G", 9)] == pytest.approx(0.5)
    assert table[("G", "T", 13)] == pytest.approx(0.266666667)
    assert table[("A", "C", 19)] == pytest.approx(0.227272727)  # PAM-proximal seed: penalized


def test_default_cfd_reproduces_published_example_scores() -> None:
    # Default CfdScorer uses the published matrix, so a known mismatch reproduces the
    # published CFD weight exactly. Build sequences differing at exactly one position.
    scorer = CfdScorer()
    base = "A" * 20
    # single mismatch spacer G / target T at position 13, NGG PAM -> weight * pam(GG)=1.0
    spacer = _sub(base, 13, "G")
    target = _sub(base, 13, "T")
    assert scorer.score(spacer, target, "AGG") == pytest.approx(0.266666667, abs=1e-9)
    # two independent mismatches multiply: (G,T,13)=0.266666667 * (A,C,19)=0.227272727
    spacer2 = _sub(spacer, 19, "A")
    target2 = _sub(target, 19, "C")
    assert scorer.score(spacer2, target2, "AGG") == pytest.approx(
        0.266666667 * 0.227272727, abs=1e-9
    )
    # a low-stringency PAM scales a perfect match by the published PAM weight
    assert scorer.score(base, base, "AAG") == pytest.approx(CFD_PAM_WEIGHTS["AG"], abs=1e-9)


def test_default_cfd_differs_from_approximation() -> None:
    # The published default and the transparent approximation are genuinely different
    # models — a seed mismatch scores differently under each.
    base = "A" * 20
    spacer, target = _sub(base, 13, "G"), _sub(base, 13, "T")
    published = CfdScorer().score(spacer, target, "AGG")
    approx = CfdScorer(approximate=True).score(spacer, target, "AGG")
    assert published != pytest.approx(approx, abs=1e-6)
