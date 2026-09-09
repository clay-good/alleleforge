"""The index/reference agreement check failed open on exactly the risky index.

`search(..., genome_index=...)` anchors PAMs over the index's sequence and reads bases and
coordinates from the reference, so an index of a *different* genome yields hits that are
silently in the wrong place. The engine guarded that seam by comparing build names, under
an `if` that required both names to be present — and an index whose genome nobody wrote
down is the one most likely to be the wrong genome.

A contig length is recorded per index and costs nothing to compare, and it does not depend
on a name: chr1 is 248,956,422 bases in hg38, 249,250,621 in hg19 and 248,387,328 in
T2T-CHM13. `GenomeIndex.disagreement_with(reference)` is the library form — a Python
caller holding an index and a FASTA can ask the same question the engine asks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.index import GenomeIndex
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

SPACER = "GACCATGCAACCTTGAACGT"
PAD = "T" * 12
NGG = PAM(pattern="NGG")


def _reference(
    tmp_path: Path, contigs: dict[str, str], name: str, build: str | None
) -> ReferenceGenome:
    fasta = tmp_path / name
    fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
    return ReferenceGenome(fasta, build=build)


def test_an_unlabelled_index_over_another_genome_is_refused(tmp_path: Path) -> None:
    """Neither side names an assembly, and they are still different genomes."""
    indexed = _reference(tmp_path, {"chrA": PAD + SPACER + "TGG" + PAD}, "a.fa", None)
    other = _reference(tmp_path, {"chrA": PAD + PAD + SPACER + "TGG" + PAD}, "b.fa", None)
    gi = GenomeIndex.build_genome(indexed, cache_dir=tmp_path / "idx")
    with pytest.raises(ValueError, match="different genomes"):
        search(SPACER, NGG, reference=other, genome_index=gi)
    gi.close()


def test_a_contig_the_reference_does_not_have_is_refused(tmp_path: Path) -> None:
    indexed = _reference(tmp_path, {"chrZ": PAD + SPACER + "TGG" + PAD}, "z.fa", None)
    other = _reference(tmp_path, {"chrA": PAD + SPACER + "TGG" + PAD}, "a2.fa", None)
    gi = GenomeIndex.build_genome(indexed, cache_dir=tmp_path / "idx2")
    assert "chrZ" in str(gi.disagreement_with(other))
    gi.close()


def test_an_index_over_a_subset_of_contigs_still_agrees(tmp_path: Path) -> None:
    """An index may cover part of a genome; that is not a disagreement."""
    ref = _reference(
        tmp_path, {"chrA": PAD + SPACER + "TGG" + PAD, "chrB": "ACGT" * 8}, "sub.fa", None
    )
    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx3", contigs=["chrA"])
    assert gi.disagreement_with(ref) is None
    hits = search(SPACER, NGG, reference=ref, genome_index=gi)
    assert hits is not None
    gi.close()


def test_the_matching_case_says_nothing(tmp_path: Path) -> None:
    ref = _reference(tmp_path, {"chrA": PAD + SPACER + "TGG" + PAD}, "ok.fa", "hg38")
    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx4")
    assert gi.disagreement_with(ref) is None
    gi.close()
