"""Tests for haplotype-aware off-target evaluation."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.haplotype import enumerate_haplotype_sites
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import Variant

from .conftest import PAD, SPACER

NRG = PAM(pattern="NRG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _interval() -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=10, end=40, strand=Strand.PLUS)


def _hap(variants: tuple[Variant, ...], freqs: dict[str, float]) -> Haplotype:
    return Haplotype(
        hap_id="H1", interval=_interval(), variants=variants, frequencies=freqs, source="1000g"
    )


def test_haplotype_creates_de_novo_site(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="T", alt="G"),), {"AFR": 0.2, "EUR": 0.01})
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert len(sites) == 1
    hit, prov = sites[0]
    assert hit.mismatches == 0
    assert prov.origin is SiteOrigin.POPULATION
    assert "AFR" in prov.populations
    assert "chr2:32:T>G" in (prov.causal_allele or "")


def test_two_variant_haplotype_lists_both(make_reference: MakeRef) -> None:
    # One variant creates the PAM, a second sits in the protospacer; the
    # haplotype's causal-allele string records both.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    variants = (
        Variant(chrom="chr2", pos=32, ref="T", alt="G"),  # creates CGG PAM
        Variant(chrom="chr2", pos=12, ref=SPACER[2], alt="A" if SPACER[2] != "A" else "C"),
    )
    hap = _hap(variants, {"AFR": 0.15})
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert sites
    _, prov = sites[0]
    assert "chr2:32:T>G" in (prov.causal_allele or "")
    assert "chr2:12:" in (prov.causal_allele or "")


def test_window_with_reference_site_only_emits_created(make_reference: MakeRef) -> None:
    # The window spans a real reference site (SPACER+TGG) and a second SPACER
    # whose PAM the haplotype variant creates. Only the created site is emitted;
    # the pre-existing reference site (untouched by the variant) is not.
    contig = PAD + SPACER + "TGG" + "AAAA" + SPACER + "CGT" + PAD
    ref = make_reference({"chr2": contig})
    interval = GenomicInterval(chrom="chr2", start=10, end=60, strand=Strand.PLUS)
    hap = Haplotype(
        hap_id="H1",
        interval=interval,
        variants=(Variant(chrom="chr2", pos=59, ref="T", alt="G"),),
        frequencies={"AFR": 0.2},
        source="1000g",
    )
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert len(sites) == 1
    hit, _ = sites[0]
    assert (hit.start, hit.end) == (37, 57)  # the created site, not the [10,30) reference site


def test_reference_haplotype_skipped(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((), {"AFR": 0.9})  # no variants -> reference haplotype
    assert enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap]) == []


def test_haplotype_ref_clash_skipped(make_reference: MakeRef) -> None:
    # A variant whose ref disagrees with the build cannot be applied -> skipped.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="A", alt="G"),), {"AFR": 0.2})
    assert enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap]) == []


def test_haplotype_absent_contig_skipped(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = Haplotype(
        hap_id="HX",
        interval=GenomicInterval(chrom="chrX", start=0, end=30, strand=Strand.PLUS),
        variants=(Variant(chrom="chrX", pos=5, ref="A", alt="G"),),
        frequencies={"AFR": 0.2},
        source="1000g",
    )
    assert enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap]) == []


def test_rare_haplotype_skipped(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="T", alt="G"),), {"AFR": 0.0005})
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert sites == []
