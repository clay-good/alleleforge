"""Hazard flags must be told apart from descriptive ones, and stay that way.

Found by running the product and reading the page: the top-ranked, Pareto-front
pegRNA for a realistic correction carried `close-nick` — its two nicks 8 nt apart,
which is a staggered double-strand break, the outcome prime editing is chosen to
avoid — printed in a comma-separated line with exactly the weight of
`epegRNA:tevopreQ1` and `both-nicks-searched`. The oligo *warnings* already had a
prominent channel for precisely this; the candidate's own hazards did not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from alleleforge.report.builder import CAVEAT_FLAGS, DESCRIPTIVE_FLAGS, caveats

_SRC = Path(__file__).resolve().parents[2] / "src" / "alleleforge"

#: Where candidate flags are built, as globs under `src/alleleforge`. Pinned by
#: `test_the_scan_covers_every_flag_source` so a new flag source cannot join silently.
_FLAG_SOURCES = ("design/**/*.py", "genome/coordinates.py")


def _is_flags(node: ast.AST) -> bool:
    """Return ``True`` if ``node`` names something called ``flags``."""
    return (isinstance(node, ast.Name) and node.id == "flags") or (
        isinstance(node, ast.Attribute) and node.attr == "flags"
    )


def _flag_literals(node: ast.AST) -> set[str]:
    """Return every string literal reachable in ``node``.

    An f-string contributes only its leading literal — `f"nick-distance:{d:+d}nt"` is
    the flag `nick-distance`, not also `+d` and `nt` — so this recurses by hand rather
    than `ast.walk`ing blindly into every format spec.
    """
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else set()
    if isinstance(node, ast.JoinedStr):
        first = node.values[0] if node.values else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return {first.value}
        return set()
    out: set[str] = set()
    for child in ast.iter_child_nodes(node):
        out |= _flag_literals(child)
    return out


def _emitted_flag_prefixes() -> set[str]:
    """Return the flag prefix of every candidate flag the source can attach.

    Reading the source rather than a hand-kept list is the point: a flag added
    tomorrow appears here without anyone remembering to update a test.

    Structural (AST) rather than a pile of regexes, because the regexes kept missing
    an idiom and each miss was a flag rendered with no sentence behind it. Three so
    far: `model_copy(update={"flags": ...})` (the base editor's `recommended`),
    `flags = [f"..." for ...]` (`ambiguous-region`), and a bare
    `return [f"..."]` from a flag builder (`intended-not-modal`). What is collected is
    every string literal that flows into something *named* flags — appended to it,
    assigned to it, returned from a `*_flags` function, or set as a `"flags"` value.

    Only where *candidate* flags are built. `report/oligos.py` fills a local also
    called `flags` with oligo warnings — a different channel, rendered separately —
    and scanning it made two oligo warnings look like classified candidate flags.
    The scope is hand-drawn, so `test_the_scan_covers_every_flag_source` pins it
    against the modules that actually attach candidate flags: it was `design/` alone
    while `genome/coordinates.py` built two more, and one of those went unclassified.
    """
    literals: set[str] = set()
    for path in sorted(path for root in _FLAG_SOURCES for path in _SRC.glob(root)):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"append", "extend"} and _is_flags(node.func.value):
                    for arg in node.args:
                        literals |= _flag_literals(arg)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(_is_flags(t) for t in targets) and node.value is not None:
                    literals |= _flag_literals(node.value)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if isinstance(key, ast.Constant) and key.value == "flags":
                        literals |= _flag_literals(value)
            elif isinstance(node, ast.FunctionDef) and node.name.endswith("flags"):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and sub.value is not None:
                        literals |= _flag_literals(sub.value)
    # `gc-out-of-band:{gc}` is one flag, not one per value; keep the part before the
    # first interpolated value.
    prefixes = {literal.split("{")[0].rstrip(":").strip() for literal in literals}
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
    # ...and the classification cannot rot into naming flags nothing emits. Both
    # tables, not just the descriptive one: `recommend-reference` sat in CAVEAT_FLAGS
    # with a written sentence for a flag no candidate carried, because the code that
    # attaches it had no caller. A caveat nobody can trigger is a promise, not a
    # safeguard, and it read as coverage.
    emitted = _emitted_flag_prefixes()
    for flag in (*DESCRIPTIVE_FLAGS, *CAVEAT_FLAGS):
        assert any(e.startswith(flag) or flag.startswith(e) for e in emitted), (
            f"{flag!r} is classified but nothing emits it"
        )


def test_the_scan_covers_every_flag_source() -> None:
    """The hand-drawn scope has to still be every place candidate flags are built.

    `_emitted_flag_prefixes` reads a fixed set of paths. A module that starts attaching
    candidate flags outside that set is invisible to the classification check — which is
    how `ambiguous-region:<kind>` reached a candidate with no sentence behind it.
    """
    attaches = {
        path.relative_to(_SRC).as_posix()
        for path in _SRC.rglob("*.py")
        if 'update={"flags"' in path.read_text() or "candidate_flags" in path.read_text()
    }
    scanned = {
        path.relative_to(_SRC).as_posix() for root in _FLAG_SOURCES for path in _SRC.glob(root)
    }
    assert attaches <= scanned, (
        f"these attach candidate flags but are not scanned: {sorted(attaches - scanned)}. "
        "Add them to _FLAG_SOURCES, or their flags go unclassified."
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
