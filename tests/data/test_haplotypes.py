"""Tests for phased-haplotype panels and the 1000G / HGDP wrappers."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.haplotypes import HaplotypePanel
from alleleforge.data.hgdp import HGDP
from alleleforge.data.thousand_genomes import ThousandGenomes
from alleleforge.types.sequence import GenomicInterval, Strand


def _interval(start: int = 60100, end: int = 60160) -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=start, end=end, strand=Strand.PLUS)


def test_panel_enumerates_nonreference_haplotypes(haplotypes_tsv: Path) -> None:
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="1000g")
    haps = panel.common_haplotypes(_interval())
    ids = [h.hap_id for h in haps]
    assert ids == ["H1", "H2"]  # sorted by descending max frequency
    assert all(not h.is_reference for h in haps)


def test_reference_haplotype_included_on_request(haplotypes_tsv: Path) -> None:
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="1000g")
    haps = panel.common_haplotypes(_interval(), include_reference=True)
    assert haps[0].hap_id == "HREF"  # 0.95 EUR is the most common
    assert haps[0].is_reference


def test_haplotype_carries_variants_and_populations(haplotypes_tsv: Path) -> None:
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="1000g")
    h2 = next(h for h in panel.common_haplotypes(_interval()) if h.hap_id == "H2")
    assert len(h2.variants) == 2
    assert h2.variants[0].chrom == "chr2"
    assert h2.variants[0].pos == 60149  # parsed as 0-based directly
    assert set(h2.populations) == {"AFR", "EUR"}
    assert h2.source == "1000g"


def test_population_and_frequency_filter(haplotypes_tsv: Path) -> None:
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="1000g")
    haps = panel.common_haplotypes(_interval(), min_freq=0.01, populations=["EUR"])
    assert [h.hap_id for h in haps] == ["H1"]  # H2 is EUR 0.001 < 0.01


def test_non_overlapping_interval_is_empty(haplotypes_tsv: Path) -> None:
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="1000g")
    assert panel.common_haplotypes(_interval(70000, 70100)) == []


def test_query_naming_mismatch_still_resolves(haplotypes_tsv: Path) -> None:
    # The fixture panel is chr-named ("chr2"); a bare-named query ("2") — the
    # 1000G/HGDP-VCF-vs-hg38-reference case — must still hit the bucket, or the
    # haplotype-aware off-target pass silently returns nothing (a fail-open).
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="1000g")
    bare = GenomicInterval(chrom="2", start=60100, end=60160, strand=Strand.PLUS)
    assert [h.hap_id for h in panel.common_haplotypes(bare)] == ["H1", "H2"]


def test_thousand_genomes_wrapper(haplotypes_tsv: Path) -> None:
    tg = ThousandGenomes.from_tsv(haplotypes_tsv)
    assert tg.source == "1000g"
    assert "EUR" in tg.populations
    assert [h.hap_id for h in tg.common_haplotypes(_interval())] == ["H1", "H2"]


def test_hgdp_wrapper(haplotypes_tsv: Path) -> None:
    hgdp = HGDP.from_tsv(haplotypes_tsv)
    assert hgdp.source == "hgdp"
    assert "africa" in hgdp.populations
    # the same fixture is reused; only the source label differs
    assert hgdp.common_haplotypes(_interval())[0].source == "hgdp"


def test_missing_header_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tsv"
    bad.write_text("H1\tchr2\t60000\t60300\tAFR\t0.2\t.\n")
    with pytest.raises(ValueError, match="missing its"):
        HaplotypePanel.from_tsv(bad, source="1000g")
