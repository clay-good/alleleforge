"""Hazard flags must be told apart from descriptive ones, and stay that way.

Found by running the product and reading the page: the top-ranked, Pareto-front
pegRNA for a realistic correction carried `close-nick` — its two nicks 8 nt apart,
which is a staggered double-strand break, the outcome prime editing is chosen to
avoid — printed in a comma-separated line with exactly the weight of
`epegRNA:tevopreQ1` and `both-nicks-searched`. The oligo *warnings* already had a
prominent channel for precisely this; the candidate's own hazards did not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.report.builder import CAVEAT_FLAGS, DESCRIPTIVE_FLAGS, caveats

_SRC = Path(__file__).resolve().parents[2] / "src" / "alleleforge"


def _emitted_flag_prefixes() -> set[str]:
    """Return the flag prefix of every ``flags.append(...)`` literal in the source.

    Reading the source rather than a hand-kept list is the point: a flag added
    tomorrow appears here without anyone remembering to update a test.
    """
    prefixes: set[str] = set()
    # Only where *candidate* flags are built. `report/oligos.py` fills a local also
    # called `flags` with oligo warnings — a different channel, rendered separately —
    # and scanning it made two oligo warnings look like classified candidate flags.
    for path in sorted((_SRC / "design").rglob("*.py")):
        text = path.read_text()
        calls = re.findall(r"flags\.append\((.*?)\)\n", text, re.S)
        # `flags.append(...)` is not the only way a flag is attached. The base-editor
        # vertical adds `recommended` with `model_copy(update={"flags": ...})`, so the
        # append-only scan reported the classification complete while that flag had
        # never been classified — the guard silently under-covering the thing it guards.
        calls += re.findall(r'"flags":\s*\((.*?)\)', text, re.S)
        for call in calls:
            # Every string literal in the call, not just the first: one `append` can
            # carry a conditional emitting several flags (`pe3b`/`pe3`/`no-nick`).
            for literal in re.findall(r"f?\"([^\"]*)\"", call):
                # Keep the part before the first interpolated value:
                # `gc-out-of-band:{gc}` is one flag, not one per value.
                prefixes.add(literal.split("{")[0].rstrip(":").strip() or literal)
    return {p for p in prefixes if p and not p.startswith("*")}


def test_every_emitted_flag_is_classified() -> None:
    """A new flag must be called a hazard or a description — never default to silence.

    The unclassified default has to be "needs a decision", not "harmless": defaulting
    to harmless is the direction that loses a hazard, which is how `close-nick` came
    to be rendered as decoration in the first place.
    """
    known = set(CAVEAT_FLAGS) | set(DESCRIPTIVE_FLAGS)
    unclassified = {
        flag
        for flag in _emitted_flag_prefixes()
        if flag not in known and not any(flag.startswith(k) for k in known)
    }
    assert not unclassified, (
        f"flags classified as neither caveat nor descriptive: {sorted(unclassified)}. "
        "Add each to CAVEAT_FLAGS (with the reason it matters) or DESCRIPTIVE_FLAGS."
    )
    # ...and the classification cannot rot into naming flags nothing emits.
    emitted = _emitted_flag_prefixes()
    for flag in DESCRIPTIVE_FLAGS:
        assert any(e.startswith(flag) or flag.startswith(e) for e in emitted), (
            f"{flag!r} is classified but nothing emits it"
        )


def test_a_hazard_is_separated_from_decoration() -> None:
    flags = ("epegRNA:tevopreQ1", "pe3b", "nick-distance:+8nt", "close-nick", "clean")
    found = caveats(flags)
    assert [f for f, _ in found] == ["close-nick"]
    assert "double-strand break" in found[0][1]
    # A candidate with nothing wrong raises nothing, or the section is noise.
    assert caveats(("epegRNA:tevopreQ1", "pe3b", "clean")) == ()


def test_a_valued_flag_matches_on_its_prefix() -> None:
    """`gc-out-of-band:0.25` carries its value; a bare flag beside it is unaffected."""
    assert [f for f, _ in caveats(("gc-out-of-band:0.25",))] == ["gc-out-of-band:0.25"]
    assert [f for f, _ in caveats(("nick-distance:+8nt", "close-nick"))] == ["close-nick"]
    # A prefix must not match a longer, different flag name.
    assert caveats(("clean-something-else",)) == ()


@pytest.mark.parametrize("renderer", ["html", "pdf"])
def test_both_renders_give_a_caveat_its_own_line(renderer: str, ancestry_menu: object) -> None:
    """Prominent in both, or a PDF leave-behind still buries it in the flag list."""
    from alleleforge.report.builder import build_report
    from alleleforge.report.html import render_html
    from alleleforge.report.pdf import render_pdf
    from alleleforge.types.candidate import RankedMenu

    assert isinstance(ancestry_menu, RankedMenu)
    flagged = ancestry_menu.model_copy(
        update={
            "candidates": tuple(
                c.model_copy(update={"flags": (*c.flags, "close-nick")})
                for c in ancestry_menu.candidates
            )
        }
    )
    report = build_report(flagged)
    if renderer == "html":
        out = render_html(report)
        assert "caveat &mdash; close-nick:" in out
    else:
        out_bytes = render_pdf(report)
        assert b"CAVEAT - close-nick:" in out_bytes
        assert b"staggered" in out_bytes  # the reason, not only the flag name
