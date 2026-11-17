"""The ambiguous-region verdict quotes a coordinate, and nothing checked which one.

`ReferenceRecommendation.reason` is the sentence a reader gets when a locus sits in an
hg38-ambiguous region — or when it does not. Both branches quote the query, and an
ordered-opposite sweep swapped `self.query.start` for `self.query.end` in the negative
branch with the whole suite green.

The negative branch is the one that matters here, because it is the reassurance: *"no
hg38-ambiguous region overlaps chr1:144000000"*. Naming the far end of the window instead
of the locus asked about makes that reassurance about a different position — and the
window is `±` a margin wide, so the number is plausible either way and wrong by exactly
as much as the margin. The positive branch prints the span and is pinned by the ordering
checks beside it.

The `recommended` flag and the region list were tested; the coordinate in the sentence
was not, which is the same split this project keeps finding — the fact is checked and
the sentence carrying it is not.
"""

from __future__ import annotations

from alleleforge.genome.coordinates import ReferenceRecommendation
from alleleforge.types.sequence import GenomicInterval, Strand

_QUERY = GenomicInterval(chrom="chr1", start=144_000_000, end=144_000_200, strand=Strand.PLUS)


def _recommendation(**over: object) -> ReferenceRecommendation:
    kwargs: dict[str, object] = {
        "query": _QUERY,
        "source_build": "hg38",
        "recommended_build": None,
        "regions": (),
    }
    kwargs.update(over)
    return ReferenceRecommendation(**kwargs)  # type: ignore[arg-type]


def test_the_fixture_has_two_distinguishable_ends() -> None:
    """The premise: a zero-width query cannot tell the two ends apart."""
    assert _QUERY.start != _QUERY.end


def test_a_clear_locus_is_named_by_the_position_that_was_asked_about() -> None:
    reason = _recommendation().reason
    assert "no hg38-ambiguous region overlaps" in reason, reason
    assert reason.endswith(f"chr1:{_QUERY.start}"), reason
    assert str(_QUERY.end) not in reason, reason


def test_a_flagged_locus_names_its_whole_span_in_order() -> None:
    """The other branch, so the negative one is not carrying this file alone."""
    from alleleforge.genome.coordinates import AmbiguousRegion, RegionFlagKind

    region = AmbiguousRegion(interval=_QUERY, kind=RegionFlagKind.SEGDUP)
    reason = _recommendation(recommended_build="t2t-chm13", regions=(region,)).reason
    assert f"chr1:{_QUERY.start}-{_QUERY.end}" in reason, reason
    assert "t2t-chm13" in reason, reason
