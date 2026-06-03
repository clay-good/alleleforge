"""Tests for gnomAD per-population frequency parsing and interval queries."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_missing_header_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tsv"
    bad.write_text("chr2\t60150\tC\tG\t0.02\n")
    with pytest.raises(ValueError, match="missing its"):
        GnomadDB.from_sites_tsv(bad)
