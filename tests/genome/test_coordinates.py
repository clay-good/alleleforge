"""Tests for liftover and hg38-ambiguous-region flagging + Phase 1 wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.coordinates import (
    HG38_DIFFICULT_REGIONS,
    Liftover,
    RegionFlagKind,
    flag_ambiguous_regions,
)
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry
from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand


def _iv(chrom: str, start: int, end: int, strand: Strand = Strand.PLUS) -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=start, end=end, strand=strand)


# -- ambiguous-region flagging --------------------------------------------


def test_flag_recommends_t2t_in_centromere() -> None:
    rec = flag_ambiguous_regions(_iv("chr1", 122_000_000, 122_000_100))
    assert rec.recommended
    assert rec.recommended_build == "T2T-CHM13v2"
    kinds = {r.kind for r in rec.regions}
    assert RegionFlagKind.CENTROMERIC in kinds
    assert "recommend-reference:T2T-CHM13v2" in rec.candidate_flags()
    assert "ambiguous-region:centromeric" in rec.candidate_flags()
    assert "overlaps" in rec.reason


def test_flag_clears_outside_difficult_regions() -> None:
    rec = flag_ambiguous_regions(_iv("chr7", 1_000, 1_100))
    assert not rec.recommended
    assert rec.recommended_build is None
    assert rec.candidate_flags() == ()
    assert "no hg38-ambiguous region" in rec.reason


def test_flag_non_hg38_build_does_not_recommend() -> None:
    region = HG38_DIFFICULT_REGIONS[0]
    rec = flag_ambiguous_regions(
        _iv("chr1", 122_000_000, 122_000_100),
        source_build="T2T-CHM13v2",
        regions=(region,),
    )
    assert not rec.recommended


def test_flag_custom_region_table() -> None:
    from alleleforge.genome.coordinates import AmbiguousRegion

    custom = (
        AmbiguousRegion(
            interval=_iv("chrZ", 0, 1000), kind=RegionFlagKind.SEGDUP, note="synthetic"
        ),
    )
    rec = flag_ambiguous_regions(_iv("chrZ", 500, 600), regions=custom)
    assert rec.recommended
    assert rec.regions[0].note == "synthetic"


def test_flag_rejects_one_based() -> None:
    iv = GenomicInterval(
        chrom="chr1",
        start=1,
        end=10,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ONE_BASED,
    )
    with pytest.raises(ValueError, match="0-based"):
        flag_ambiguous_regions(iv)


def test_recommendation_wires_into_design_candidate() -> None:
    rec = flag_ambiguous_regions(_iv("chr1", 122_000_000, 122_000_100))
    candidate = DesignCandidate(chemistry=Chemistry.CAS9_NUCLEASE, flags=("pre-existing",))
    annotated = rec.apply_to(candidate)
    assert "pre-existing" in annotated.flags
    assert "recommend-reference:T2T-CHM13v2" in annotated.flags
    # idempotent: applying twice does not duplicate flags
    twice = rec.apply_to(annotated)
    assert twice.flags == annotated.flags


# -- liftover --------------------------------------------------------------


def test_liftover_injected_roundtrip() -> None:
    fwd = Liftover(
        lambda c, p: [("chrA", p + 200, "+", 100)], source_build="hg38", target_build="t2t"
    )
    rev = Liftover(
        lambda c, p: [("chr1", p - 200, "+", 100)], source_build="t2t", target_build="hg38"
    )
    lifted = fwd.lift_interval(_iv("chr1", 10, 20))
    assert lifted is not None
    assert (lifted.chrom, lifted.start, lifted.end) == ("chrA", 210, 220)
    back = rev.lift_interval(lifted)
    assert back is not None
    assert (back.chrom, back.start, back.end) == ("chr1", 10, 20)


def test_liftover_minus_strand_flips() -> None:
    lo = Liftover(lambda c, p: [("chrA", p, "-", 100)], source_build="hg38", target_build="t2t")
    lifted = lo.lift_interval(_iv("chr1", 10, 20, Strand.PLUS))
    assert lifted is not None
    assert lifted.strand is Strand.MINUS


def test_liftover_unmapped_position_returns_none() -> None:
    lo = Liftover(
        lambda c, p: [] if p == 19 else [("chrA", p, "+", 100)],
        source_build="hg38",
        target_build="t2t",
    )
    assert lo.lift_interval(_iv("chr1", 10, 20)) is None


def test_liftover_split_across_contigs_returns_none() -> None:
    lo = Liftover(
        lambda c, p: [("chrA" if p < 15 else "chrB", p, "+", 100)],
        source_build="hg38",
        target_build="t2t",
    )
    assert lo.lift_interval(_iv("chr1", 10, 20)) is None


def test_liftover_strand_split_returns_none() -> None:
    # The two endpoints map to different strands — an inversion boundary runs
    # through the interval. Keeping one endpoint's strand would emit a mis-oriented
    # span; fail closed instead.
    lo = Liftover(
        lambda c, p: [("chrA", p, "+" if p < 15 else "-", 100)],
        source_build="hg38",
        target_build="t2t",
    )
    assert lo.lift_interval(_iv("chr1", 10, 20)) is None


def test_liftover_length_change_returns_none() -> None:
    # A chain indel inside the interval resizes the lifted span (source 10 nt ->
    # lifted 15 nt): the lifted coordinates no longer describe the same bases, so
    # the lift is not faithful and must fail closed.
    lo = Liftover(
        lambda c, p: [("chrA", p if p < 15 else p + 5, "+", 100)],
        source_build="hg38",
        target_build="t2t",
    )
    assert lo.lift_interval(_iv("chr1", 10, 20)) is None
    # ...but an explicit tolerance can admit a known, quantified chain-gap slack.
    assert lo.lift_interval(_iv("chr1", 10, 20), length_tolerance=5) is not None


def test_convert_position_none_when_unmapped() -> None:
    lo = Liftover(lambda c, p: [], source_build="hg38", target_build="t2t")
    assert lo.convert_position("chr1", 5) is None


def test_lift_interval_rejects_empty() -> None:
    lo = Liftover(lambda c, p: [("chrA", p, "+", 100)], source_build="a", target_build="b")
    with pytest.raises(ValueError, match="empty"):
        lo.lift_interval(_iv("chr1", 10, 10))


def test_lift_interval_rejects_one_based() -> None:
    lo = Liftover(lambda c, p: [("chrA", p, "+", 100)], source_build="a", target_build="b")
    iv = GenomicInterval(
        chrom="chr1",
        start=1,
        end=10,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ONE_BASED,
    )
    with pytest.raises(ValueError, match="0-based"):
        lo.lift_interval(iv)


def test_liftover_from_real_chain_file_roundtrip(forward_chain: Path, reverse_chain: Path) -> None:
    fwd = Liftover.from_chain_file(forward_chain, source_build="hg38", target_build="t2t")
    rev = Liftover.from_chain_file(reverse_chain, source_build="t2t", target_build="hg38")
    lifted = fwd.lift_interval(_iv("chr1", 10, 20))
    assert lifted is not None
    assert (lifted.chrom, lifted.start, lifted.end) == ("chrA", 210, 220)
    back = rev.lift_interval(lifted)
    assert back is not None
    assert (back.chrom, back.start, back.end) == ("chr1", 10, 20)
