"""Two shipped HTML surfaces were unreadable in a browser set to dark mode.

Both set a near-black foreground on `body` and never set a background, so `body`
inherited the user agent's. In dark mode that is dark ink on a dark ground:

* **The served frontend.** Every field label, every `small` help line and the tagline
  disappeared, and the form controls rendered dark against the white panels because no
  `color-scheme` was declared either.
* **The design report** — worse, because it is the artifact a collaborator is *sent*,
  opened on a machine whose theme the author never sees. It rendered as a blank page.
  Its own charts were fine: the inlined SVG paints a white rect first.

Neither is a dark design half-finished. Both palettes are light throughout — white tabs,
a cream disclaimer panel, `#e2e2e2` hairlines — and simply never painted the ground they
assume. Nothing caught it because nothing renders these pages: the frontend tests read
the page as text, which is the right trade for a build-free page and structurally blind
to whether it can be read.

The rule is mechanical and applies to every stylesheet the project ships, so the next
surface inherits it: **a rule that sets a foreground on `body` sets a background there
too, and the palette's scheme is declared rather than inherited.** These are stand-ins
for a renderer, not a substitute for opening the page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src" / "alleleforge"


#: Every stylesheet the project ships, as (name, css). The report's lives in a Python
#: string, so it is read from the module that builds the page rather than a `.css` file.
def _stylesheets() -> list[tuple[str, str]]:
    from alleleforge.report.html import _STYLE

    return [
        ("report/html.py:_STYLE", _STYLE),
        (
            "web/frontend/styles.css",
            (_SRC / "web" / "frontend" / "styles.css").read_text(encoding="utf-8"),
        ),
    ]


def test_the_stylesheets_were_actually_found() -> None:
    """A zero-length sheet would satisfy every check below trivially."""
    sheets = _stylesheets()
    assert len(sheets) == 2
    for name, css in sheets:
        assert "body" in css and len(css) > 200, name


@pytest.mark.parametrize("name, css", _stylesheets(), ids=lambda v: v if isinstance(v, str) else "")
def test_a_body_that_sets_a_colour_sets_a_background(name: str, css: str) -> None:
    match = re.search(r"\bbody\s*\{([^}]*)\}", css)
    assert match, f"{name}: no `body` rule — this check would be vacuous"
    block = match.group(1)
    assert "color:" in block, f"{name}: the `body` rule no longer sets a foreground"
    assert "background" in block, (
        f"{name}: `body` sets a text colour and no background, so the page renders that "
        "text on whatever ground the browser supplies — dark, for a reader in dark mode."
    )


@pytest.mark.parametrize("name, css", _stylesheets(), ids=lambda v: v if isinstance(v, str) else "")
def test_the_scheme_the_palette_assumes_is_declared(name: str, css: str) -> None:
    """Without it the user agent paints selects, checkboxes and scrollbars for the wrong one."""
    assert re.search(r"color-scheme:\s*\w", css), f"{name}: no color-scheme declared"
