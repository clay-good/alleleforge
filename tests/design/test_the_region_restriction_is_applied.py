"""A scoped design run must actually scope its off-target search.

`design()` takes `offtarget_regions`, documents it, records it in the provenance
snapshot, and exposes it as `--region` / `--regions-bed` on both `aforge design` and
`aforge batch`. All three verticals accept the parameter. Two of the three call sites
did not pass it: the base editor did, SpCas9 nuclease and prime editing did not.

So for the two most-used chemistries the restriction was inert, and the artifact said
otherwise -- the snapshot recorded the intended scope while the engine scanned every
contig:

    offtarget_regions=[chr2:0-50]  ->  provenance: 50 bases, searched: 140

Both directions of that are bad. A scan wider than asked for is slower than asked for,
on the axis where the `--region` help says scoping "is usually what makes a run
practical" -- so on a real hg38 a panel-scoped design run was a whole-genome one. And
the provenance asserted a restriction that was never applied, which is the claim a
re-run would be checked against.

The bug was invisible to everything: the parameter existed end to end, every signature
accepted it, the suite was green, and a nonsense contig -- which `search()` refuses by
name -- was accepted without complaint, because it never reached `search()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand


def _interval(chrom: str, start: int, end: int) -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=start, end=end, strand=Strand.PLUS)


def _prime_contig() -> str:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    return "".join(seq)


#: One scenario per vertical that had to be wired, because the defect was per-vertical
#: and a menu-wide assertion passes as soon as *one* chemistry obeys. The first version
#: of this file covered prime only, and deleting the nuclease wiring left all of it
#: green -- the bug reproduced inside its own regression test.
SCENARIOS: dict[str, tuple[str, str, EditIntent, Chemistry]] = {
    "prime": (_prime_contig(), "chr2:71:A>C", EditIntent.CORRECT, Chemistry.PRIME),
    "cas9_nuclease": (
        "T" * 20 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 20,
        "chr2:26:A>G",
        EditIntent.KNOCK_OUT,
        Chemistry.CAS9_NUCLEASE,
    ),
    "base_editor": (
        "T" * 20 + "TTTAAACGTTTTTTTTTTTT" + "TGG" + "T" * 20,
        "chr2:26:A>G",
        EditIntent.INSTALL,
        Chemistry.BASE_ABE,
    ),
}


@pytest.fixture(params=sorted(SCENARIOS), ids=sorted(SCENARIOS))
def scenario(
    request: pytest.FixtureRequest, tmp_path: Path
) -> tuple[ReferenceGenome, str, EditIntent, Chemistry, int]:
    """A reference, an input and the chemistry it must produce, per vertical."""
    contig, variant, intent, chemistry = SCENARIOS[request.param]
    fasta = tmp_path / f"{request.param}.fa"
    fasta.write_text(">chr2\n" + contig + "\n")
    return ReferenceGenome(fasta, build="hg38"), variant, intent, chemistry, len(contig)


@pytest.fixture
def reference(scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int]) -> ReferenceGenome:
    return scenario[0]


def _menu(
    scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int],
    regions: list[GenomicInterval] | None,
) -> RankedMenu:
    reference, variant, intent, _, _ = scenario
    return design(variant, reference=reference, intent=intent, offtarget_regions=regions)


def test_the_fixture_produces_the_vertical_it_claims(
    scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int],
) -> None:
    """Guard the guard, and the reason this file is parametrized.

    A scenario that produces no candidate for its chemistry silently stops testing that
    vertical, which is how the nuclease path stayed uncovered.
    """
    expected = scenario[3]
    produced = {c.chemistry for c in _menu(scenario, None).candidates}
    assert expected in produced, f"{expected.value} produced nothing; got {produced}"


def test_an_unrestricted_run_searches_the_whole_contig(
    scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int],
) -> None:
    """The premise: without a region the scan really does cover everything."""
    contig_bases = scenario[4]
    for candidate in _menu(scenario, None).candidates:
        assert candidate.offtarget is not None
        assert candidate.offtarget.searched_bases == contig_bases


def test_a_restricted_run_searches_only_the_region(
    scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int],
) -> None:
    menu = _menu(scenario, [_interval("chr2", 0, 50)])
    assert menu.candidates, "no candidates -- this check would be vacuous"
    for candidate in menu.candidates:
        assert candidate.offtarget is not None
        assert candidate.offtarget.searched_bases == 50, (
            f"{candidate.chemistry.value} scanned "
            f"{candidate.offtarget.searched_bases} bases for a 50-base region"
        )


def test_the_provenance_and_the_search_agree(
    scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int],
) -> None:
    """The snapshot is what a re-run is checked against; it must describe what happened."""
    menu = _menu(scenario, [_interval("chr2", 0, 50)])
    snapshot = menu.provenance.config_snapshot["offtarget_regions"]
    assert snapshot is not None
    for candidate in menu.candidates:
        assert candidate.offtarget is not None
        assert candidate.offtarget.searched_bases == snapshot["bases"]


def test_a_region_the_reference_cannot_serve_reaches_the_reader(
    scenario: tuple[ReferenceGenome, str, EditIntent, Chemistry, int],
) -> None:
    """`search()` refuses an unknown contig by name; that refusal must be reachable.

    While the region was dropped, a design run scoped to a contig the reference does not
    have succeeded silently, returning a full menu -- the clearest available proof that
    the region never reached the engine. The refusal now arrives as an explained decline
    rather than an exception, which is this project's contract for a chemistry that
    cannot be designed; what matters is that it arrives at all, naming the contig.
    """
    menu = _menu(scenario, [_interval("chrNope", 0, 10)])
    assert menu.candidates == ()
    assert "chrNope" in menu.rationale
    assert "which this reference does not have" in menu.rationale
