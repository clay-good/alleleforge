"""`chrom:pos:ref>alt` goes in 1-based and comes out 0-based, in the same syntax.

    $ aforge resolve chr1:1018:T>A
    chr1:1017:T>A  [snv, build hg38, from coordinates]

That is a documented choice — the tool emits 0-based half-open everywhere, and says so.
The trap is that the *printed* form is syntactically the *input* form, and the input form
is read as a VCF record, which is 1-based. So the one locus this tool prints that cannot
be handed straight back to it is the variant, and the two ways that fails are both bad:

    $ aforge resolve chr1:1017:T>A
    error: reference mismatch at chr1:1016: ... (wrong build?)

The build is the one thing that was not wrong. And when the neighbouring base happens to
match the asserted ref, nothing fails at all: the run designs an edit one base away, with
every downstream number correct for the wrong locus.

Nothing can detect the silent case — a valid variant is a valid variant — so this works
the two places it can. The refusal names the convention and hands back the string that
does work, because the evidence is in hand at the moment of the refusal: the ref sits one
base to the right. And the human renders carry the warning beside the variant, where the
surprise is, rather than in the footer's general note about loci.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import VARIANT_POSITION_NOTE, build_report
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from tests.pdf_text import pdf_text

#: A contig whose base at 0-based 1017 is `T` and whose base at 1016 is `A`, so the
#: paste-back lands on a mismatch rather than silently succeeding.
_CONTIG = ("AC" * 508) + "G" + "T" + ("GC" * 200)


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + _CONTIG + "\n")
    return path


def test_the_fixture_is_the_off_by_one_case() -> None:
    """Without this the refusal below could be an ordinary mismatch."""
    assert _CONTIG[1017] == "T"
    assert _CONTIG[1016] != "T"


def test_the_printed_variant_is_one_lower_than_the_input(fasta: Path) -> None:
    """The premise. If this ever stops being true, the rest of the file is moot."""
    from alleleforge.variant.resolver import resolve

    resolved = resolve(
        "chr1:1018:T>A", build="hg38", reference=ReferenceGenome(fasta, build="hg38")
    )
    assert str(resolved.variant) == "chr1:1017:T>A"


def test_pasting_the_printed_variant_back_names_the_convention(fasta: Path) -> None:
    result = CliRunner().invoke(app, ["resolve", "chr1:1017:T>A", "--reference-fasta", str(fasta)])
    assert result.exit_code != 0
    output = result.output + result.stderr
    assert "1-based" in output, output
    # The remedy is the string that works — which is the caller's original input.
    assert "chr1:1018:T>A" in output, output
    assert "wrong build?" not in output, "the build is the one thing that is not wrong"


def test_a_genuine_build_mismatch_still_blames_the_build(fasta: Path) -> None:
    """The remedy must not fire on every mismatch, or it becomes noise."""
    result = CliRunner().invoke(
        app, ["resolve", "chr1:400:GGGGG>A", "--reference-fasta", str(fasta)]
    )
    assert result.exit_code != 0
    output = result.output + result.stderr
    assert "wrong build?" in output, output


def test_both_human_renders_warn_beside_the_variant(fasta: Path) -> None:
    menu = design(
        "chr1:1018:T>A", reference=ReferenceGenome(fasta, build="hg38"), run_offtarget=False
    )
    report = build_report(menu, variant="chr1:1017:T>A", intent="correct")
    # `_esc` turns the note's `ref>alt` into `ref&gt;alt`, so the HTML carries the
    # escaped form of the same sentence — compared as such rather than weakened to a
    # substring that would also match a paraphrase.
    assert escape(VARIANT_POSITION_NOTE) in render_html(report)
    # The PDF writer hard-wraps to its column width, so the note spans two text runs.
    # Reassembled from the `(...) Tj` payloads rather than matched as a fragment, so a
    # truncated or paraphrased note fails instead of passing on its first clause.
    prose = pdf_text(render_pdf(report))
    assert VARIANT_POSITION_NOTE in prose, prose[:400]


def test_a_report_with_no_variant_carries_no_note(fasta: Path) -> None:
    """The note explains a number that is not there."""
    menu = design(
        "chr1:1018:T>A", reference=ReferenceGenome(fasta, build="hg38"), run_offtarget=False
    )
    report = build_report(menu, variant=None, intent="correct")
    assert escape(VARIANT_POSITION_NOTE) not in render_html(report)
