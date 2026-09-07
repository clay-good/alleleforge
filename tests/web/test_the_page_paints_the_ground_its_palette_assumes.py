"""The served page was unreadable in a browser set to dark mode.

`styles.css` is a light design throughout — `#fff` tabs, a cream disclaimer box,
`#e2e2e2` hairlines — and it set `color: #1a1a1a` on `body` without ever setting a
background. `body` therefore inherited the user agent's, which in dark mode is dark: near
-black text on a dark ground. Every field label, every `small` help line and the tagline
disappeared, and the form controls rendered dark against the white panels because no
`color-scheme` was declared either.

Nothing caught it because nothing renders this page — the frontend tests read it as text,
which is the right trade for a build-free page but blind to exactly this. Two mechanical
properties stand in: a stylesheet that sets a foreground on `body` sets a background
there too, and the scheme its palette assumes is declared rather than inherited.
"""

from __future__ import annotations

import re
from pathlib import Path

_CSS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "styles.css"
).read_text(encoding="utf-8")


def _body_block() -> str:
    match = re.search(r"\bbody\s*\{([^}]*)\}", _CSS)
    assert match, "no `body` rule in styles.css — this check would be vacuous"
    return match.group(1)


def test_body_sets_a_background_wherever_it_sets_a_colour() -> None:
    block = _body_block()
    assert "color:" in block, "the `body` rule no longer sets a foreground"
    assert "background" in block, (
        "`body` sets a text colour and no background, so the page renders that text on "
        "whatever ground the browser supplies — dark, for a user in dark mode."
    )


def test_the_stylesheet_declares_the_scheme_its_palette_assumes() -> None:
    """Without it the UA paints selects and checkboxes for the wrong scheme."""
    assert re.search(r"color-scheme:\s*\w", _CSS), "no color-scheme declared"
