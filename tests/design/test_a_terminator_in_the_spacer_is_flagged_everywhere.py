"""`TTTT` stops U6 transcription, and only one of three chemistries said so.

`design/spacer_quality.py` exists because the spacer caveats "are properties of an sgRNA
spacer as a *transcribed reagent*, not of the chemistry that uses it" — its own words,
written when a low-GC spacer was flagged on prime and reported clean on the other two.
Two of prime's three checks moved there. The third stayed behind, and it is the severe
one: a missing 5' G and an out-of-band GC make a guide transcribe *worse*, while `TTTT`
makes it not transcribe to full length at all — the reagent is not made.

So the same constraint was enforced three different ways: prime refuses the protospacer,
the cas9 efficiency model docks 1.5 logits, and base editing was silent. The golden
reproducibility fixture is the proof — its single `recommended` candidate is an ABE8e
sgRNA on `TTTAAACGTTTTTTTTTTTT`, flagged `gc-out-of-band:0.10` and `no-5prime-g` and
saying nothing about twelve consecutive Ts, reproduced byte-exactly on every run.

The check is in the shared module now, so every chemistry that keeps such a spacer
annotates it, and the caveat states the consequence rather than the motif.
"""

from __future__ import annotations

from alleleforge.design.spacer_quality import spacer_quality_flags
from alleleforge.report.builder import CAVEAT_FLAGS, caveats


def test_the_terminator_is_flagged() -> None:
    assert "pol3-terminator" in spacer_quality_flags("TTTAAACGTTTTTTTTTTTT")
    assert "pol3-terminator" in spacer_quality_flags("GACCTTTTAACCGGTTAACC")


def test_a_clean_spacer_is_not_flagged() -> None:
    """Three Ts are not a terminator; a flag that always fires says nothing."""
    assert spacer_quality_flags("GACCTTTAACCGGTTAACCG") == []


def test_it_leads_the_list_because_it_is_categorical() -> None:
    """A truncated transcript is a different kind of problem from a poor one."""
    flags = spacer_quality_flags("TTTAAACGTTTTTTTTTTTT")
    assert flags[0] == "pol3-terminator"


def test_it_is_a_hazard_that_names_its_consequence() -> None:
    reason = dict(caveats(("pol3-terminator",)))["pol3-terminator"]
    assert "terminates Pol III" in reason
    assert "truncated" in reason
    assert "pol3-terminator" in CAVEAT_FLAGS


def test_every_sgrna_chemistry_annotates_it() -> None:
    """The point of the shared module: one spacer property, one answer.

    Each vertical calls `spacer_quality_flags` on its own spacer, so this asserts the
    call site exists in all three rather than re-deriving the flag three times.
    """
    import inspect

    from alleleforge.design import base_editor, cas9, prime

    for module in (base_editor, cas9, prime):
        source = inspect.getsource(module)
        assert "spacer_quality_flags(" in source, f"{module.__name__} skips the shared checks"
