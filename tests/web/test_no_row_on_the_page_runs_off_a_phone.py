"""A flex row that does not wrap grows until the page pans sideways.

Measured in a browser at 375x812, after a design: `document.scrollWidth` was 503 against
a 375px viewport, and the two elements past the right edge were the download buttons. The
row of three had already been 4px over before this session; adding a fourth made it 128.
A non-wrapping flex row does not care how much room it has, and the page has no other
horizontal overflow at that width — the form's `.row` has always wrapped, and this row
was the exception.

Nothing in the suite drives a browser, so the check is on the rule rather than the
rendering: a `display: flex` row that lays out left-to-right must say what happens when
it runs out of room. That is a rule the next button can break, which is the same way this
one broke.
"""

from __future__ import annotations

import re
from pathlib import Path

_CSS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "styles.css"
).read_text(encoding="utf-8")

#: Flex rules that legitimately do not wrap, with the reason.
_NEED_NO_WRAP: dict[str, str] = {
    ".field": "flex-direction: column — it stacks, so there is no row to overflow",
    ".checkbox": "a box and its label; wrapping would split the control from its text, "
    "and the pair is shorter than the narrowest supported viewport",
}


def _flex_rules() -> dict[str, str]:
    """Return {selector: declarations} for every rule that sets `display: flex`."""
    rules = {}
    for match in re.finditer(r"(?m)^([^@{/\s][^{]*)\{([^}]*)\}", _CSS):
        selector, body = match.group(1).strip(), match.group(2)
        if re.search(r"display:\s*flex", body):
            rules[selector] = body
    assert len(rules) > 3, f"parsed {list(rules)} — this check would be vacuous"
    return rules


def test_every_horizontal_flex_row_says_what_happens_when_it_runs_out_of_room() -> None:
    offenders = [
        selector
        for selector, body in _flex_rules().items()
        if "flex-wrap" not in body and selector not in _NEED_NO_WRAP
    ]
    assert not offenders, (
        f"{offenders} lay out in a row and never wrap, so the page pans sideways once "
        "the contents outgrow a phone. Add `flex-wrap: wrap`, or record the selector in "
        "_NEED_NO_WRAP with the reason."
    )


def test_the_recorded_exceptions_are_real_selectors() -> None:
    stale = sorted(set(_NEED_NO_WRAP) - set(_flex_rules()))
    assert not stale, f"reasons recorded for flex rules that no longer exist: {stale}"


def test_the_download_row_wraps() -> None:
    """The row this was found on, named directly: it is the one that keeps growing."""
    actions = _flex_rules()[".actions"]
    assert "flex-wrap: wrap" in actions, actions
