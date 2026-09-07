"""A caveat pointed a reader *down* at a table both renders draw above it.

    caveat — outcome-is-nhej-spectrum: the outcome distribution below is the NHEJ
    indel spectrum — the byproduct of this strategy, not the intended correction…

`_candidate_html` and `_candidate_lines` both build the allele table first and the caveats
afterwards, so "below" sent a reader looking downward past the flags, the oligo block and
the score line for something they had already scrolled by. The sentence was written where
the flag is *set* — `cas9.py` carries the same wording in a comment — which is the one
place in the codebase with no view of where it lands.

A caveat is positioned by whichever surface renders it, and the same reasons are read on a
page, on a printable sheet, and potentially anywhere else that grows a caveat section.
None of them may depend on the position they end up in.

This is the same rule R320 applied to the shared search description, one layer down, and
the guard is deliberately narrow: it forbids the words in *caveat reasons*, where the
target's position is not the string's to know. `oligo_lines` keeps "the scores above",
because that block controls its own internal order on both renders.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.builder import CAVEAT_FLAGS, caveats
from alleleforge.report.html import _candidate_html
from alleleforge.report.pdf import _candidate_lines

#: Patterns for *deictic* use — a word pointing at page content. Deliberately not a bare
#: word list: `offtarget-high` legitimately says a site "scores at or above the triage
#: band", which is a comparison, and a check that cannot tell the two apart would either
#: fire on that or need an exception list that hides the next real one.
_POSITIONAL = (
    r"\b(?:below|above)\s+(?:is|are|shows?|lists?)\b",
    r"\b(?:the|this)\s+\w+(?:\s+\w+)?\s+(?:below|above)\b",
    r"\b(?:overleaf|on the left|on the right|earlier on this page)\b",
)


def test_the_reasons_were_found() -> None:
    assert len(CAVEAT_FLAGS) > 5, sorted(CAVEAT_FLAGS)


@pytest.mark.parametrize("pattern", _POSITIONAL)
def test_no_caveat_reason_says_where_to_look(pattern: str) -> None:
    offenders = {
        flag: reason for flag, reason in CAVEAT_FLAGS.items() if re.search(pattern, reason)
    }
    assert not offenders, (
        f"caveat reasons match {pattern!r}: {offenders}. A caveat is positioned by "
        "whichever surface renders it — both current renders draw the allele table "
        "before the caveats, so 'below' points backwards."
    )


def test_a_numeric_comparison_is_not_mistaken_for_a_direction() -> None:
    """The check must not fire on `scores at or above the triage band`."""
    comparison = CAVEAT_FLAGS["offtarget-high"]
    assert "at or above" in comparison, "the fixture claim moved; re-point this test"
    assert not any(re.search(p, comparison) for p in _POSITIONAL), comparison


def test_the_renders_really_do_put_the_table_first() -> None:
    """The premise, read off the renderers rather than assumed.

    If a render ever draws caveats above the table, "below" becomes correct there and
    wrong on the other one — which is the argument for positionless prose, not for
    flipping the word.
    """
    import inspect

    for renderer in (_candidate_html, _candidate_lines):
        source = inspect.getsource(renderer)
        table = source.index("outcome_top")
        caveat = source.index("caveats(c.flags)")
        assert table < caveat, renderer.__name__


def test_the_reason_still_says_what_the_distribution_is() -> None:
    """Rewording must not drop the fact the caveat exists to deliver."""
    reason = dict(caveats(("outcome-is-nhej-spectrum",)))["outcome-is-nhej-spectrum"]
    assert "NHEJ indel spectrum" in reason
    assert "byproduct" in reason
    assert "not the intended correction" in reason
