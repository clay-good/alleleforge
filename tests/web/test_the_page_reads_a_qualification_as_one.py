"""A qualification rendered as a list item reads as its opposite.

The cohort table gained a `<source>:build-mismatch` key: `{"gnomad": 2,
"gnomad:build-mismatch": 2}` means "two gnomAD records were found here and neither could be
used, because they assert a base this genome does not have". The page's renderer for that
cell prints the mapping's **keys**, so it came out as:

    OFF-TARGET BASIS
    gnomad, gnomad:build-mismatch

— which reads as *two sources*, both of which contributed. The exact opposite of what the
number says, on the surface with no terminal to fall back to, from a disclosure added two
rounds earlier by someone who did not open the page.

The count is the content: "2 of 2 records wrong build" is actionable and "gnomad:build-
mismatch" is not, and it belongs in the hazard style the caveats column uses, not in the
neutral list of sources that were read.
"""

from __future__ import annotations

from pathlib import Path

_APP_JS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
).read_text(encoding="utf-8")


def test_the_renderer_special_cases_the_qualification() -> None:
    assert ":build-mismatch" in _APP_JS, (
        "the page renders `offtarget_sources` keys verbatim, so a build-mismatch "
        "qualification appears in the list of sources that contributed"
    )


def test_it_renders_the_count_and_not_the_key() -> None:
    """A reader acts on 'how many', not on a key name."""
    assert "record(s) wrong build" in _APP_JS
    assert "of ${of}" in _APP_JS, "the count is not stated against the number considered"


def test_it_is_styled_as_a_hazard() -> None:
    """`err` is the class the caveats column uses; a source list is neutral text."""
    index = _APP_JS.index("record(s) wrong build")
    window = _APP_JS[index - 200 : index]
    assert 'class="err"' in window, "the qualification is rendered as neutral text"
