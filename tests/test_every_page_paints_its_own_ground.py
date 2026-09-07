"""Every HTML page this project emits must be readable in a dark browser.

Three shipped surfaces were not, in two different ways.

The **served frontend** and the **design report** each set a near-black foreground on
`body` and no background, so `body` inherited the user agent's. In dark mode that is dark
ink on a dark ground: on the frontend every field label and help line disappeared; the
report — the artifact a collaborator is *sent* — rendered as a blank page.

The **leaderboard** failed the same way for the opposite reason: it declared no colours at
all. That is not neutral. With no `color-scheme` the user agent applies its default
*light* text rules while the browser paints a dark canvas underneath, so the board came
out dark grey on near-black. The first guard here was written over stylesheet sources and
was structurally blind to a page that has no stylesheet — it was added in the round that
fixed two of the three, and missed the third by asking about CSS files instead of pages.

So the check renders each page and asks of the document what a reader would: does it say
which scheme it was drawn for, and does it paint its own ground? None of these is a dark
design half-finished; all three palettes are light, and a distributed document that
changes appearance with the reader's OS setting is worse than one that states what it is.

These are stand-ins for a renderer, not a substitute for opening the page — all three
defects were found by looking, and only then written down.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src" / "alleleforge"


def _report_page() -> str:
    from alleleforge.report.builder import build_report
    from alleleforge.report.html import render_html
    from alleleforge.types.candidate import RankedMenu

    empty = RankedMenu(candidates=(), pareto_front=(), rationale="", provenance=None)
    return render_html(build_report(empty))


def _leaderboard_page() -> str:
    from alleleforge.benchmark.leaderboard import Leaderboard

    return Leaderboard().render_html()


def _frontend_page() -> str:
    """The served page plus the stylesheet it links, as a browser assembles them."""
    frontend = _SRC / "web" / "frontend"
    return (frontend / "index.html").read_text(encoding="utf-8") + (
        frontend / "styles.css"
    ).read_text(encoding="utf-8")


#: Every HTML document this project puts in front of a human, as (name, page-source).
_PAGES: tuple[tuple[str, str], ...] = (
    ("design report", _report_page()),
    ("bench leaderboard", _leaderboard_page()),
    ("served frontend", _frontend_page()),
)


def test_the_pages_were_actually_rendered() -> None:
    """An empty page would satisfy every check below trivially."""
    for name, page in _PAGES:
        assert "<body" in page or "body" in page, name
        assert len(page) > 400, name


@pytest.mark.parametrize("name, page", _PAGES, ids=[n for n, _ in _PAGES])
def test_the_page_declares_the_scheme_it_was_drawn_for(name: str, page: str) -> None:
    """Undeclared is not neutral: the UA pairs light text rules with a dark canvas."""
    assert re.search(r"color-scheme\s*:\s*\w", page), (
        f"{name} declares no colour scheme, so a browser in dark mode supplies one for "
        "it — light text rules on a dark canvas."
    )


@pytest.mark.parametrize("name, page", _PAGES, ids=[n for n, _ in _PAGES])
def test_the_page_paints_its_own_ground(name: str, page: str) -> None:
    match = re.search(r"\bbody\s*\{([^}]*)\}", page)
    assert match, f"{name}: no `body` rule at all, so it paints nothing"
    block = match.group(1)
    assert "background" in block, (
        f"{name}: `body` sets no background, so the page renders on whatever ground the "
        "browser supplies — dark, for a reader in dark mode."
    )
    assert "color:" in block, f"{name}: `body` sets a background and no foreground"
