"""`GUIDE_SPACER_RANGE` decides whether a query is a reagent or just a sequence.

An off-target report over a 17-nt query is a guide's safety profile; over a 4-mer it is
arithmetic about a 4-mer, and the report says so. The range that separates the two is a
published fact with two named sources, recorded in the constant's own comment: 17-18 nt
for the truncated SpCas9 guides of Fu et al. 2014 at the low end, 20-24 nt for Cas12a at
the high end.

Every test of that boundary derived its fixtures *from the constant* —
`GUIDE_SPACER_RANGE[0] - 1`, `parametrize(..., GUIDE_SPACER_RANGE)` — so both sides of
each assertion came from one source. Shift the range to (18, 25) and every one of those
fixtures shifts with it: a real 17-nt truncated guide would be labelled "not a guide
length" and nothing would fail. This test is the one place the numbers are written down
independently, so the range cannot drift away from the literature it cites.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.types import guide
from alleleforge.types.guide import GUIDE_SPACER_RANGE
from alleleforge.types.offtarget import OffTargetReport, headline_notes


def _report(spacer: str) -> OffTargetReport:
    """A report over ``spacer``, with everything else the minimum a report needs."""
    return OffTargetReport(spacer=spacer, pam="NGG", searched_bases=1_000, resolved_bases=1_000)


def test_the_range_is_the_literature_values() -> None:
    assert GUIDE_SPACER_RANGE == (17, 24), (
        "the guide-length range moved; 17 is Fu et al. 2014's truncated SpCas9 guide "
        "and 24 is Cas12a's upper spacer length. Change the cited sources with it."
    )


def test_the_constants_comment_still_names_both_sources() -> None:
    """The numbers are only defensible while the comment that sources them agrees."""
    text = Path(guide.__file__).read_text(encoding="utf-8")
    low, high = GUIDE_SPACER_RANGE
    assert f"{low}-18 for the truncated SpCas9 guides of Fu et al. 2014" in text
    assert f"20-{high} for Cas12a" in text


def test_a_truncated_guide_is_a_guide_and_a_seed_query_is_not() -> None:
    """Both sides, with lengths written out rather than read off the constant."""
    assert "not a guide length" not in " ".join(headline_notes(_report("A" * 17)))
    assert "not a guide length" not in " ".join(headline_notes(_report("A" * 24)))
    assert "not a guide length" in " ".join(headline_notes(_report("A" * 16)))
    assert "not a guide length" in " ".join(headline_notes(_report("A" * 25)))


def test_the_reported_sentence_quotes_the_real_range() -> None:
    """A reader is told which range they fell outside; it must be the shipped one."""
    assert "outside the 17-24 nt range a guide has" in _report("A" * 16).search_description()
