"""Every printed span is `start-end`, and nothing checked which end came first.

An ordered-opposite sweep swapped `start` for `end` (and subscript `0` for `1`) at each
place a span is rendered, and the suite stayed green in four of them: the locus line's
`chrom:start-end`, and the base-editor reagent line's `window N-M`.

The failure is quiet in the way this project keeps finding: `chr2:117-97` is a locus a
reader copies into a browser, and an inverted window is a range a bench scientist reads
as the bases the editor acts on. Both still *look* like coordinates. The report's existing
checks ask whether the contig is present and whether a cut position is printed — questions
an inverted span answers correctly.

A sibling round already fixed exactly this shape in two printed intervals in
`design/ranking` and `report/pdf`, where an upper bound was quoted as a lower one. These
two are the same defect in the same report, found by asking the question in a form a sweep
can check rather than by reading.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import _locus_summary, _reagent_summary
from alleleforge.types.edit import Chemistry, EditIntent


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _candidates(reference: ReferenceGenome, variant: str, intent: EditIntent) -> list[object]:
    return list(design(variant, reference=reference, intent=intent, run_offtarget=False).candidates)


def _span(text: str, prefix: str) -> tuple[int, int]:
    """Pull the `A-B` span out of a rendered line, after ``prefix``."""
    import re

    match = re.search(r"(\d+)-(\d+)", text.split(prefix, 1)[1])
    assert match is not None, text
    return int(match.group(1)), int(match.group(2))


def test_the_locus_line_prints_its_span_in_order(reference: ReferenceGenome) -> None:
    candidates = _candidates(reference, "chr2:1050:G>A", EditIntent.KNOCK_OUT)
    assert candidates, "no candidate to render"
    seen = 0
    for candidate in candidates:
        line = _locus_summary(candidate)  # type: ignore[arg-type]
        if line is None:
            continue
        seen += 1
        start, end = _span(line, "chr2:")
        assert start < end, line
    assert seen, "no candidate carried a placement; this check would be vacuous"


def test_the_locus_span_is_the_placement_it_was_given(reference: ReferenceGenome) -> None:
    """Order alone would pass on a line that prints the same number twice."""
    from alleleforge.report.builder import _placement

    for candidate in _candidates(reference, "chr2:1050:G>A", EditIntent.KNOCK_OUT):
        placement = _placement(candidate)  # type: ignore[arg-type]
        line = _locus_summary(candidate)  # type: ignore[arg-type]
        if placement is None or line is None:
            continue
        assert _span(line, "chr2:") == (placement.start, placement.end), line


def test_a_base_editor_window_prints_in_order(reference: ReferenceGenome) -> None:
    candidates = [
        c
        for c in _candidates(reference, "chr2:1050:G>A", EditIntent.CORRECT)
        if c.chemistry in (Chemistry.BASE_ABE, Chemistry.BASE_CBE)  # type: ignore[attr-defined]
    ]
    if not candidates:
        pytest.skip("this fixture produced no base-editor candidate")
    for candidate in candidates:
        line = _reagent_summary(candidate)  # type: ignore[arg-type]
        assert "window " in line, line
        low, high = _span(line, "window ")
        assert low <= high, line
        window = candidate.base_edit_window  # type: ignore[attr-defined]
        assert (low, high) == (window.window[0], window.window[1]), line
