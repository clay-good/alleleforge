"""Three Download buttons stood on the page before anything had been designed.

The page hides and shows sections with the `hidden` attribute — `actions.hidden = true`
until a design succeeds. The attribute works by a user-agent rule, `[hidden] { display:
none }`, which any author rule setting `display` outranks. `.actions { display: flex }`
did exactly that, so both download bars were `hidden === true` and `display: flex` at the
same time, and the page opened with *Download PDF / JSON / TSV* offered for a result that
did not exist. Pressing one returned silently.

That is a whole class, not one rule: every element the page toggles this way is one
`display` declaration away from the same bug, and the failure is invisible to a test that
reads the markup — the attribute really is set. So the fix is the neutralizing rule, and
the check is that the rule is there and outranks the classes that could beat it.

Found by opening the page. Nothing else was going to find it.
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_CSS = (_FRONTEND / "styles.css").read_text(encoding="utf-8")
_HTML = (_FRONTEND / "index.html").read_text(encoding="utf-8")
_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")


def test_the_stylesheet_neutralizes_the_attribute_it_cannot_otherwise_beat() -> None:
    match = re.search(r"\[hidden\]\s*\{([^}]*)\}", _CSS)
    assert match, (
        "styles.css has no `[hidden]` rule, so any class setting `display` un-hides the "
        "element it is on while `el.hidden` still reads true."
    )
    body = match.group(1).replace(" ", "")
    assert "display:none" in body, match.group(1)
    assert "!important" in body, (
        "without !important a later class rule of equal specificity wins again"
    )


def test_every_class_that_sets_display_is_covered_by_that_rule() -> None:
    """The rule must precede nothing and beat everything — hence `!important`.

    Listing the offenders makes the collision concrete rather than theoretical: these are
    the classes that were, or could have been, on a `hidden` element.
    """
    setters = {m.group(1) for m in re.finditer(r"^\.([\w-]+)[^{]*\{[^}]*display\s*:", _CSS, re.M)}
    assert setters, "no class sets display — this check would be vacuous"
    assert "actions" in setters, "the class that caused this is gone; re-point the test"


def test_the_page_still_marks_those_sections_hidden() -> None:
    """The CSS fix is only meaningful if the markup still asks for the behaviour."""
    for element_id in ("actions", "batch-actions", "report", "panel-batch"):
        pattern = rf'id="{element_id}"[^>]*\bhidden\b'
        assert re.search(pattern, _HTML), element_id


def test_a_download_with_nothing_designed_says_so() -> None:
    """Behind the CSS fix: the handlers no longer return in silence."""
    for function in ("download", "downloadBatch"):
        body = re.search(rf"function {function}\(.*?\n\}}", _JS, re.S)
        assert body, function
        guard = re.search(r"if \(!last\w*\) \{(.*?)\}", body.group(0), re.S)
        assert guard, f"{function} no longer guards on a missing result"
        assert "Run a" in guard.group(1), (
            f"{function} returns without telling the user why: {guard.group(1)!r}"
        )
