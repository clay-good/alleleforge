"""Tests for dbSNP rsID <-> locus resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.types.sequence import GenomicInterval, Strand


def test_locus_lookup_and_coordinate_conversion(dbsnp_tsv: Path) -> None:
    db = DbSnpDB.from_tsv(dbsnp_tsv)
    var = db.locus("rs114518452")
    assert var.chrom == "chr2"
    assert var.pos == 60200  # 1-based 60201 -> 0-based
    assert var.ref == "G" and var.alt == "A"


def test_len(dbsnp_tsv: Path) -> None:
    assert len(DbSnpDB.from_tsv(dbsnp_tsv)) == 3


def test_unknown_rsid_raises(dbsnp_tsv: Path) -> None:
    db = DbSnpDB.from_tsv(dbsnp_tsv)
    with pytest.raises(KeyError, match="no dbSNP record"):
        db.locus("rs999999")


def test_rsids_at_interval(dbsnp_tsv: Path) -> None:
    db = DbSnpDB.from_tsv(dbsnp_tsv)
    region = GenomicInterval(chrom="chr2", start=60000, end=60250, strand=Strand.PLUS)
    ids = sorted(str(r) for r in db.rsids_at(region))
    assert ids == ["rs114518452", "rs334"]


def test_no_chr_prefix_option(dbsnp_tsv: Path) -> None:
    db = DbSnpDB.from_tsv(dbsnp_tsv, add_chr_prefix=False)
    assert db.locus("rs334").chrom == "2"


def test_variant_without_rsid_rejected() -> None:
    from alleleforge.types.variant import Variant

    with pytest.raises(ValueError, match="has no rsid"):
        DbSnpDB([Variant(chrom="chr2", pos=1, ref="A", alt="T")])


def test_missing_rsid_column_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tsv"
    bad.write_text("2\t60100\tA\tT\n")  # no header line
    with pytest.raises(ValueError, match="missing its"):
        DbSnpDB.from_tsv(bad)
