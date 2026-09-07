"""A ranked list of two chemistries compares two models' outputs, and said nothing.

A real menu orders `prime 0.366` above or below `base_abe 0.400`. Those numbers come from
different models — `pridict2-baseline` and `be-dict-baseline`, both named in the run's
provenance, neither calibrated against the other. The projection onto four shared
objectives is what makes the ordering *possible*; it does not make the efficiency axis one
measurement.

The project already draws this distinction where it is easy: the leaderboard refuses to
rank across metrics and prints a note saying the groups are incomparable. The design menu
*does* rank across chemistries, because a user needs one list, and had no equivalent
sentence — the surface where the reader is most likely to read a rank as a measured
comparison was the one that did not qualify it.

Only when the menu spans more than one chemistry: a note that always appears is not a note.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome

_NOTE = "triage, not a measured comparison"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_a_mixed_menu_qualifies_the_ordering(reference: ReferenceGenome) -> None:
    menu = design("chr2:1050:G>A", reference=reference, run_offtarget=False)
    chemistries = {c.chemistry for c in menu.candidates}
    assert len(chemistries) > 1, "the fixture must produce a mixed menu"
    assert _NOTE in menu.rationale
    assert "different model for each chemistry" in menu.rationale


def test_a_single_chemistry_menu_does_not(reference: ReferenceGenome) -> None:
    menu = design("chr2:1006:G>A", reference=reference, run_offtarget=False)
    assert len({c.chemistry for c in menu.candidates}) == 1
    assert _NOTE not in menu.rationale


def test_the_note_names_where_the_models_are_recorded(reference: ReferenceGenome) -> None:
    """It points at the provenance, so the claim is checkable rather than atmospheric."""
    menu = design("chr2:1050:G>A", reference=reference, run_offtarget=False)
    assert "named in the provenance" in menu.rationale
    assert len({model.name for model in menu.provenance.models}) > 1


def test_every_render_carries_it(reference: ReferenceGenome) -> None:
    from alleleforge.report.builder import build_report
    from alleleforge.report.export import report_to_json
    from alleleforge.report.html import render_html

    report = build_report(design("chr2:1050:G>A", reference=reference, run_offtarget=False))
    assert _NOTE in render_html(report)
    assert _NOTE in report_to_json(report)
