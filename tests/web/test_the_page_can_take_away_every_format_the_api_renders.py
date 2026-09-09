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

Its first version checked the single-variant panel only, and the cohort panel — which
downloads a different enum from a different row — turned out to have the same gap for the
same reason: the TSV round added a button to one panel and not the other. A guard written
against one of two panels is a guard against half the defect, so both are checked here.

Then a *third* panel arrived, and the guard was silent about it — the same shape a third
time. "Check a spacer" rendered a result and offered no way to keep it, and this guard
could not say so, because its population is *formats the API serves under `?format=`* and
`/api/offtarget` serves one shape and takes no format parameter. That is the right
population for the question it asks and the wrong one for the question underneath it,
which is: **can a reader take away what the page just showed them?** The last section here
asks that one, off the panels rather than off the format enums.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.web.api.app import BatchFormat, DesignFormat

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")

#: Formats the page legitimately does not offer, with the reason.
_NOT_ON_THE_PAGE: dict[str, str] = {
    "parquet": "a binary columnar file for a pipeline, which reads it from the API or "
    "the CLI; a browser download of it can be opened by nothing the browser has, and "
    "the TSV beside it carries the same columns in the same order",
}


#: Cohort renderings the panel legitimately does not offer, with the reason.
_NOT_ON_THE_COHORT_PANEL: dict[str, str] = {
    "parquet": "the same reason as the per-candidate one above — a binary columnar file "
    "for a pipeline, which reads it from the API or the CLI, and the TSV button beside "
    "it carries the same columns in the same order",
}


def _downloadable() -> set[str]:
    """Return the formats the single-variant panel fetches, read from its download calls."""
    formats = set(re.findall(r'download\("(\w+)"', _APP_JS))
    assert len(formats) > 2, f"parsed {formats} — this check would be vacuous"
    return formats


def _cohort_downloadable() -> set[str]:
    """Return the formats the cohort panel offers, read from its buttons and handlers."""
    buttons = set(re.findall(r'<button id="batch-download-(\w+)"', _INDEX))
    assert buttons, "no cohort download buttons found; this check would be vacuous"
    for name in buttons:
        assert f'"batch-download-{name}"' in _APP_JS, (
            f"the cohort panel shows a {name} button that nothing listens to"
        )
    return buttons


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


def test_the_cohort_panel_offers_every_cohort_rendering_or_says_why() -> None:
    """A cohort *is* a table, so the argument for the flat rendering is stronger here."""
    served = {f.value for f in BatchFormat}
    missing = sorted(served - _cohort_downloadable() - set(_NOT_ON_THE_COHORT_PANEL))
    assert not missing, (
        f"/api/batch renders {missing} and the cohort panel cannot download them. Add "
        "the button, or record it in _NOT_ON_THE_COHORT_PANEL with the reason."
    )


def test_the_cohort_exceptions_are_real_formats() -> None:
    served = {f.value for f in BatchFormat}
    stale = sorted(set(_NOT_ON_THE_COHORT_PANEL) - served)
    assert not stale, f"reasons recorded for cohort formats no longer served: {stale}"


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


# --- the question underneath the format enums --------------------------------


#: Every results panel, mapped to the element that must offer a way to keep the result.
#: A panel that renders something a reader would want and offers no download is the
#: defect at the top of this file, and it has now happened three times — each time to a
#: panel the previous guard's population did not include.
_RESULT_PANELS: dict[str, str] = {
    "panel-single": "actions",
    "panel-batch": "batch-actions",
    "panel-offtarget": "ot-actions",
}


def _panels_in_the_markup() -> set[str]:
    return set(re.findall(r'<section id="(panel-[\w-]+)"', _INDEX))


def test_every_panel_is_accounted_for() -> None:
    """The population is the panels the page has, not the ones this list remembers."""
    unlisted = sorted(_panels_in_the_markup() - set(_RESULT_PANELS))
    assert not unlisted, (
        f"these panels exist and no download surface is recorded for them: {unlisted}. "
        "A panel that renders a result a reader would want to keep must offer one."
    )
    stale = sorted(set(_RESULT_PANELS) - _panels_in_the_markup())
    assert not stale, f"recorded for panels that no longer exist: {stale}"


@pytest.mark.parametrize("panel", sorted(_RESULT_PANELS))
def test_every_panel_offers_a_way_to_keep_its_result(panel: str) -> None:
    actions = _RESULT_PANELS[panel]
    assert f'id="{actions}"' in _INDEX, f"{panel} records {actions}, which the markup lacks"
    section = _INDEX.split(f'id="{actions}"', 1)[1].split("</section>", 1)[0]
    buttons = re.findall(r'<button id="([\w-]+)"', section)
    assert buttons, f"{actions} holds no download button"
    for button in buttons:
        assert f'"{button}"' in _APP_JS, f"{button} has no handler in app.js"
