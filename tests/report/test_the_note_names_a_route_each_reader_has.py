"""The sentence pointing at the full spectrum named two routes, for four audiences.

`RANKED_MENU_SOURCE` is rendered into the HTML report, the PDF, and the notes both flat
exports carry — artifacts read by a terminal user, a Python caller, an HTTP client and a
browser. It named `aforge design --json` and `menu_to_json`: a terminal and a Python API.

The browser case is the one that already had a round of its own. The served page displays
that sentence to the audience the README describes as "users who will not touch a
terminal"; the fix then was to build them a route — `POST /api/design?format=menu` and a
**Download full menu** button — and the sentence was left pointing at the two it already
had. The remedy existed and the text still sent the reader somewhere they could not go,
which is the same defect one layer up.

So the note names a route per surface, and this pins each one to a route that exists: the
CLI format, the HTTP format, the page's button, and the library function.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.cli.main import OutputFormat
from alleleforge.report.builder import RANKED_MENU_SOURCE, WITHHELD_ALLELES_NOTE
from alleleforge.web.api.app import DesignFormat

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"


def test_the_cli_route_it_names_is_a_real_format() -> None:
    assert "--format menu" in RANKED_MENU_SOURCE, RANKED_MENU_SOURCE
    assert OutputFormat.menu.value == "menu"


def test_the_http_route_it_names_is_a_real_format() -> None:
    assert "format=menu" in RANKED_MENU_SOURCE, RANKED_MENU_SOURCE
    assert DesignFormat.menu.value == "menu"


def test_the_button_it_names_is_on_the_page() -> None:
    """The audience that cannot follow any of the other three."""
    index = (_FRONTEND / "index.html").read_text(encoding="utf-8")
    app_js = (_FRONTEND / "app.js").read_text(encoding="utf-8")
    label = "Download full menu"
    assert label in RANKED_MENU_SOURCE, RANKED_MENU_SOURCE
    assert label in index, "the note names a button the page does not show"
    assert "download-menu" in app_js, "the button the note names has no handler"


def test_the_library_route_it_names_is_importable() -> None:
    from alleleforge.report.export import menu_to_json  # noqa: F401

    assert "menu_to_json" in RANKED_MENU_SOURCE, RANKED_MENU_SOURCE


def test_the_withheld_note_carries_the_whole_sentence() -> None:
    """Both notes are built from it, so neither can drift from the routes above."""
    assert RANKED_MENU_SOURCE in WITHHELD_ALLELES_NOTE, WITHHELD_ALLELES_NOTE
