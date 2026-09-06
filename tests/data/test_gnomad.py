"""Tests for gnomAD per-population frequency parsing and interval queries."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.types.sequence import GenomicInterval, Strand


def _interval(start: int, end: int, chrom: str = "chr2") -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=start, end=end, strand=Strand.PLUS)


def test_parse_normalizes_to_zero_based(gnomad_tsv: Path) -> None:
    db = GnomadDB.from_sites_tsv(gnomad_tsv)
    recs = db.frequencies(_interval(60149, 60150))
    assert len(recs) == 1
    assert recs[0].ref == "C" and recs[0].alt == "G"  # 1-based 60150 -> 0-based 60149


def test_frequencies_within_interval(gnomad_tsv: Path) -> None:
    db = GnomadDB.from_sites_tsv(gnomad_tsv)
    recs = db.frequencies(_interval(60000, 60300))
    assert {r.pos for r in recs} == {60149, 60200}


def test_maf_threshold_filters_rare_alleles(gnomad_tsv: Path) -> None:
    db = GnomadDB.from_sites_tsv(gnomad_tsv)
    recs = db.frequencies(_interval(60000, 60600), maf=0.001)
    # the 60499 site has overall AF 0.0005 and max pop AF 0.001 -> kept at 0.001
    kept = {r.pos for r in recs}
    assert 60149 in kept and 60200 in kept and 60499 in kept
    strict = db.frequencies(_interval(60000, 60600), maf=0.01)
    assert 60499 not in {r.pos for r in strict}


def test_population_restriction(gnomad_tsv: Path) -> None:
    db = GnomadDB.from_sites_tsv(gnomad_tsv)
    rec = db.frequencies(_interval(60200, 60201), populations=["afr"])[0]
    assert set(rec.populations) == {"afr"}
    assert rec.populations["afr"] == 0.30


def test_max_af_and_exceeds() -> None:
    pf = PopulationFrequency(
        chrom="chr2",
        pos=60200,
        ref="G",
        alt="A",
        overall_af=0.12,
        populations={"afr": 0.30, "nfe": 0.02},
    )
    assert pf.max_af() == 0.30
    assert pf.max_af(["nfe"]) == 0.02
    assert pf.exceeds(0.2, ["afr"])
    assert not pf.exceeds(0.2, ["nfe"])
    assert pf.variant_key == "chr2:60200:G>A"


def test_empty_interval_returns_nothing(gnomad_tsv: Path) -> None:
    db = GnomadDB.from_sites_tsv(gnomad_tsv)
    assert db.frequencies(_interval(70000, 70100)) == []


def test_query_in_other_naming_style_is_reconciled() -> None:
    # A DB stored Ensembl-style ("2") queried with a UCSC-named ("chr2") interval
    # (or vice versa) must still match — otherwise a reference-vs-gnomAD naming
    # mismatch silently returns no records and population off-target augmentation
    # is empty (the reference-bias blind spot the module exists to catch).
    db = GnomadDB(
        [
            PopulationFrequency(
                chrom="2", pos=60200, ref="G", alt="A", overall_af=0.12, populations={"afr": 0.30}
            )
        ]
    )
    assert [r.pos for r in db.frequencies(_interval(60000, 60300, chrom="chr2"))] == [60200]
    # and the symmetric direction
    db2 = GnomadDB(
        [
            PopulationFrequency(
                chrom="chr2",
                pos=60200,
                ref="G",
                alt="A",
                overall_af=0.12,
                populations={"afr": 0.30},
            )
        ]
    )
    assert [r.pos for r in db2.frequencies(_interval(60000, 60300, chrom="2"))] == [60200]


def test_missing_header_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tsv"
    bad.write_text("chr2\t60150\tC\tG\t0.02\n")
    with pytest.raises(ValueError, match="missing its"):
        GnomadDB.from_sites_tsv(bad)


def test_a_percent_scaled_frequency_column_is_refused() -> None:
    """A frequency of 2.0 is a percent column, and it used to be accepted silently.

    The consequences are quiet and bad: the MAF filter admits everything, and the
    ancestry breakdown a human reads to judge whether a guide is safe in a population
    shows "200%". A scale error has to fail at the parse boundary — propagated, it
    produces a safety figure wrong by 100x that looks deliberate.
    """
    with pytest.raises(ValidationError, match="fractions, not percentages"):
        PopulationFrequency(
            chrom="chr2", pos=1, ref="A", alt="G", overall_af=1.5, populations={"afr": 2.0}
        )

    # The message names every offending field, not just the first one found.
    with pytest.raises(ValidationError) as excinfo:
        PopulationFrequency(
            chrom="chr2", pos=1, ref="A", alt="G", overall_af=50.0, populations={"afr": 80.0}
        )
    assert "overall_af=50.0" in str(excinfo.value) and "afr=80.0" in str(excinfo.value)

    # A negative frequency is equally impossible.
    with pytest.raises(ValidationError, match="outside"):
        PopulationFrequency(chrom="chr2", pos=1, ref="A", alt="G", overall_af=-0.1)

    # The boundaries are valid: a monomorphic and a fixed allele are both real.
    assert PopulationFrequency(chrom="chr2", pos=1, ref="A", alt="G", overall_af=0.0)
    assert PopulationFrequency(
        chrom="chr2", pos=1, ref="A", alt="G", overall_af=1.0, populations={"afr": 1.0}
    )


def test_available_populations_is_computed_once() -> None:
    """It is a full scan of the database and `search()` asks once per candidate.

    Measured over 200,000 records the scan costs ~49 ms, so a 470-candidate prime
    menu paid about 23 seconds for a label — and a real per-chromosome gnomAD file is
    an order of magnitude larger again. The database is immutable once constructed, so
    the answer is cached; this pins that rather than the timing, which is
    machine-dependent.
    """
    db = GnomadDB(
        [
            PopulationFrequency(
                chrom="chr1", pos=i, ref="A", alt="G", overall_af=0.05, populations={"afr": 0.1}
            )
            for i in range(50)
        ]
    )
    first = db.available_populations
    assert first == frozenset({"afr"})
    # Identity, not equality: a recomputed frozenset would be equal but not the same
    # object, so this fails if the cache is removed.
    assert db.available_populations is first


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_allele_frequency_is_rejected(bad: float) -> None:
    """`NaN` slips past a bare range comparison, and this validator survives it by shape.

    `nan > 1.0` and `nan < 0.0` are both False, so a check written as
    `if af > 1 or af < 0` admits `NaN` — which then propagates into every MAF
    comparison, where it compares False against any threshold and silently drops the
    variant from the search. The validator is written as `not 0.0 <= af <= 1.0`, whose
    negation catches it. That is correct by construction and one refactor away from not
    being, so it is pinned rather than left to the shape of an expression.

    The same property already cost this project a fix in `RankingWeights`, where a
    non-finite weight poisoned the composite the ranking sorts on.
    """
    with pytest.raises(ValidationError, match="outside"):
        PopulationFrequency(chrom="chr2", pos=1, ref="A", alt="G", overall_af=bad)
    with pytest.raises(ValidationError, match="outside"):
        PopulationFrequency(
            chrom="chr2", pos=1, ref="A", alt="G", overall_af=0.1, populations={"afr": bad}
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_haplotype_frequency_is_validated_the_same_way(bad: float) -> None:
    """The sibling source must not admit what gnomAD refuses.

    Both feed the same ancestry stratification, so a non-finite frequency reaching the
    search from either one has the same effect.
    """
    from alleleforge.data.haplotypes import Haplotype

    with pytest.raises(ValidationError):
        Haplotype(chrom="chr1", variants=(), frequencies={"afr": bad})
