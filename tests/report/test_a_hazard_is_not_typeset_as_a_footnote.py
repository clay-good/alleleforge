"""On the HTML report, "this insert cannot be cloned" was styled as de-emphasis.

Measured in a browser, the paragraph carrying `oligo warning: internal-BbsI-site` computed
to 13.6px in `rgb(102, 102, 102)` on no background — because it carried `class="muted"`.
So did every one of its neighbours:

    showing 3 of 54 predicted alleles (0.16 of the probability mass)   muted
    flags: offtarget-not-searched, no-5prime-g                        muted
    oligo warning: internal-BbsI-site:sgrna:+@8                       muted
    oligo prep: Phosphorylate the annealed oligos with T4 PNK         muted

A pagination note, a flag list, a cloning-lethal hazard and a routine protocol reminder,
all smaller and greyer than the body text around them. The `<strong>` label bolded two
words; the class greyed the sentence. The same was true of every `caveat —` line, which
is the *hazard subset* of the flags and exists precisely so hazards do not read with the
weight of `epegRNA:tevopreQ1`.

Hazards now use the report's own warning colours — the amber the research-use panel at
the top of the page already uses — at full size and full ink. This pins the relationship
rather than the hex: a hazard must not be typeset in the class whose job is to recede.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report
from alleleforge.report.html import _STYLE, render_html
from alleleforge.types.candidate import RankedMenu


def _paragraphs(html: str) -> list[tuple[str, str]]:
    """Return (class, text) for every `<p>` in the rendered page."""
    return [
        (m.group(1), re.sub(r"<[^>]+>", "", m.group(2)))
        for m in re.finditer(r"<p class='([^']+)'>(.*?)</p>", html, re.S)
    ]


@pytest.fixture
def page(prime_menu: RankedMenu) -> str:
    html = render_html(build_report(prime_menu))
    assert "caveat &mdash;" in html, "the fixture carries no caveat — this would be vacuous"
    return html


def test_a_caveat_is_not_muted(page: str) -> None:
    for css_class, text in _paragraphs(page):
        if text.startswith("caveat "):
            assert "muted" not in css_class, (css_class, text[:60])
            assert "hazard" in css_class, (css_class, text[:60])


def test_an_oligo_warning_is_not_muted(tmp_path: Path) -> None:
    # The R294 fixture: a random contig whose pegRNA extension happens to carry the
    # acceptor's own BsaI site, so the shipped default screen really fires.
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    menu = design(
        "chr2:1050:G>A", reference=ReferenceGenome(fasta, build="hg38"), run_offtarget=False
    )
    page = render_html(build_report(menu, with_oligos=True))
    warnings = [(css, text) for css, text in _paragraphs(page) if text.startswith("oligo warning:")]
    assert warnings, "the fixture produces no oligo warning — this check would be vacuous"
    for css_class, text in warnings:
        assert "muted" not in css_class, (css_class, text[:60])
        assert "hazard" in css_class, (css_class, text[:60])


def test_the_routine_notes_stay_muted(page: str) -> None:
    """The fix must separate hazards from footnotes, not promote the footnotes too."""
    recede = [text for css, text in _paragraphs(page) if "muted" in css]
    assert any(t.startswith("showing ") for t in recede), recede[:5]
    assert any(t.startswith("flags: ") for t in recede), recede[:5]


def test_the_hazard_style_recedes_less_than_the_muted_one() -> None:
    """The relationship, not the hex: a hazard may not be smaller or greyer."""

    def rule(name: str) -> str:
        match = re.search(rf"\.{name} \{{([^}}]*)\}}", _STYLE)
        assert match, f"no .{name} rule in the report stylesheet"
        return match.group(1)

    hazard, muted = rule("hazard"), rule("muted")
    assert "var(--muted)" not in hazard, hazard
    assert "var(--ink)" in hazard, hazard

    def size(block: str) -> float:
        match = re.search(r"font-size:\s*([\d.]+)rem", block)
        assert match, block
        return float(match.group(1))

    assert size("hazard" and hazard) > size(muted), (hazard, muted)
    # And it is set apart from the flow, not merely re-coloured inside it.
    assert "background" in hazard and "border" in hazard, hazard
