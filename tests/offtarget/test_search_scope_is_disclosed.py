"""Two searches with different specificity must not carry identical provenance.

`search_description()` exists so that "a reader comparing two reports" can do so: the
site count, the worst score and the specificity are all conditional on the settings it
names. It named the mismatch and bulge budgets and the two reporting cut-offs -- and not
the *extent* searched, which is the setting that moves the numbers most.

Scoping to a gene panel is the ordinary way a run is made practical; the `--region` help
says so outright. Over a two-contig reference holding the same locus twice:

    chr2 only  -> 1 site, specificity 0.468, searched 140 bases
    whole ref  -> 2 sites, specificity 0.305, searched 280 bases

`searched_bases` was recorded on the model and mentioned only when the *resolved*
fraction fell below 99%. Both of these resolved fully, so both printed the same string.
A reader saw two different specificities under identical provenance, with the smaller
search -- the one that finds fewer off-targets -- reading as the safer guide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.sequence import GenomicInterval, Strand


@pytest.fixture
def duplicated_locus(tmp_path: Path) -> tuple[ReferenceGenome, str]:
    """A reference carrying the same 140-base locus on two contigs, plus its spacer."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # a PAM, so the locus yields a guide
    seq[55:58] = list("CCA")
    locus = "".join(seq)
    fasta = tmp_path / "two_contigs.fa"
    fasta.write_text(f">chr2\n{locus}\n>chr9\n{locus}\n")
    return ReferenceGenome(fasta, build="hg38"), locus[43:63]


def _reports(ref: ReferenceGenome, spacer: str) -> tuple[OffTargetReport, OffTargetReport]:
    scoped = search(
        spacer,
        PAM(pattern="NGG"),
        reference=ref,
        regions=[GenomicInterval(chrom="chr2", start=0, end=140, strand=Strand.PLUS)],
    )
    whole = search(spacer, PAM(pattern="NGG"), reference=ref)
    return scoped, whole


def test_the_premise_a_scoped_search_really_does_look_safer(
    duplicated_locus: tuple[ReferenceGenome, str],
) -> None:
    """Without this, the provenance check below would prove nothing."""
    scoped, whole = _reports(*duplicated_locus)
    assert scoped.n_sites < whole.n_sites
    assert scoped.specificity_score() > whole.specificity_score()
    assert scoped.searched_bases < whole.searched_bases
    # ...and neither is degraded, which is why the old coverage clause stayed silent.
    assert scoped.resolved_bases == scoped.searched_bases
    assert whole.resolved_bases == whole.searched_bases


def test_two_scopes_do_not_share_one_provenance_string(
    duplicated_locus: tuple[ReferenceGenome, str],
) -> None:
    scoped, whole = _reports(*duplicated_locus)
    assert scoped.search_description() != whole.search_description(), (
        "a panel scan and a genome-wide scan describe themselves identically while "
        "reporting different specificities"
    )


def test_the_description_states_the_extent_searched(
    duplicated_locus: tuple[ReferenceGenome, str],
) -> None:
    scoped, whole = _reports(*duplicated_locus)
    assert "140 bases" in scoped.search_description()
    assert "280 bases" in whole.search_description()


def test_the_extent_is_stated_even_when_coverage_is_perfect(
    duplicated_locus: tuple[ReferenceGenome, str],
) -> None:
    """The bug was a conditional, so the unconditional case is the one to pin."""
    scoped, _ = _reports(*duplicated_locus)
    description = scoped.search_description()
    assert scoped.resolved_bases == scoped.searched_bases  # no degradation to report
    assert "were searchable" not in description  # ...so the old clause is silent
    assert "bases" in description  # ...and the extent is stated anyway


def test_the_description_stays_ascii(duplicated_locus: tuple[ReferenceGenome, str]) -> None:
    """It reaches the PDF, whose WinAnsi font has no glyph for a non-ASCII character."""
    scoped, whole = _reports(*duplicated_locus)
    for report in (scoped, whole):
        report.search_description().encode("ascii")  # raises if a non-ASCII char crept in


def test_an_unrecorded_extent_is_named_not_reported_as_zero(
    duplicated_locus: tuple[ReferenceGenome, str],
) -> None:
    """`searched_bases` has a default, so 0 can mean "not recorded", not "none".

    A report deserialized from before the field existed arrives at 0 with its sites
    attached. "over 0 bases" beside a table of nominated sites is not a scope, it is a
    contradiction -- and it would invite exactly the comparison this change exists to
    make possible, between one real extent and one that was never measured.
    """
    _, whole = _reports(*duplicated_locus)
    assert whole.sites, "the fixture must have sites, or this proves nothing"
    stale = whole.model_copy(update={"searched_bases": 0, "resolved_bases": 0})
    description = stale.search_description()
    assert "over 0 bases" not in description
    assert "unrecorded extent" in description


def test_an_empty_search_still_says_it_examined_nothing() -> None:
    """The pre-existing empty-search warning must not be displaced by the extent."""
    empty = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(),
        mismatch_threshold=4,
        dna_bulge_budget=1,
        rna_bulge_budget=1,
        cfd_threshold=0.2,
        mit_threshold=0.1,
        searched_bases=0,
        resolved_bases=0,
        reference_build="hg38",
    )
    description = empty.search_description()
    assert "NO SEQUENCE WAS SEARCHED" in description
    assert "over 0 bases" not in description
