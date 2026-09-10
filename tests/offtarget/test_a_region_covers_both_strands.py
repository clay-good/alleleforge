"""A restriction covers both strands, which the request model asserts and nothing measured.

`Region` carries no strand, and its docstring says why: "a restriction covers both strands
by construction, so requiring one would be [misleading]". That is a claim about what the
scan does with the interval, made in the type that omits the field — and *by construction*
is a statement of confidence, not evidence.

It matters more than most such claims. If the filter compared a hit's strand as well as its
span, a minus-strand off-target inside the region a user scoped to would be dropped: a
missing danger, in the one feature whose purpose is to make a whole-genome scan practical,
and invisible because the result would look like a clean region.

Two off-target sites are planted — one on each strand — and each region is required to keep
the site inside it whichever strand that site is on. Both strands, because two neighbouring
geometries in this repository were one base wrong for exactly the want of that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

_GUIDE = "ACCTGACTCCTGAGGAGAAG"
_PLUS_AT, _MINUS_AT = 100, 200


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    body = ["T"] * 400
    body[_PLUS_AT : _PLUS_AT + 20] = list(_GUIDE)
    body[_PLUS_AT + 20 : _PLUS_AT + 23] = list("TGG")
    body[_MINUS_AT : _MINUS_AT + 20] = list(str(DNASequence(_GUIDE).reverse_complement()))
    body[_MINUS_AT - 3 : _MINUS_AT] = list("CCA")
    fasta = tmp_path / "both.fa"
    fasta.write_text(">chr1\n" + "".join(body) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _sites(reference: ReferenceGenome, region: GenomicInterval | None) -> set[tuple[int, str]]:
    report = search(
        _GUIDE,
        PAM(pattern="NGG"),
        reference=reference,
        regions=None if region is None else [region],
    )
    return {(s.locus.start, s.locus.strand.value) for s in report.sites}


def test_the_fixture_plants_one_site_on_each_strand(reference: ReferenceGenome) -> None:
    """Without both, the checks below cannot tell a strand filter from a span filter."""
    assert _sites(reference, None) == {(_PLUS_AT, "+"), (_MINUS_AT, "-")}


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (90, 130, {(_PLUS_AT, "+")}),
        (190, 230, {(_MINUS_AT, "-")}),
        (90, 230, {(_PLUS_AT, "+"), (_MINUS_AT, "-")}),
    ],
)
def test_a_region_keeps_the_site_inside_it_whichever_strand(
    start: int, end: int, expected: set[tuple[int, str]], reference: ReferenceGenome
) -> None:
    region = GenomicInterval(chrom="chr1", start=start, end=end, strand=Strand.PLUS)
    assert _sites(reference, region) == expected


def test_a_plus_stranded_region_does_not_hide_a_minus_stranded_site(
    reference: ReferenceGenome,
) -> None:
    """The failure the type's own docstring rules out, stated as the thing to fear.

    A restriction is written `chr1:190-230(+)` because an interval needs *a* strand to be
    spelled; reading that `+` as part of the filter would drop the minus-strand off-target
    inside it — a missing danger that reads as a clean region.
    """
    region = GenomicInterval(chrom="chr1", start=190, end=230, strand=Strand.PLUS)
    assert (_MINUS_AT, "-") in _sites(reference, region)
