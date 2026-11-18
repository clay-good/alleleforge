"""The lookup that dedups a haplotype hit against the reference pass keyed on a pair.

`enumerate_haplotype_sites` scans the haplotype-substituted window, then asks whether
each alt hit is *created or strengthened* relative to the reference:

    if _strengthens(h, ref_best.get((h.strand, h.start, h.end)), scorer):

`_reference_best` builds that dictionary with the same `(strand, start, end)` key, and
`_strengthens(hit, None, ...)` returns `True` — "no reference hit at this placement, so
this one is created". An ordered-opposite sweep swapped the two ends of the *lookup* key,
making it `(strand, end, start)`, and the whole suite stayed green.

With the key reversed every lookup misses, so every alt hit is reported as newly created.
On a reference that already carries the site, the count goes from **0 to 2**: the
reference pass finds it, the haplotype pass finds it again, and the report presents the
same locus twice with one copy attributed to a population. This is the module whose
entire purpose is to say honestly which off-targets a population carries and which the
reference already had — inflating it is the failure it exists to prevent, and it is
invisible to any test that only asks whether haplotype-aware scanning finds anything.

The fixture is a contig holding an exact protospacer and PAM, so the reference pass has
a hit to dedup against. Both sides are checked: a variant that does not make the site
more dangerous yields nothing, and one that upgrades the PAM yields a site.
"""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.data.haplotypes import Haplotype
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.haplotype import enumerate_haplotype_sites
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import Variant

from .conftest import PAD, SPACER

NRG = PAM(pattern="NRG")
MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: The reference already carries this protospacer with a canonical `AGG` PAM, so the
#: reference pass nominates it and the haplotype pass must not nominate it again.
_CONTIG = PAD * 3 + SPACER + "AGG" + PAD * 3
_SITE = len(PAD) * 3
_BLOCK = GenomicInterval(chrom="chr2", start=5, end=len(_CONTIG) - 5, strand=Strand.PLUS)


def _hap(pos: int, alt: str) -> Haplotype:
    return Haplotype(
        hap_id="H1",
        interval=_BLOCK,
        variants=(Variant(chrom="chr2", pos=pos, ref=_CONTIG[pos], alt=alt),),
        frequencies={"AFR": 0.2},
        source="1000g",
    )


def _sites(reference: ReferenceGenome, pos: int, alt: str) -> list[object]:
    return list(
        enumerate_haplotype_sites(
            SPACER, NRG, reference=reference, haplotypes=[_hap(pos, alt)], min_freq=0.001
        )
    )


def test_the_reference_already_carries_the_site(make_reference: MakeRef) -> None:
    """The premise. Without a reference hit there is nothing to dedup against."""
    from alleleforge.offtarget.engine import search

    reference = make_reference({"chr2": _CONTIG})
    report = search(SPACER, pam=NRG, reference=reference)
    assert any(site.locus.start == _SITE for site in report.sites), [
        site.locus.start for site in report.sites
    ]


def test_a_variant_that_does_not_strengthen_adds_no_population_site(
    make_reference: MakeRef,
) -> None:
    """The dedup. This locus is the reference's, not a population's."""
    reference = make_reference({"chr2": _CONTIG})
    assert _sites(reference, _SITE + 5, "G") == []


def test_a_variant_that_upgrades_the_pam_does_add_one(make_reference: MakeRef) -> None:
    """The other side: a real strengthening must still be nominated.

    Without this, the check above would pass on an enumerator that reports nothing.
    """
    reference = make_reference({"chr2": _CONTIG})
    assert _SITE + len(SPACER) == 50
    sites = _sites(reference, _SITE + len(SPACER), "G")
    assert len(sites) == 1, sites
