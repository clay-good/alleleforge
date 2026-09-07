"""A pX330 user's inserts were screened for BsaI, and only the scheme name said so.

`--vector-scheme px330-bbsi` on an all-prime menu is completely inert: an sgRNA acceptor
defines no pegRNA 3'-extension overhangs, so every pegRNA candidate stays on the pegRNA
acceptor — a deliberate choice, since failing the whole report would be worse. What was
missing is the sentence. Every candidate's block names the scheme it was built with, so
the fact was *derivable*, by noticing that a name differs from the one you typed.

This report already states an inert input everywhere else it has one: a cell context prime
alone consumes, a PAM fallback the nuclease vertical alone takes. A vector is the same
shape with a sharper consequence — the enzyme the inserts were screened against is not the
one that will cut them.

The note fires only when nothing used the requested scheme. A menu that used it, or a
mixed menu that used it for some candidates, has nothing to report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report
from alleleforge.report.html import render_html
from alleleforge.report.oligos import LENTIGUIDE_BSMBI, PEGRNA_GG_BSAI, PX330_BBSI
from alleleforge.types.edit import EditIntent


@pytest.fixture
def prime_only(tmp_path: Path) -> object:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    menu = design(
        "chr2:71:A>C",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
        max_candidates_per_chemistry=3,
    )
    assert menu.candidates, "no candidates"
    return menu


def test_the_fixture_cannot_use_an_sgrna_vector(prime_only: object) -> None:
    """The premise: an sgRNA acceptor has no 3'-extension overhangs."""
    report = build_report(prime_only, with_oligos=True, scheme=PX330_BBSI)
    used = {c.oligos.scheme.name for c in report.candidates if c.oligos}
    assert used == {PEGRNA_GG_BSAI.name}, used


def test_an_unused_vector_is_named_in_the_rationale(prime_only: object) -> None:
    rationale = build_report(prime_only, with_oligos=True, scheme=PX330_BBSI).rationale or ""
    assert "px330-bbsi" in rationale, rationale
    assert "no candidate could use it" in rationale
    assert "pegrna-gg-bsai was used instead" in rationale


def test_it_names_the_enzyme_that_did_not_screen(prime_only: object) -> None:
    """The consequence, not just the substitution: BbsI is what would have cut."""
    rationale = build_report(prime_only, with_oligos=True, scheme=PX330_BBSI).rationale or ""
    assert "not BbsI" in rationale, rationale


def test_a_vector_that_was_used_says_nothing(prime_only: object) -> None:
    """A note that fires when nothing went wrong is noise."""
    rationale = build_report(prime_only, with_oligos=True, scheme=PEGRNA_GG_BSAI).rationale or ""
    assert "no candidate could use it" not in rationale


def test_no_vector_requested_says_nothing(prime_only: object) -> None:
    rationale = build_report(prime_only, with_oligos=True).rationale or ""
    assert "no candidate could use it" not in rationale


def test_no_oligos_requested_says_nothing(prime_only: object) -> None:
    """Nothing was screened at all, so no screen ran against the wrong enzyme."""
    rationale = build_report(prime_only, with_oligos=False, scheme=PX330_BBSI).rationale or ""
    assert "no candidate could use it" not in rationale


def test_the_note_reaches_a_reader(prime_only: object) -> None:
    html = render_html(build_report(prime_only, with_oligos=True, scheme=PX330_BBSI))
    assert "no candidate could use it" in html


def test_a_nuclease_menu_uses_the_sgrna_vector(tmp_path: Path) -> None:
    """The other side: where the vector applies, it applies and nothing is said."""
    path = tmp_path / "ko.fa"
    contig = ("T" * 20) + "ACGTAACGTTACGTAACGTT" + "TGG" + ("T" * 20)
    path.write_text(">chr1\n" + contig + "\n")
    # The ref base read off the contig, 1-based as the variant string is, so the fixture
    # cannot drift from the sequence it is built on.
    menu = design(
        f"chr1:26:{contig[25]}>A",
        reference=ReferenceGenome(path, build="hg38"),
        run_offtarget=False,
        intent=EditIntent.KNOCK_OUT,
    )
    report = build_report(menu, with_oligos=True, scheme=LENTIGUIDE_BSMBI)
    used = {c.oligos.scheme.name for c in report.candidates if c.oligos}
    assert used == {LENTIGUIDE_BSMBI.name}, used
    assert "no candidate could use it" not in (report.rationale or "")
