"""A design re-scanned the same genome for the same spacer, in two of three verticals.

A scan is a pass over the whole reference: on a real genome it is the dominant cost of a
run, and everything else this library does is rounding beside it. Two verticals were
paying for it twice.

**Prime** memoizes its *merged* off-target report under the pair it belongs to — `(peg
spacer, nicking spacer, both placements)` — which is the right key for that value and the
wrong one for the two scans it is built from. So a peg spacer paired with two different
nicking guides was scanned twice, and a nicking guide shared by several pegRNAs was scanned
once per pegRNA: 1 of 6, 4 of 10 and 1 of 4 scans on three measured loci.

**Base editing** scans per *window*, and two deaminases over one protospacer are two
windows with one spacer: 1 of 2 scans at a measured locus.

`RunScanner` binds the ten run-wide arguments every scan shares and memoizes on the two
that vary — the spacer, and the locus excluded from its own report. That key is exactly
what a report depends on: keying on the spacer alone would hand a candidate at one locus a
report that excluded a *different* locus, dropping a genuine paralogous off-target for it.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget import engine
from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand


@pytest.fixture
def contig(tmp_path: Path) -> tuple[ReferenceGenome, str]:
    """A random 4 kb contig, and its sequence, so a variant can be built from real bases."""
    rng = random.Random(4)
    sequence = "".join(rng.choice("ACGT") for _ in range(4000))
    fasta = tmp_path / "scan.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    return ReferenceGenome(fasta, build="hg38"), sequence


def _scans(reference: ReferenceGenome, variant: str) -> list[tuple[str, str]]:
    """Return every whole-genome scan a design ran, as (spacer, excluded locus)."""
    seen: list[tuple[str, str]] = []
    original = engine.search

    def spy(spacer: Any, pam: Any, **kwargs: Any) -> Any:
        seen.append((str(spacer.sequence), str(kwargs.get("on_target"))))
        return original(spacer, pam, **kwargs)

    engine.search = spy  # type: ignore[assignment]
    try:
        design(variant, reference=reference, run_offtarget=True)
    finally:
        engine.search = original  # type: ignore[assignment]
    return seen


def test_no_spacer_is_scanned_twice_for_the_same_excluded_locus(
    contig: tuple[ReferenceGenome, str],
) -> None:
    """Across every vertical a design runs, not one of them in isolation."""
    reference, sequence = contig
    scanned = 0
    for position in range(2000, 2060):
        ref_base = sequence[position]
        alt = {"A": "G", "G": "A", "C": "T", "T": "C"}[ref_base]
        scans = _scans(reference, f"chr1:{position + 1}:{ref_base}>{alt}")
        if not scans:
            continue
        scanned += 1
        duplicates = len(scans) - len(set(scans))
        assert duplicates == 0, (
            f"{duplicates} of {len(scans)} whole-genome scans at position {position + 1} "
            "repeated one already done in the same design"
        )
    assert scanned >= 10, f"only {scanned} loci produced a scan; this check would be weak"


def test_the_memo_distinguishes_two_loci_with_one_spacer(
    contig: tuple[ReferenceGenome, str],
) -> None:
    """The obligation the key inherits: a report carries its own locus's exclusion.

    Two candidates at different loci can share a spacer, and they must not share a report
    — the one excluded from it is not the same locus. Asserted on the scanner directly,
    because arranging that collision through a real enumerator is what the pair-key
    docstring says nobody managed to do.
    """
    reference, _ = contig
    scanner = engine.RunScanner(reference=reference)
    from alleleforge.types.guide import PAM, Spacer
    from alleleforge.types.sequence import DNASequence

    spacer = Spacer(sequence=DNASequence(str(reference.fetch(_interval(100, 120)))))
    first = scanner.scan(spacer, PAM(pattern="NGG"), _interval(100, 123))
    second = scanner.scan(spacer, PAM(pattern="NGG"), _interval(900, 923))
    assert len(scanner) == 2, "one spacer at two loci is two reports, not one"
    assert first is not second

    again = scanner.scan(spacer, PAM(pattern="NGG"), _interval(100, 123))
    assert again is first, "the same spacer at the same locus must not rescan"
    assert len(scanner) == 2


def _interval(start: int, end: int) -> GenomicInterval:
    return GenomicInterval(
        chrom="chr1",
        start=start,
        end=end,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )
