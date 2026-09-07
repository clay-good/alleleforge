"""One search description is read on a page with site rows and on a page without.

`SearchDescription` is built once by the off-target engine and rendered by two very
different surfaces. `aforge offtarget` prints a row per nominated site. The design report
prints none — it summarises, which is why a separate note now says where the rows are. Two
clauses were written for the first reader and shipped to both:

    …and each site's own PAM is on its row
    …scored below the reporting cut-off and is not shown

On the report, "its row" is a row that does not exist, and "not shown" contrasts a hidden
tail with a visible list that is also not there — leaving a reader who wants to check the
PAM of a low-stringency hit looking for a table nobody rendered.

Both now describe the *data* rather than a layout: a site records the PAM it was found
with, and a sub-threshold placement is not among the nominated sites. Each is true on both
surfaces and neither loses anything on the one that does print rows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.html import render_html
from alleleforge.types.candidate import RankedMenu

_TYPES = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "types" / "offtarget.py"

#: Words that describe a *layout* rather than the data. A description shared by a surface
#: that renders rows and one that does not may not use them.
_LAYOUT_WORDS = ("on its row", "is not shown", "the listed ones", "on the page", "printed below")


def _description_strings() -> list[str]:
    """Return the string literals `SearchDescription` composes for a reader."""
    import ast

    tree = ast.parse(_TYPES.read_text(encoding="utf-8"))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_the_strings_were_found() -> None:
    strings = _description_strings()
    assert any("PAM was broadened" in s for s in strings), "description text not found"


@pytest.mark.parametrize("word", _LAYOUT_WORDS)
def test_the_description_describes_data_not_a_layout(word: str) -> None:
    offenders = [s for s in _description_strings() if word in s]
    assert not offenders, (
        f"the shared search description says {word!r}: {offenders}. It is rendered by "
        "`aforge offtarget`, which prints a row per site, and by the design report, "
        "which prints none."
    )


def test_the_facts_those_clauses_carried_are_still_there() -> None:
    """Rewording must not quietly drop what the reader needed."""
    strings = " ".join(_description_strings())
    assert "records the PAM it was actually found with" in strings
    assert "not among the nominated sites" in strings
    assert "raising the cut-off cannot improve it" in strings


def test_the_report_never_promises_rows_it_does_not_draw(nuclease_menu: RankedMenu) -> None:
    """End to end on the surface that has no rows."""
    html = render_html(build_report(nuclease_menu))
    text = re.sub(r"<[^>]+>", " ", html)
    for word in _LAYOUT_WORDS:
        assert word not in text, word
