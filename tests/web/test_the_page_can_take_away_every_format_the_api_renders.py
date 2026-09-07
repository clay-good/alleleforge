"""The one rendering the page could not give you was the one it was showing you.

`/api/design?format=` serves five renderings. The page offered PDF, JSON and TSV — the
TSV added in its own round, with the reasoning written next to the button: the format a
bench scientist opens in Excel "had to be produced by another shell". HTML was in exactly
that position and is worse, because the page is *already rendering* it.

The report is embedded in a deliberately locked-down iframe — no scripts, no forms, no
same-origin — so it cannot report its own height back and the frame is a fixed 1400px. A
report is routinely tens of thousands of pixels tall, so a reader sees a few percent of
it through a keyhole with no scroll cue, and had no way to take the document away, keep
it, or send it to a colleague. Every other rendering could be downloaded; the one on the
screen could not.

The check is the shape the request-field guard already uses: every format the API serves
is downloadable from the page, or recorded here with the reason it is not.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.web.api.app import DesignFormat

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")

#: Formats the page legitimately does not offer, with the reason.
_NOT_ON_THE_PAGE: dict[str, str] = {
    "parquet": "a binary columnar file for a pipeline, which reads it from the API or "
    "the CLI; a browser download of it can be opened by nothing the browser has, and "
    "the TSV beside it carries the same columns in the same order",
}


def _downloadable() -> set[str]:
    """Return the formats the page actually fetches, read from the download calls."""
    formats = set(re.findall(r'download\("(\w+)"', _APP_JS))
    assert len(formats) > 2, f"parsed {formats} — this check would be vacuous"
    return formats


def test_every_rendering_is_downloadable_or_says_why() -> None:
    served = {f.value for f in DesignFormat}
    missing = sorted(served - _downloadable() - set(_NOT_ON_THE_PAGE))
    assert not missing, (
        f"the API renders {missing} and the page cannot download them. Add the button, "
        "or record it in _NOT_ON_THE_PAGE with the reason."
    )


def test_the_recorded_exceptions_are_real_formats() -> None:
    served = {f.value for f in DesignFormat}
    stale = sorted(set(_NOT_ON_THE_PAGE) - served)
    assert not stale, f"reasons recorded for formats the API no longer serves: {stale}"


def test_an_excuse_does_not_outlive_the_gap() -> None:
    """As elsewhere: an entry both offered and excused is a false record, not a no-op."""
    both = sorted(set(_NOT_ON_THE_PAGE) & _downloadable())
    assert not both, f"the page downloads {both} and still records a reason it does not"


def test_every_download_button_is_wired() -> None:
    """A button with no listener is a control that silently does nothing when pressed."""
    buttons = set(re.findall(r'<button id="download-(\w+)"', _INDEX))
    assert buttons, "no download buttons found in the markup"
    assert buttons == _downloadable(), (
        f"markup has {sorted(buttons)}, app.js downloads {sorted(_downloadable())}"
    )


def test_the_reader_is_told_the_frame_is_not_the_whole_report() -> None:
    """The frame is a fixed height and cannot resize itself; silence reads as an end."""
    assert 'id="report-note"' in _INDEX, "nothing tells the reader the frame scrolls"
    assert "report-note" in _APP_JS, "the note is never revealed with the report"
    note = re.search(r'<small id="report-note"[^>]*>((?:.|\n)*?)</small>', _INDEX)
    assert note and "Download HTML" in note.group(1), (
        "the note should point at the rendering that can be read at full height"
    )
