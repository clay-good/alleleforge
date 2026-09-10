"""A PE3 candidate is two U6-driven spacers, and only one of them was ever checked.

`spacer_quality_flags` exists because Pol III caveats are "properties of an sgRNA spacer as
a *transcribed reagent*, not of the chemistry that uses it" — its own docstring records the
round where the checks lived in the prime vertical alone and the other two chemistries
reported `clean` on an identical problem. The same gap survived one level down: the prime
vertical applied them to the pegRNA spacer and never to the nicking guide's.

That is not cosmetic. `TTTT` terminates Pol III transcription, so a nicking guide carrying
one is truncated and never nicks — the candidate behaves as PE2 while the menu says PE3b,
the flags say `pe3b`, and the report prints ngRNA cloning oligos for a reagent that will not
work. The prefixed flags say which of the two spacers is at fault, because that is the whole
actionable content: one is re-picked by changing the edit, the other by picking another nick.
"""

from __future__ import annotations

from alleleforge.design.prime import _flags
from alleleforge.report.builder import CAVEAT_FLAGS, DESCRIPTIVE_FLAGS


class _Spacer:
    def __init__(self, sequence: str) -> None:
        self.sequence = sequence


class _Guide:
    def __init__(self, sequence: str) -> None:
        self.spacer = _Spacer(sequence)
        self.seed_disrupting = True
        self.nick_offset = 60


class _PegRNA:
    def __init__(self, spacer: str, nicking: str | None) -> None:
        self.spacer = _Spacer(spacer)
        self.nicking_guide = _Guide(nicking) if nicking is not None else None
        self.is_epegrna = False
        self.templated_edit_length = 1


class _Prediction:
    in_distribution = True


_CLEAN = "GACCTGACTCCTGAGGAGAA"  # 5' G, in-band GC, no TTTT


def _flags_for(pegrna_spacer: str, nicking_spacer: str | None) -> tuple[str, ...]:
    return _flags(
        _PegRNA(pegrna_spacer, nicking_spacer),  # type: ignore[arg-type]
        _Prediction(),  # type: ignore[arg-type]
        None,
        None,
    )


def test_a_nicking_guide_that_cannot_be_transcribed_is_flagged() -> None:
    flags = _flags_for(_CLEAN, "GACCTTTTCTCCTGAGGAGA")
    assert "ngrna-pol3-terminator" in flags
    # And not confused with the pegRNA's own, which is clean here.
    assert "pol3-terminator" not in flags


def test_the_pegrna_and_the_nicking_guide_are_told_apart() -> None:
    flags = _flags_for("GACCTTTTCTCCTGAGGAGA", "GACCTTTTCTCCTGAGGAGA")
    assert "pol3-terminator" in flags
    assert "ngrna-pol3-terminator" in flags


def test_a_clean_pair_carries_neither() -> None:
    flags = _flags_for(_CLEAN, _CLEAN)
    assert not [f for f in flags if f.startswith("ngrna-")]


def test_a_pe2_candidate_has_nothing_to_say_about_a_guide_it_does_not_have() -> None:
    flags = _flags_for(_CLEAN, None)
    assert not [f for f in flags if f.startswith("ngrna-")]


def test_the_gc_flag_carries_the_nicking_guides_own_value() -> None:
    """A reader judges the margin, not the verdict — so it must be *that* spacer's GC."""
    flags = _flags_for(_CLEAN, "GAAAAAAAAAATAAAAAAAA")
    gc = next(f for f in flags if f.startswith("ngrna-gc-out-of-band"))
    assert gc == "ngrna-gc-out-of-band:0.05"


def test_every_new_flag_says_what_it_means_for_a_pe3_run() -> None:
    """A hazard whose sentence is the pegRNA's would send the reader to the wrong reagent."""
    assert "nicking guide" in CAVEAT_FLAGS["ngrna-pol3-terminator"]
    assert "PE2" in CAVEAT_FLAGS["ngrna-pol3-terminator"]
    assert "nicking guide" in CAVEAT_FLAGS["ngrna-gc-out-of-band"]
    assert "ngrna-no-5prime-g" in DESCRIPTIVE_FLAGS
