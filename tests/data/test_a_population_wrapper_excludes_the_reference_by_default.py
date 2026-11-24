"""The panel's default was tested; the HGDP wrapper's was not.

`common_haplotypes(include_reference=False)` keeps the reference (no-variant) haplotype
out of the result. It matters because these haplotypes drive the population-aware
off-target scan: the reference haplotype is what the scan is already measuring against, so
including it turns the reference sequence into a "population" site and inflates the
population-origin count and the expected burden.

`HaplotypePanel.common_haplotypes` is pinned in both directions — `tests/data/
test_haplotypes.py` asserts the default excludes it and that `include_reference=True`
brings it back. The two thin wrappers over the panel, `HGDP` and `ThousandGenomes`,
declare the same parameter again and forward it. Only one of them was reachable from a
test that asserted the default, so flipping `HGDP.common_haplotypes`'s default to `True`
survived the whole suite while the same flip on `ThousandGenomes` was killed.

**Two of three siblings tested means the third is the finding** — the same shape this log
has recorded for the base editor's `ood` flag and for cas9's. A delegation looks too
trivial to test, and a parameter that is re-declared is a parameter that can disagree with
what it delegates to.

Found by flipping the default (`scripts/mutate.py --mode dflt`).
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.data.haplotypes import HaplotypePanel
from alleleforge.data.hgdp import HGDP
from alleleforge.data.thousand_genomes import ThousandGenomes
from alleleforge.types.sequence import GenomicInterval, Strand


def _interval() -> GenomicInterval:
    return GenomicInterval(chrom="chr2", start=60100, end=60160, strand=Strand.PLUS)


def test_the_fixture_carries_a_reference_haplotype(haplotypes_tsv: Path) -> None:
    """Premise: there is a reference haplotype here to exclude.

    Without it every assertion below passes on an empty absence, which is how a filter
    comes to be "tested" by data it cannot act on.
    """
    panel = HaplotypePanel.from_tsv(haplotypes_tsv, source="hgdp")
    assert any(
        hap.is_reference for hap in panel.common_haplotypes(_interval(), include_reference=True)
    )


def test_the_hgdp_wrapper_excludes_the_reference_by_default(haplotypes_tsv: Path) -> None:
    haps = HGDP.from_tsv(haplotypes_tsv).common_haplotypes(_interval())
    assert haps, "premise: the window carries common haplotypes"
    assert not any(hap.is_reference for hap in haps), (
        "HGDP.common_haplotypes returned the reference haplotype to a caller who did "
        "not ask for it; it would enter the population-aware scan as a population site"
    )


def test_the_hgdp_wrapper_still_forwards_the_request(haplotypes_tsv: Path) -> None:
    """The default is a default, not a hardcoded exclusion."""
    haps = HGDP.from_tsv(haplotypes_tsv).common_haplotypes(_interval(), include_reference=True)
    assert any(hap.is_reference for hap in haps)


def test_the_thousand_genomes_wrapper_agrees(haplotypes_tsv: Path) -> None:
    """The sibling, asserted here too so the pair cannot drift apart again."""
    wrapper = ThousandGenomes.from_tsv(haplotypes_tsv)
    assert not any(hap.is_reference for hap in wrapper.common_haplotypes(_interval()))
    assert any(
        hap.is_reference for hap in wrapper.common_haplotypes(_interval(), include_reference=True)
    )
