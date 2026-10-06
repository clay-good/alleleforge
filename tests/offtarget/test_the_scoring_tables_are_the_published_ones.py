"""The off-target weight tables, pinned to sources the code does not control.

A constant-mutation sweep of `offtarget/scoring.py` found 34 of the 36 weights in these two
tables free to change by 10% with the suite green. The existing tests compared a score
against `CFD_PAM_WEIGHTS["AG"]`, the table under test, so editing the table moved both sides
together. Only the two PAM-proximal MIT weights and the `AG`/`GG` PAM entries were reached
by an independent golden.

* **CFD PAM weights.** The module docstring says they "default to the published Doench 2016
  matrix (vendored in `cfd_matrix.json`)". The scorer, though, reads the hand-typed
  `CFD_PAM_WEIGHTS` dict, and the vendored file's own `pam` table, the copy that was
  cross-verified against CRISPOR and CRISPRitz, is never consumed. The two are bound here,
  so the docstring stays true.
* **MIT (Hsu 2013) position weights.** There is no vendored copy. The expected values are
  CRISPOR's `hitScoreM` (crispor.py, maximilianh/crisporWebsite), the same tool the CFD
  matrix was verified against, checked identical on 2026-10-05.
"""

from __future__ import annotations

import json

import pytest

from alleleforge.offtarget.scoring import CFD_MATRIX_FILE, CFD_PAM_WEIGHTS, MIT_WEIGHTS

#: CRISPOR `hitScoreM`, transcribed from its source rather than from this module.
_CRISPOR_HIT_SCORE_M = (
    0, 0, 0.014, 0, 0, 0.395, 0.317, 0, 0.389, 0.079,
    0.445, 0.508, 0.613, 0.851, 0.732, 0.828, 0.615, 0.804, 0.685, 0.583,
)  # fmt: skip


def test_the_pam_weights_scored_are_the_vendored_published_ones() -> None:
    vendored = json.loads(CFD_MATRIX_FILE.read_text(encoding="utf-8"))["pam"]
    assert set(CFD_PAM_WEIGHTS) == set(vendored)
    for dinucleotide, weight in vendored.items():
        assert CFD_PAM_WEIGHTS[dinucleotide] == pytest.approx(weight, abs=1e-9), dinucleotide


def test_the_mit_weights_are_crispor_s() -> None:
    assert MIT_WEIGHTS == pytest.approx(_CRISPOR_HIT_SCORE_M, abs=0)


_SP = "GACCATGCAACCTTGAACGT"  # 20 nt


def test_a_weight_just_above_one_is_refused_and_one_is_not() -> None:
    from alleleforge.offtarget.scoring import cfd_score

    assert cfd_score(_SP, _SP, "AGG", pam_weights={"GG": 1.0}) == 1.0
    with pytest.raises(ValueError, match="outside"):
        cfd_score(_SP, _SP, "AGG", pam_weights={"GG": 1.05})


def test_a_pam_the_table_does_not_weight_scores_zero() -> None:
    from alleleforge.offtarget.scoring import cfd_score

    # "GN" is no dinucleotide in the table: no published activity, so no score.
    assert cfd_score(_SP, _SP, "AGN") == 0.0


def test_a_mismatch_the_table_does_not_weight_scores_zero() -> None:
    from alleleforge.offtarget.scoring import (
        cas12a_cfd_score,
        cfd_score,
        published_cfd_mismatch_weights,
    )

    # The published matrix has no weight for a mismatch against an `N`; the module's
    # contract is that an unweighted mismatch collapses the score rather than guessing.
    target = _SP[:10] + "N" + _SP[11:]
    assert cfd_score(_SP, target, "AGG", mismatch_weights=published_cfd_mismatch_weights()) == 0.0
    # The same holds for an injected Cas12a table that lacks the key.
    assert cas12a_cfd_score(_SP, _SP[:5] + "A" + _SP[6:], "TTTA", mismatch_weights={}) == 0.0
