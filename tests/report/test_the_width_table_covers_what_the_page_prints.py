"""Every glyph the printable report emits has a real advance width, not the fallback.

`_text_width` looks each character up in `_HELVETICA_W` and falls back to
`_DEFAULT_ADVANCE` (556) for anything missing. The fallback is deliberately mid-range, but
it is wrong in both directions: `i` is 222, so a missing narrow glyph over-estimates by
2.5x, and `%` is 889 and `W` is 944, so a missing wide glyph *under*-estimates — and an
under-estimate is the direction that runs text off the page, which is the regression this
table was written to fix.

Nothing checked that the table covers the characters the reports really print. The two
`zip(..., strict=True)` calls that build the letter blocks guard those blocks' lengths at
import, but the punctuation was typed out by hand, and the glyph most likely to go missing
is the one some future note introduces.

The 90-odd individual widths are deliberately *not* frozen here. They are a hand
transcription of Adobe's published Helvetica metrics, and a one-unit error in any single
entry moves a line by 0.01pt — below the resolution at which anything observable changes,
with the property that matters (every line fits the 504pt column, and a rule fills it and
stops short) already guarded in `test_the_printable_sheet_fits_the_paper.py`. What is
pinned instead are the invariants a *typo* would break.
"""

from __future__ import annotations

import string
from pathlib import Path

from alleleforge.report import pdf
from alleleforge.report.builder import build_report
from alleleforge.report.pdf import (
    _DEFAULT_ADVANCE,
    _HELVETICA_W,
    _text_width,
    render_pdf,
)
from alleleforge.types.candidate import RankedMenu
from tests.pdf_text import pdf_text


def test_every_character_a_rendered_report_prints_has_its_own_width(
    prime_menu: RankedMenu, nuclease_menu: RankedMenu
) -> None:
    printed: set[str] = set()
    for menu in (prime_menu, nuclease_menu):
        printed |= set(pdf_text(render_pdf(build_report(menu, variant="chr2:70:A>C"))))
    printed -= {"\n", "\r", "\t"}
    assert printed, "no text was extracted; this test would pass vacuously"
    missing = sorted(c for c in printed if c not in _HELVETICA_W)
    assert not missing, (
        f"these glyphs reach the page with no measured width and fall back to "
        f"{_DEFAULT_ADVANCE}: {missing}. A wide glyph measured as 556 is under-measured, "
        "which is the direction that runs a line off the page."
    )


def test_the_table_covers_every_printable_ascii_character() -> None:
    """The forward-looking half: a note added later cannot introduce a missing glyph."""
    expected = set(string.printable) - set(string.whitespace) | {" "}
    missing = sorted(c for c in expected if c not in _HELVETICA_W)
    assert not missing, f"printable ASCII absent from the width table: {missing}"


def test_the_digits_share_one_advance() -> None:
    """Helvetica's figures are tabular: all ten are the same width, by design.

    Source-independent, and the strongest single check on the transcription: a typo in
    any one digit entry breaks it, and a column of numbers that does not line up is the
    visible symptom on the page.
    """
    widths = {d: _HELVETICA_W[d] for d in string.digits}
    assert len(set(widths.values())) == 1, f"digits have differing advances: {widths}"


def test_a_space_and_the_sentence_punctuation_share_the_narrow_advance() -> None:
    """Also tabular-by-design in Helvetica, and all three are on every line."""
    assert _HELVETICA_W[" "] == _HELVETICA_W["."] == _HELVETICA_W[","]


def test_every_advance_is_a_plausible_adobe_metric() -> None:
    """A transposed digit (556 -> 5560) or a dropped one (55) shows up here.

    The ceiling is 1015, not 1000: Helvetica's widest glyph in this table is `@` at
    1015, so an advance may legitimately exceed one em. A first draft of this test
    asserted 1000 and failed against a correct entry.
    """
    for glyph, advance in _HELVETICA_W.items():
        assert isinstance(advance, int), (glyph, advance)
        assert 100 <= advance <= 1015, (
            f"{glyph!r} has advance {advance}, outside the range an Adobe AFM uses "
            "for a Helvetica glyph (per 1000 em)"
        )


def test_the_fallback_is_the_advance_of_the_glyph_that_actually_renders() -> None:
    """An unmappable character is *drawn* as `?`, so it must be *measured* as `?`.

    `_escape` encodes the page to CP1252 with `errors="replace"`. A character
    WinAnsiEncoding cannot represent therefore reaches the paper as a question mark,
    and measuring it as anything other than Helvetica's `?` would describe a glyph
    the page does not contain.
    """
    assert _DEFAULT_ADVANCE == _HELVETICA_W["?"]
    assert "\u2192".encode("cp1252", "replace") == b"?", (
        "the encoding's replacement character is what makes the fallback correct"
    )


def test_a_glyph_that_survives_the_encoding_is_measured_as_itself() -> None:
    """The regression: an em dash renders as an em dash, so 556 under-measures it.

    `—` is CP1252 0x97 and reaches the page intact, but it was absent from the table
    and fell back to the `?` advance of 556 against a true 1000 — 4.44pt narrower per
    dash at 10pt. The caveat sentence about the ranked menu wrapped to 504.1pt on a
    504pt column because of it, and `test_the_printable_sheet_fits_the_paper` could
    not see the overflow: it measures with this table, so a glyph missing from the
    table is invisible to the one guard whose job is catching a line off the page.
    """
    for glyph in "\u2014\u2013\u2026\u00b1\u00b7":
        assert glyph.encode("cp1252", "replace") != b"?", (
            f"{glyph!r} no longer survives the encoding; it renders as `?` and the "
            "fallback would then be the right measurement"
        )
        assert glyph in _HELVETICA_W, (
            f"{glyph!r} reaches the page as itself but has no measured width"
        )
    assert _HELVETICA_W["\u2014"] == 1000, "Adobe Helvetica emdash"
    assert _text_width("\u2014") > _text_width("?"), (
        "an em dash is wider than the question mark it used to be measured as"
    )


def test_no_cp1252_glyph_this_library_prints_is_missing_a_width() -> None:
    """Forward-looking: catches the next such glyph where it is introduced.

    Scans the library's own source for non-ASCII characters that survive CP1252, which
    are exactly the ones that reach the page as themselves rather than as `?`.
    """
    found: set[str] = set()
    # The shipped package tree, read from disk. Note for a future reader: run this
    # while a mutation sweep is live and it passes for the wrong reason — the harness
    # rewrites a module through `ast.unparse`, which drops comments, so a glyph that
    # lives in one disappears from the file being scanned.
    for path in Path(pdf.__file__).parents[1].rglob("*.py"):
        for ch in path.read_text(encoding="utf-8"):
            if ord(ch) > 127 and ch.encode("cp1252", "replace") != b"?":
                found.add(ch)
    assert found, "no such glyph found; this test would pass vacuously"
    missing = sorted(c for c in found if c not in _HELVETICA_W)
    assert not missing, (
        f"these glyphs survive the page's encoding but have no measured width, so "
        f"each is measured as a question mark: {missing}"
    )
