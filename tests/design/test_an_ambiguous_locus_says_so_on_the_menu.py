"""A design inside a segmental duplication has to say that it is.

The resolver already checked: `flag_ambiguous_regions` matches the working interval
against a table of hg38-difficult loci (segdups, centromeres, acrocentric arms), builds
`ambiguous-region:<kind>` and `recommend-reference:<build>` flags, and recommends T2T.
`ReferenceRecommendation.apply_to` — "the wiring point into the Phase 1 result types",
per its own docstring — had no caller anywhere in the package. Only tests called it.

So designing at a locus flagged as a segmental duplication produced 70 candidates, an
HTML page, a PDF and a JSON export, none of which mentioned it. That is the condition
under which a read cannot be placed uniquely, which is exactly when the off-target
search under-reports — the number the whole safety axis rests on. Meanwhile
`recommend-reference` sat in `CAVEAT_FLAGS` with a written sentence, waiting for a flag
that never arrived, and read as coverage.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.coordinates import AmbiguousRegion, RegionFlagKind
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report, caveats
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


@pytest.fixture
def segdup_reference(tmp_path: Path) -> ReferenceGenome:
    import random

    rng = random.Random(7)
    fasta = tmp_path / "segdup.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(2_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _menu(reference: ReferenceGenome) -> object:
    region = AmbiguousRegion(
        interval=GenomicInterval(chrom="chr1", start=0, end=2_000, strand=Strand.PLUS),
        kind=RegionFlagKind.SEGDUP,
        note="test segdup",
    )
    ref_base = reference.fetch(
        GenomicInterval(chrom="chr1", start=419, end=420, strand=Strand.PLUS)
    )
    alt = "A" if ref_base != "A" else "G"
    resolved = resolve(
        f"chr1:420:{ref_base}>{alt}", reference=reference, ambiguous_regions=(region,)
    )
    assert resolved.reference_recommendation is not None, "the fixture must be flagged"
    return design(resolved, reference=reference, run_offtarget=False)


def test_every_candidate_carries_the_ambiguity(segdup_reference: ReferenceGenome) -> None:
    menu = _menu(segdup_reference)
    assert menu.candidates, "no candidate to check"
    for candidate in menu.candidates:
        assert "ambiguous-region:segdup" in candidate.flags
        assert "recommend-reference:T2T-CHM13v2" in candidate.flags


def test_the_flag_is_explained_not_just_printed(segdup_reference: ReferenceGenome) -> None:
    """A raw token in a comma-separated line is not a disclosure."""
    candidate = _menu(segdup_reference).candidates[0]
    reasons = dict(caveats(candidate.flags))
    why = reasons["ambiguous-region:segdup"]
    assert "uniquely" in why and "off-target search under-reports" in why


def test_the_report_carries_it_to_the_reader(segdup_reference: ReferenceGenome) -> None:
    body = build_report(_menu(segdup_reference)).model_dump_json()
    assert "segdup" in body
    assert "T2T-CHM13v2" in body
