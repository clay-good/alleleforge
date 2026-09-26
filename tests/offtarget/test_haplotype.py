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


def test_haplotype_panel_in_other_naming_style_is_reconciled(make_reference: MakeRef) -> None:
    # A 1000G/HGDP panel named Ensembl-style ("2") against a UCSC-named ("chr2")
    # reference must still create its de-novo site — a raw membership check would
    # silently skip every haplotype (zero haplotype-aware off-targets), even though
    # reference.fetch reconciles the name. The emitted hit is labeled in the
    # reference's naming style so it dedups against the reference pass.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = Haplotype(
        hap_id="H1",
        interval=GenomicInterval(chrom="2", start=10, end=40, strand=Strand.PLUS),
        variants=(Variant(chrom="2", pos=32, ref="T", alt="G"),),
        frequencies={"AFR": 0.2},
        source="1000g",
    )
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert len(sites) == 1
    hit, prov = sites[0]
    assert hit.chrom == "chr2"  # rebound to the reference's naming
    assert prov.origin is SiteOrigin.POPULATION


def test_below_threshold_population_excluded_from_ancestry(make_reference: MakeRef) -> None:
    # AFR carries the haplotype above threshold; EUR is present but below min_freq.
    # Only the carrying population may appear in the site's populations *and*
    # ancestries, so a below-threshold population cannot inflate the per-ancestry
    # off-target burden in OffTargetReport.ancestry_stratification(). This exercises
    # the populations=None path, which previously kept the full frequency dict.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="T", alt="G"),), {"AFR": 0.2, "EUR": 0.0005})
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert len(sites) == 1
    _, prov = sites[0]
    assert prov.populations == ("AFR",)
    assert set(prov.ancestries) == {"AFR"}


def test_zero_min_freq_with_uncarried_population_does_not_crash(make_reference: MakeRef) -> None:
    # A requested super-population the haplotype has no frequency for must not enter
    # the carrying set — a `.get(p, 0.0) >= min_freq` filter admitted it at min_freq<=0
    # (0.0 >= 0.0) and then KeyError'd on `frequencies[p]`, aborting the whole search.
    # This path is CLI-reachable via `off-target --maf 0 --populations AFR,EUR`, and a
    # region-frequent haplotype carrying only a subset of super-populations is the norm.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="T", alt="G"),), {"AFR": 0.2})  # no EUR
    sites = enumerate_haplotype_sites(
        SPACER, NRG, reference=ref, haplotypes=[hap], populations=["AFR", "EUR"], min_freq=0.0
    )
    assert len(sites) == 1
    _, prov = sites[0]
    # EUR is not recorded, so it never enters the carrying set or the ancestry map.
    assert prov.populations == ("AFR",)
    assert set(prov.ancestries) == {"AFR"}


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


def test_partial_haplotype_applies_non_clashing_subset(make_reference: MakeRef) -> None:
    # A haplotype with one ref-clashing variant (pos 15 asserts 'A' where the build
    # has 'T') and one PAM-creating variant (pos 32 T>G). The whole haplotype must
    # no longer be discarded: the created site is still nominated, the clashing
    # variant is skipped and recorded, and it is absent from the causal allele.
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap(
        (
            Variant(chrom="chr2", pos=15, ref="A", alt="G"),  # clashes: build has 'T'
            Variant(chrom="chr2", pos=32, ref="T", alt="G"),  # creates the CGG PAM
        ),
        {"AFR": 0.2},
    )
    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert len(sites) == 1
    hit, prov = sites[0]
    assert hit.mismatches == 0  # the in-protospacer clashing variant was not applied
    assert prov.causal_allele == "chr2:32:T>G"
    assert prov.skipped_variants == ("chr2:15:A>G",)


# -- the safety threshold is "at or above", in both places it is applied --------
#
# Two separate comparisons implement one rule, and the code says so: "a population
# 'carries' the haplotype only at or above the safety threshold". `min_freq` gates whether
# the haplotype is scanned at all (`max_freq(...) < min_freq` skips it) and, separately,
# which populations are named as carrying it (`frequencies[p] >= min_freq`). The
# below-threshold case is covered; equality was not, so tightening either comparison
# dropped a haplotype, or an ancestry, that sits exactly on the line the caller drew.


def test_a_haplotype_exactly_at_the_threshold_is_still_scanned(make_reference: MakeRef) -> None:
    """`max_freq(...) < min_freq` skips only what is *below* the line."""
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="T", alt="G"),), {"AFR": 0.2})

    at_threshold = enumerate_haplotype_sites(
        SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.2
    )
    assert len(at_threshold) == 1, "a haplotype at exactly the threshold must be scanned"

    above = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.19)
    assert len(above) == 1
    below = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.21)
    assert below == [], "and one below it must not be"


def test_a_population_exactly_at_the_threshold_is_named_as_carrying(
    make_reference: MakeRef,
) -> None:
    """`frequencies[p] >= min_freq` — the ancestry attribution side of the same line.

    Tightened to `>`, an ancestry recorded at exactly the threshold is dropped from
    `populations`, so `ancestry_stratification` reports no per-ancestry burden for a
    population the caller's own cut-off includes — the axis reads "not measured" for a
    group that is in fact carrying.
    """
    ref = make_reference({"chr2": PAD + SPACER + "CGT" + PAD})
    hap = _hap((Variant(chrom="chr2", pos=32, ref="T", alt="G"),), {"AFR": 0.2, "EUR": 0.05})

    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.2)
    assert len(sites) == 1
    _, prov = sites[0]
    assert "AFR" in prov.populations, "an ancestry exactly at the threshold carries it"
    assert "EUR" not in prov.populations, "and one below it does not"


def test_a_hit_touching_one_of_two_applied_variants_is_attributed(
    make_reference: MakeRef,
) -> None:
    """Attribution is `any(...)` over the applied variants' spans, not `all(...)`.

    A haplotype is a set of co-inherited alleles, and a hit needs to overlap only the one
    that made it dangerous. Every existing two-variant fixture placed both variants inside
    the protospacer, so the hit touched both and `any` and `all` agreed. With `all`, a hit
    overlapping one variant and not the other is dropped — and the more variants a
    haplotype carries, the more certainly every hit is discarded, so the richest
    haplotypes lose their off-target sites first.
    """
    contig = PAD + SPACER + "CGT" + PAD
    ref = make_reference({"chr2": contig})
    window = GenomicInterval(chrom="chr2", start=0, end=len(contig), strand=Strand.PLUS)
    hap = Haplotype(
        hap_id="H2",
        interval=window,
        variants=(
            Variant(chrom="chr2", pos=32, ref=contig[32], alt="G"),  # creates the PAM
            Variant(chrom="chr2", pos=38, ref=contig[38], alt="A"),  # past the hit's reach
        ),
        frequencies={"AFR": 0.2},
        source="1000g",
    )

    sites = enumerate_haplotype_sites(SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001)
    assert len(sites) == 1, "the hit overlaps one applied variant and must be attributed"
    hit, prov = sites[0]
    # The distant variant is applied and named, but is not what the hit overlaps.
    assert hit.end <= 38, "the fixture's hit must not reach the second variant"
    assert "chr2:32:T>G" in (prov.causal_allele or "")


def test_an_indel_bearing_haplotype_reports_its_hits_at_reference_coordinates(
    make_reference: MakeRef,
) -> None:
    """A hit found on the alt window must be lifted back to where it is in the reference.

    `applied_edits` records each applied variant as a **window-local** offset,
    `(v.pos - start, len(ref), len(alt))`, and `_reindex_alt_hits` uses those offsets to
    map alt-window coordinates back to genomic ones. Getting them wrong does not drop a
    site: it reports one at the wrong locus, which is worse than missing it, because the
    coordinates are what somebody would go and look at.

    Two coincidences hid this. Every existing fixture's haplotype carries only SNVs, and
    for length-preserving edits the lift is the identity whatever offsets it is given; and
    every fixture's interval starts at 0, so the window start clamps to 0 and
    `v.pos - start` equals `v.pos + start`. This fixture breaks both: a four-base deletion
    upstream of the protospacer, and an interval far enough into the contig that the
    window starts at 46. With the offsets mis-signed the site moves three bases.

    The assertion needs no knowledge of the lift's arithmetic: the protospacer is at one
    place in the reference, so adding an upstream deletion to the haplotype must not move
    where the hit is reported.
    """
    lead = "ACGTACGTACGTACGTACGT" * 4
    contig = lead + SPACER + "CGT" + PAD
    ref = make_reference({"chr2": contig})
    pam_t = len(lead) + len(SPACER)
    window = GenomicInterval(chrom="chr2", start=70, end=len(contig), strand=Strand.PLUS)
    creates_the_pam = Variant(chrom="chr2", pos=pam_t + 2, ref=contig[pam_t + 2], alt="G")
    upstream_deletion = Variant(chrom="chr2", pos=72, ref=contig[72:76], alt=contig[72])

    def _loci(variants: tuple[Variant, ...]) -> list[tuple[int, int]]:
        hap = Haplotype(
            hap_id="H3",
            interval=window,
            variants=variants,
            frequencies={"AFR": 0.2},
            source="1000g",
        )
        sites = enumerate_haplotype_sites(
            SPACER, NRG, reference=ref, haplotypes=[hap], min_freq=0.001
        )
        return [(h.start, h.end) for h, _ in sites]

    without = _loci((creates_the_pam,))
    assert without == [(len(lead), pam_t)], "the control must find the protospacer in place"
    assert _loci((upstream_deletion, creates_the_pam)) == without, (
        "an upstream deletion changed where the hit is reported in the reference"
    )
