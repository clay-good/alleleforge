"""Two notes about the candidates are only true when there are candidates.

`design` writes a note when a chromatin track was supplied and adjusted nothing, and
another when a cell context was supplied and only prime could consider it. Both are
guarded the same way — *the input is set* **and** *there are candidates* — and every
fixture in the suite supplies the input to a run that produces a menu, so the second arm
never decided anything.

The two guards are not equally load-bearing, which is the point of pinning them:

* the chromatin note counts the adjusted candidates and speaks when the count is zero,
  and zero is exactly what an empty menu gives. Without `and candidates` an empty menu
  is told that the track "covers none of the candidate loci — every efficiency here is
  the unadjusted estimate", about efficiencies that do not exist. A reader who gets no
  candidates and a sentence blaming their track has been pointed away from the real
  reason, which is in the routing rationale directly above it.
* the cell-context note is suppressed by its own inner `if unconsidered:` for an empty
  menu, so dropping its `and candidates` changes nothing. Recorded here as behaviour
  rather than left as a coincidence: the note is about chemistries that ran.

The empty menu is the no-op variant — an edit that does not change the sequence, which
every chemistry declines.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.data.annotations import EncodeTracks, _Segment
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _covering_track() -> EncodeTracks:
    return EncodeTracks({("atac", "chr2"): [_Segment(start=0, end=3_000, value=2.0)]})


def test_the_fixture_produces_an_empty_menu(reference: ReferenceGenome) -> None:
    """The premise. A no-op edit is declined by every chemistry."""
    menu = design("chr2:1200:A>A", reference=reference, run_offtarget=False)
    assert not menu.candidates


def test_an_empty_menu_is_not_told_its_chromatin_track_adjusted_nothing(
    reference: ReferenceGenome,
) -> None:
    menu = design(
        "chr2:1200:A>A",
        reference=reference,
        encode_tracks=_covering_track(),
        chromatin_track="atac",
        run_offtarget=False,
    )
    assert not menu.candidates
    assert "covers none of the candidate loci" not in (menu.rationale or "")


def test_an_empty_menu_is_not_told_a_cell_context_went_unconsidered(
    reference: ReferenceGenome,
) -> None:
    menu = design(
        "chr2:1200:A>A",
        reference=reference,
        cell_context="K562",
        run_offtarget=False,
    )
    assert not menu.candidates
    assert "was supplied but is only consumed by prime" not in (menu.rationale or "")


def test_a_real_menu_still_gets_the_chromatin_note_when_nothing_was_adjusted(
    reference: ReferenceGenome,
) -> None:
    """The negative case, so the two checks above are not passing by silence."""
    uncovered = EncodeTracks({("atac", "chr2"): [_Segment(start=0, end=10, value=2.0)]})
    menu = design(
        "chr2:1200:A>T",
        reference=reference,
        encode_tracks=uncovered,
        chromatin_track="atac",
        run_offtarget=False,
    )
    assert menu.candidates, "the fixture must produce a menu"
    assert "covers none of the candidate loci" in (menu.rationale or "")
