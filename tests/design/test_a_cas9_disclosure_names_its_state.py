"""The nuclease vertical's flags and rationale, asserted by value rather than by shape.

Three of `design/cas9.py`'s confirmed mutation survivors were disclosure inversions that
existing tests could not see, each blind in a different way:

* `assert any(f.startswith("hdr-donor:") for f in candidate.flags)` — a **prefix** check.
  Inverting `if donor is None` labels a candidate that *has* a template
  ``hdr-donor:none``, which still starts with ``hdr-donor:``.
* `assert "HDR donor" in candidate.rationale` — a **substring** check. The inverted
  sentence for a candidate with a template is "no HDR donor available", which contains
  "HDR donor".
* the `relaxed-pam` flag had no check at all in either direction.

A fourth was a **symmetric fixture**: `test_candidates_sorted_by_efficiency` lays two
copies of the same spacer in the contig, so both candidates score identically and any
order is sorted.

The common failure is asserting the *shape* of a disclosure — that something of roughly
the right form is present — when the reader acts on its value. "A template is attached"
and "no template exists" are opposite facts, and a test that accepts either has checked
that the vertical emits a string.
"""

from __future__ import annotations

import pytest

from alleleforge.design.cas9 import _candidate_sort_key, _flags, _rationale
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import PAM, Guide, HDRDonor, Spacer
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

#: A concrete PAM the model will accept for each pattern under test. `Guide` validates
#: that `pam_sequence` matches `pam.pattern`, so the fallback patterns need their own.
_CONCRETE = {"NGG": "TGG", "NG": "TG", "NRN": "TGA"}


def _guide(pam: str = "NGG") -> Guide:
    return Guide(
        spacer=Spacer(sequence=DNASequence("ACGTAACGTTACGTAACGTT")),
        pam=PAM(pattern=pam),
        pam_sequence=DNASequence(_CONCRETE[pam]),
        placement=GenomicInterval(chrom="chr1", start=100, end=120, strand=Strand.PLUS),
        cut_site=117,
    )


def _eff(value: float = 0.5, *, in_distribution: bool = True) -> Prediction[float]:
    return Prediction[float](
        value=value,
        interval=(max(0.0, value - 0.1), min(1.0, value + 0.1)),
        method=UncertaintyMethod.HEURISTIC,
        in_distribution=in_distribution,
    )


def _donor(*, blocked: bool) -> HDRDonor:
    return HDRDonor(sequence=DNASequence("A" * 60), recut_blocked=blocked)


def _donor_flags(donor: HDRDonor | None) -> tuple[str, ...]:
    return _flags(_guide(), _eff(), None, donor, None, precise=True)


# -- which of the three donor states ------------------------------------------


@pytest.mark.parametrize(
    ("donor", "expected"),
    [
        (None, "hdr-donor:none"),
        (_donor(blocked=True), "hdr-donor:recut-blocked"),
        (_donor(blocked=False), "hdr-donor:recut-not-blocked"),
    ],
)
def test_the_donor_flag_names_the_state_it_is_in(donor: HDRDonor | None, expected: str) -> None:
    """Exactly one of three, by value. A prefix check accepts all three equally."""
    flags = _donor_flags(donor)
    donor_flags = [f for f in flags if f.startswith("hdr-donor:")]
    assert donor_flags == [expected]


def test_a_candidate_with_a_template_is_never_flagged_as_having_none() -> None:
    """The inversion stated directly, since it is the one that misleads a reader.

    `hdr-donor:none` says a break is being offered for a correction it cannot make.
    Attached to a candidate that *does* carry a template, it is the safe-sounding
    direction and the wrong one.
    """
    assert "hdr-donor:none" not in _donor_flags(_donor(blocked=True))
    assert "hdr-donor:none" not in _donor_flags(_donor(blocked=False))
    assert "hdr-donor:none" in _donor_flags(None)


def test_a_disruption_intent_gets_no_donor_flag_at_all() -> None:
    """The three-state disclosure belongs to a precise intent only."""
    flags = _flags(_guide(), _eff(), None, None, None, precise=False)
    assert not [f for f in flags if f.startswith("hdr-donor:")]


# -- the rationale sentence ---------------------------------------------------


def test_the_rationale_says_a_template_is_present_not_absent() -> None:
    """Both branches contain "HDR donor", so the check must name which sentence.

    The absent-template sentence is a superstring of the phrase the old assertion
    searched for, which is why inverting the condition changed nothing.
    """
    with_donor = _rationale(_guide(), _eff(), _donor(blocked=True), precise=True)
    assert "no HDR donor available" not in with_donor
    assert "HDR donor 60 nt" in with_donor
    assert "re-cut blocked" in with_donor

    without = _rationale(_guide(), _eff(), None, precise=True)
    assert "no HDR donor available" in without
    assert "60 nt" not in without


def test_the_rationale_distinguishes_a_blocked_recut_from_an_unblocked_one() -> None:
    """ "re-cut blocked" is a substring of "re-cut NOT blocked", so assert the negative."""
    blocked = _rationale(_guide(), _eff(), _donor(blocked=True), precise=True)
    unblocked = _rationale(_guide(), _eff(), _donor(blocked=False), precise=True)
    assert "NOT blocked" not in blocked
    assert "NOT blocked" in unblocked


def test_a_disruption_rationale_mentions_no_template() -> None:
    """The non-precise branch returns before any donor clause."""
    note = _rationale(_guide(), _eff(), _donor(blocked=True), precise=False)
    assert "HDR donor" not in note
    assert "guide on + strand" in note


# -- the relaxed-PAM flag -----------------------------------------------------


def test_a_relaxed_pam_is_flagged_with_its_pattern() -> None:
    """`guide.pam.pattern != "NGG"` — untested in either direction until now.

    A fallback guide is cut less efficiently than an NGG one, so the flag is how a
    reader knows which reagent they are looking at. Inverted, every ordinary guide
    carries the caveat and every fallback guide loses it.
    """
    assert "relaxed-pam:NG" in _flags(_guide("NG"), _eff(), None, None, None, precise=False)
    assert "relaxed-pam:NRN" in _flags(_guide("NRN"), _eff(), None, None, None, precise=False)


def test_an_ngg_guide_carries_no_relaxed_pam_flag() -> None:
    flags = _flags(_guide("NGG"), _eff(), None, None, None, precise=False)
    assert not [f for f in flags if f.startswith("relaxed-pam")]


# -- the candidate sort key ---------------------------------------------------


def _candidate(eff: float, worst: float) -> DesignCandidate:
    sites = (
        (
            OffTargetSite(
                locus=GenomicInterval(chrom="chr9", start=10, end=30, strand=Strand.PLUS),
                mismatches=2,
                score=worst,
                score_method=ScoreMethod.CFD,
            ),
        )
        if worst
        else ()
    )
    return DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        efficiency=_eff(eff),
        offtarget=OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites),
        rationale="r",
    )


def test_the_sort_key_ranks_higher_efficiency_first() -> None:
    """Two candidates differing on efficiency alone, which the old fixture could not do.

    `test_candidates_sorted_by_efficiency` places two copies of one spacer, so both
    candidates score identically and `effs == sorted(effs, reverse=True)` holds whatever
    the key returns — including a key that ignores efficiency entirely.
    """
    low, high = _candidate(0.2, 0.0), _candidate(0.9, 0.0)
    assert _candidate_sort_key(high) < _candidate_sort_key(low)
    assert sorted([low, high], key=_candidate_sort_key) == [high, low]


def test_the_sort_key_breaks_an_efficiency_tie_on_off_target() -> None:
    """The second term, on a pair tied on the first."""
    risky, clean = _candidate(0.5, 0.8), _candidate(0.5, 0.1)
    assert sorted([risky, clean], key=_candidate_sort_key) == [clean, risky]


def test_the_sort_key_treats_a_missing_axis_as_the_reassuring_extreme() -> None:
    """An unmeasured axis must not sort a candidate to the top by accident."""
    measured = _candidate(0.7, 0.0)
    unscored = DesignCandidate(chemistry=Chemistry.CAS9_NUCLEASE, rationale="r")
    assert _candidate_sort_key(measured) < _candidate_sort_key(unscored)
