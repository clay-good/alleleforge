"""A reported locus must name its contig the way the searched reference does.

The same off-target site, the same guide, the same genome, reported two ways:

    aforge offtarget ... --reference-fasta decoy.fa
      chr2:43-63(+)   ...

    aforge offtarget ... --reference-fasta decoy.fa --region 2:0-183
      2:43-63(+)      ...

Without a scope the contigs come from the reference and carry its spelling; with one
they carry whatever the caller typed. So the **identity of a site depended on an
unrelated scoping flag**, and two runs over one genome produced site lists that do not
join, diff or deduplicate against each other.

Nothing was mis-searched — `canonical_contig` reconciles the styles, which is why both
runs find both sites. What was wrong is the name written down afterwards. Every
coordinate in a report describes a position *in the reference*, and the only name
guaranteed to address that position in that reference is the reference's own; the
caller's spelling is an input convenience.

Rewriting toward the reference has no cost to an Ensembl-space user, which is the
reason to prefer it over the other direction: a bare-named FASTA produces bare-named
output, because the output follows the genome the caller themselves supplied.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import resolve

SPACER = "TATATATATATACCAATATA"


def _fasta(tmp_path: Path, name: str, contig: str) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / name
    path.write_text(f">{contig}\n" + "".join(seq) + SPACER + "TGG" + "T" * 20 + "\n")
    return path


def _loci(reference: ReferenceGenome, regions: list[GenomicInterval] | None) -> list[str]:
    report = search(SPACER, PAM(pattern="NGG"), reference=reference, regions=regions)
    return sorted(f"{s.locus.chrom}:{s.locus.start}-{s.locus.end}" for s in report.sites)


def _region(chrom: str) -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=0, end=183, strand=Strand.PLUS)


def test_a_scope_does_not_rename_the_sites_it_scopes(tmp_path: Path) -> None:
    """The finding: scoping a search must not change what its results are called."""
    reference = ReferenceGenome(_fasta(tmp_path, "ucsc.fa", "chr2"))
    unscoped = _loci(reference, None)
    assert unscoped, "fixture found nothing — this check would be vacuous"
    assert _loci(reference, [_region("2")]) == unscoped
    assert _loci(reference, [_region("chr2")]) == unscoped


def test_the_reference_decides_the_spelling(tmp_path: Path) -> None:
    """A UCSC-named genome yields `chr2` however the caller spelled the scope."""
    reference = ReferenceGenome(_fasta(tmp_path, "ucsc.fa", "chr2"))
    for scope in (None, [_region("2")], [_region("chr2")]):
        assert all(locus.startswith("chr2:") for locus in _loci(reference, scope))


def test_an_ensembl_named_genome_keeps_its_own_spelling(tmp_path: Path) -> None:
    """The rewrite is toward the supplied genome, never toward `chr` for its own sake."""
    reference = ReferenceGenome(_fasta(tmp_path, "ensembl.fa", "2"))
    for scope in (None, [_region("2")], [_region("chr2")]):
        loci = _loci(reference, scope)
        assert loci, scope
        assert all(locus.startswith("2:") for locus in loci), (scope, loci)


def test_an_unknown_contig_is_still_refused(tmp_path: Path) -> None:
    """Reconciling a spelling must not become accepting a contig that is absent."""
    reference = ReferenceGenome(_fasta(tmp_path, "ucsc.fa", "chr2"))
    with pytest.raises(ValueError, match="chr9"):
        _loci(reference, [_region("chr9")])


def test_a_report_does_not_mix_two_spellings_of_one_contig(tmp_path: Path) -> None:
    """The variant names the candidate; the reference names the off-target sites.

    Fixing only the scope would have made this worse: a `2:71:A>C` input against a
    `chr2` genome produced a candidate at `2:43-63` beside off-target sites at
    `chr2:…`, in one document, describing one contig.
    """
    reference = ReferenceGenome(_fasta(tmp_path, "ucsc.fa", "chr2"))
    menu = design(
        "2:71:A>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        max_candidates_per_chemistry=1,
    )
    assert menu.candidates, "fixture produced no candidate"
    # A prime candidate carries a `pegrna`, a nuclease/base one a `guide`; take the
    # contig from whichever placed this candidate, plus every site screened for it.
    spellings: set[str] = set()
    for candidate in menu.candidates:
        placed = candidate.guide or candidate.pegrna
        assert placed is not None
        spellings.add(placed.placement.chrom)
        if candidate.offtarget is not None:
            spellings |= {site.locus.chrom for site in candidate.offtarget.sites}
    assert spellings == {"chr2"}, spellings


def test_resolving_without_a_reference_renames_nothing(tmp_path: Path) -> None:
    """There is no genome to be named after, so the caller's spelling stands."""
    assert resolve("2:71:A>C").variant.chrom == "2"


def test_resolving_against_a_reference_adopts_its_spelling(tmp_path: Path) -> None:
    ucsc = ReferenceGenome(_fasta(tmp_path, "ucsc.fa", "chr2"))
    ensembl = ReferenceGenome(_fasta(tmp_path, "ensembl.fa", "2"))
    assert resolve("2:71:A>C", reference=ucsc).variant.chrom == "chr2"
    assert resolve("chr2:71:A>C", reference=ucsc).variant.chrom == "chr2"
    assert resolve("chr2:71:A>C", reference=ensembl).variant.chrom == "2"
    assert resolve("2:71:A>C", reference=ensembl).variant.chrom == "2"
