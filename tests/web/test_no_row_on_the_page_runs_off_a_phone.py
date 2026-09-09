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

It broke a second way. The sentence above — "the page has no other horizontal overflow at
that width" — was true when written and false once the cohort table grew columns: twelve
of them, ~980px of content that does not shrink, inside ancestors that all defaulted to
`overflow-x: visible`. Overflow propagates, so the whole document panned, not just the
table. Measured at 375x812: `document.scrollWidth` 998 against a 375px viewport, and 375
after the fix, with the table scrolling inside its own box.

So the rule here is the general one now: an element that can outgrow the viewport must
contain its own overflow. A flex row does it by wrapping, a table by living in a
scrolling container — same defect, two mechanisms, and the second was invisible to a
check written only for the first.
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


#: Tables whose container must scroll, mapped to the container that does it. A table's
#: content does not shrink — a twelve-column cohort row is ~980px whatever the viewport —
#: so the only two honest options are a scrolling box or a narrower table.
_SCROLLING_TABLE_CONTAINERS: dict[str, str] = {
    "table.results": "#batch-results",
}

#: Elements the page writes a `<table>` into, mapped to the same containers.
#:
#: The check below used to enumerate tables from the *stylesheet* — every rule matching
#: `table…`. That is the wrong population, and the round that added the off-target panel
#: proved it: two new tables, written into `#ot-results` with no rule of their own, were
#: invisible to a guard whose whole subject is tables. They happened to fit (measured at
#: 375px: 335 and 298), so nothing was broken — but a guard that cannot see an element is
#: not protecting it, and the next column would have gone unnoticed. The population is now
#: the markup that emits a table, which is what the rule is actually about.
_TABLE_TARGETS: dict[str, str] = {
    "batchResults": "#batch-results",
    "otResults": "#ot-results",
}


def _rules() -> dict[str, str]:
    """Return {selector: declarations} for every rule in the stylesheet."""
    rules = {}
    for match in re.finditer(r"(?m)^([^@{/\s][^{]*)\{([^}]*)\}", _CSS):
        rules[match.group(1).strip()] = match.group(2)
    assert len(rules) > 10, f"parsed {list(rules)} — this check would be vacuous"
    return rules


def test_every_table_scrolls_inside_its_own_box() -> None:
    """A wide table pans the page exactly as a non-wrapping flex row does."""
    rules = _rules()
    tables = [s for s in rules if re.match(r"table(\.|\s|$)", s)]
    assert tables, "no table rules found — this check would be vacuous"
    for selector in tables:
        base = selector.split()[0]
        container = _SCROLLING_TABLE_CONTAINERS.get(base)
        assert container is not None, (
            f"{selector} styles a table and no container is recorded for it. A table's "
            "content does not shrink, so without a scrolling ancestor it pans the whole "
            "page at a phone width. Record its container here."
        )
        body = rules.get(container)
        assert body is not None, f"{container} is recorded for {selector} but has no rule"
        assert "overflow-x: auto" in body, (
            f"{container} holds {selector} and does not scroll ({body.strip()}). "
            "Overflow propagates: a visible overflow on any ancestor moves the document, "
            "not the table."
        )


def _elements_given_a_table() -> set[str]:
    """Return the JS variables the page assigns table markup to, via `innerHTML`."""
    source = (
        Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
    ).read_text(encoding="utf-8")
    found = set()
    for match in re.finditer(r"(\w+)\.innerHTML\s*=(.*?);\n", source, re.S):
        if "<table" in match.group(2) or "table(" in match.group(2):
            found.add(match.group(1))
    return found


def test_every_element_the_page_writes_a_table_into_scrolls() -> None:
    """The population is the markup, not the stylesheet.

    A table with no CSS rule of its own is still a table, and still does not shrink.
    """
    rules = _rules()
    targets = _elements_given_a_table()
    assert targets, "no innerHTML assignment carrying a table found — this would be vacuous"
    for target in sorted(targets):
        container = _TABLE_TARGETS.get(target)
        assert container is not None, (
            f"`{target}.innerHTML` is given a table and no container is recorded for it. "
            "Record it in _TABLE_TARGETS with the element that scrolls."
        )
        body = rules.get(container)
        assert body is not None, f"{container} is recorded for {target} but has no rule"
        assert "overflow-x: auto" in body, (
            f"{container} receives a table and does not scroll ({body.strip()})."
        )


def test_the_recorded_table_targets_still_receive_tables() -> None:
    """An entry for an element that no longer renders a table hides the next one."""
    stale = sorted(set(_TABLE_TARGETS) - _elements_given_a_table())
    assert not stale, f"recorded as receiving a table, but no longer does: {stale}"


def test_the_recorded_containers_are_real_selectors() -> None:
    """A container recorded for a table that no longer exists hides the next one."""
    rules = _rules()
    stale = sorted(s for s in _SCROLLING_TABLE_CONTAINERS if s not in rules)
    assert not stale, f"containers recorded for table rules that are gone: {stale}"
