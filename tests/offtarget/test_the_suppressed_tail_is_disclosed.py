"""A specificity a reader cannot reconstruct must say what else went into it.

`specificity_score()` is `1 / (1 + Σ reported scores + subthreshold_score_sum)`. The
tail is deliberate and load-bearing: a guide with real off-targets must not become
clean because the caller asked to *see* fewer of them, so the aggregate ignores the
display filter. That behaviour is right and already pinned.

What it produces is a headline number the rows cannot explain. Over a CAG repeat with
the reporting cut-offs raised past every hit:

    spacer CAGCAGCAGCAGCAGCAGCA / PAM NGG: 0 site(s), worst score 0.000,
    specificity 0.130

Three numbers. Two say there is nothing to look at; the third says the guide is bad,
and nothing on the page connects them. A reader who trusts *0 sites, worst 0.000* and
skims the third concludes the guide is clean — and a reader who notices the third
concludes the tool is broken. At the default cut-offs the same gap is quieter and still
there: summing the 25 shown scores gives 0.1337 where the tool reports 0.1304, because
0.19 of the denominator came from sites never displayed.

So the tail is disclosed: how many placements it covers and how much score mass they
carry, stated only when there is a tail. The behaviour does not change — this is the
sentence that makes the existing number readable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

_SPACER = "CAGCAGCAGCAGCAGCAGCA"


@pytest.fixture
def repeat_reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "repeat.fa"
    fasta.write_text(">chr7\n" + "A" * 40 + "CAG" * 30 + "T" * 40 + "\n")
    return ReferenceGenome(fasta)


def test_the_premise_a_hidden_tail_moves_the_number(repeat_reference: ReferenceGenome) -> None:
    """Without this the checks below could pass on a report with no tail at all."""
    report = search(_SPACER, PAM(pattern="NGG"), reference=repeat_reference)
    assert report.subthreshold_score_sum > 0.0
    shown = sum(site.score for site in report.sites)
    assert report.specificity_score() != pytest.approx(1.0 / (1.0 + shown))


def test_the_tail_is_stated_when_it_exists(repeat_reference: ReferenceGenome) -> None:
    description = search(
        _SPACER, PAM(pattern="NGG"), reference=repeat_reference
    ).search_description()
    assert "sub-threshold" in description
    assert "specificity" in description


def test_zero_sites_with_a_bad_specificity_explains_itself(
    repeat_reference: ReferenceGenome,
) -> None:
    """The sharp case: nothing shown, a terrible aggregate, and no other clue.

    Raising the cut-offs past every hit leaves `0 site(s), worst score 0.000,
    specificity 0.130`. The specificity is correct — a guide does not become clean
    because fewer of its off-targets are displayed — and is the only number on the
    page carrying the risk.
    """
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=repeat_reference,
        cfd_threshold=0.9,
        mit_threshold=0.9,
    )
    assert report.n_sites == 0
    assert report.specificity_score() < 0.5
    description = report.search_description()
    assert "sub-threshold" in description
    assert "not shown" in description or "below" in description


def test_a_report_with_no_tail_says_nothing_extra(repeat_reference: ReferenceGenome) -> None:
    """A note that always appears is not a note."""
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=repeat_reference,
        cfd_threshold=0.0,
        mit_threshold=0.0,
    )
    assert report.subthreshold_score_sum == 0.0
    assert "sub-threshold" not in report.search_description()


def test_the_description_stays_ascii(repeat_reference: ReferenceGenome) -> None:
    """It reaches the PDF, whose WinAnsi font has no glyph for a dash or a sigma."""
    description = search(
        _SPACER, PAM(pattern="NGG"), reference=repeat_reference
    ).search_description()
    assert description.isascii(), [c for c in description if not c.isascii()]
