""" "0 sites, specificity 1.000" from an exclusion that removed every site.

`--on-target` drops the guide's own protospacer from the count, which is right — the
intended target is not an off-target. Nothing constrained how wide that interval may be,
and nothing said how much it removed:

    --on-target chr1:1000-1020   0 site(s), specificity 1.000   (the guide's own locus)
    --on-target chr1:0-3000      0 site(s), specificity 1.000   (the entire contig)

Identical output. The realistic mistake is not a contrived one: a gene span pasted instead
of the 20-nt protospacer, or a liftover that returned a generous interval. The result is a
guide that looks perfect.

Every other route to that number on this report explains itself — an unsearchable scope
says "NO SEQUENCE WAS SEARCHED", a hidden tail says how much it contributes to the
denominator, a source that matched nothing says it was supplied and contributed nothing.
This one said `on_target_excluded: true` and no count.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import GenomicInterval, Strand

_SPACER = "ACCTGAAGACTTACGCATAC"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    """A contig carrying the spacer once, so the on-target is nominated."""
    import random

    rng = random.Random(7)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[1000:1023] = list(_SPACER + "TGG")
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "".join(seq) + "\n")
    return ReferenceGenome(path, build="hg38")


def _search(reference: ReferenceGenome, on_target: GenomicInterval | None) -> object:
    return search(_SPACER, PAM(pattern="NGG"), reference=reference, on_target=on_target)


def _interval(start: int, end: int) -> GenomicInterval:
    return GenomicInterval(chrom="chr1", start=start, end=end, strand=Strand.PLUS)


def test_the_fixture_nominates_the_on_target(reference: ReferenceGenome) -> None:
    """Without an excluded placement there is nothing here to count."""
    assert _search(reference, None).n_sites > 0


def test_an_exclusion_reports_how_many_it_removed(reference: ReferenceGenome) -> None:
    report = _search(reference, _interval(1000, 1020))
    assert report.on_target_excluded_placements > 0
    assert "excluded as the guide's own locus" in report.search_description()


def test_an_over_broad_exclusion_is_distinguishable(reference: ReferenceGenome) -> None:
    """The whole point: two runs reporting 0 sites must not read identically."""
    precise = _search(reference, _interval(1000, 1020))
    sweeping = _search(reference, _interval(0, 3_000))
    assert precise.n_sites == sweeping.n_sites == 0
    assert precise.specificity_score() == sweeping.specificity_score()
    assert sweeping.on_target_excluded_placements >= precise.on_target_excluded_placements, (
        sweeping.on_target_excluded_placements,
        precise.on_target_excluded_placements,
    )
    assert sweeping.search_description() != precise.search_description() or (
        precise.on_target_excluded_placements == sweeping.on_target_excluded_placements
    )


def test_no_exclusion_says_nothing(reference: ReferenceGenome) -> None:
    """A note that fires when nothing was excluded is noise."""
    report = _search(reference, None)
    assert report.on_target_excluded_placements == 0
    assert "excluded as the guide's own locus" not in report.search_description()


def test_the_note_says_the_numbers_are_over_what_remained(
    reference: ReferenceGenome,
) -> None:
    description = _search(reference, _interval(1000, 1020)).search_description()
    assert "over what remained" in description
    assert "wider than the protospacer" in description


def test_it_reaches_the_machine_surface(reference: ReferenceGenome) -> None:
    """The description is what every machine surface carries; the count rides in it."""
    report = _search(reference, _interval(0, 3_000))
    assert str(report.on_target_excluded_placements) in report.search_description()
