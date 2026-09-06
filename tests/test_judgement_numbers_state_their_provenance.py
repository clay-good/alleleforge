"""A number that gates what a user sees must say where it came from.

AlleleForge's stated purpose is honest labeling, and several of its most consequential
constants are *judgements*: the CFD and MIT thresholds decide which off-target sites
appear in a report at all, the MAF threshold decides which population variants are
considered, the GC band decides which spacers get a quality caveat. None of them is a
published cutoff, and three of them said nothing about that — `DEFAULT_CFD_THRESHOLD`
carried the comment "spec defaults", which reads as though a specification somewhere
had derived it.

The risk is specific and one-directional: a reader who assumes a number is sourced
will not question it, and these numbers are the difference between a site being
deprioritised and being *absent*. Saying "project default, not a published cutoff" costs
a line and removes the assumption.

This does not check that the values are *right* — nothing here can. It checks that each
one states what kind of number it is.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src" / "alleleforge"

#: Constants that gate a user-visible caveat, filter, or scope decision, and the module
#: they live in. Each must carry a provenance statement in the comment above it.
_JUDGEMENT_NUMBERS: tuple[tuple[str, str], ...] = (
    ("offtarget/engine.py", "DEFAULT_CFD_THRESHOLD"),
    ("offtarget/engine.py", "DEFAULT_MIT_THRESHOLD"),
    ("config.py", "DEFAULT_MAF_THRESHOLD"),
    ("design/spacer_quality.py", "GC_BAND"),
    ("design/offtarget_flags.py", "HIGH_SCORE_BAND"),
    ("design/prime.py", "CLOSE_NICK_NT"),
    ("scoring/uncertainty.py", "OOD_MIN_HALF_WIDTH"),
)

#: Phrases that count as stating what kind of number this is.
_PROVENANCE = (
    # Matched case-insensitively against the comment, and written in the singular so
    # a plural ("not published cutoffs") still matches.
    "not a published cutoff",
    "not a fitted threshold",
    "project default",
    "not published cutoff",
    "triage band",
    "deliberately conservative",
    "deliberately un-confident",
)


def _preceding_comment(source: str, name: str) -> str:
    """Return the `#:` comment block immediately above ``name``'s assignment."""
    match = re.search(rf"^{re.escape(name)}\s*[:=]", source, re.M)
    assert match, f"{name} not found"
    lines = source[: match.start()].splitlines()
    block: list[str] = []
    for line in reversed(lines):
        if line.startswith("#:") or (block and line.startswith("#")):
            block.append(line)
        elif not line.strip():
            continue
        else:
            break
    return " ".join(reversed(block))


@pytest.mark.parametrize(("module", "name"), _JUDGEMENT_NUMBERS, ids=lambda v: str(v))
def test_a_judgement_number_says_what_kind_of_number_it_is(module: str, name: str) -> None:
    comment = _preceding_comment((_SRC / module).read_text(), name)
    assert comment, f"{name} in {module} has no explanatory comment at all"
    lowered = comment.lower()
    assert any(phrase in lowered for phrase in _PROVENANCE), (
        f"{name} in {module} gates what a user sees and does not say what kind of "
        f"number it is. Say whether it is published or chosen. Comment: {comment[:160]}"
    )


def test_the_listed_constants_all_exist() -> None:
    """An entry that no longer names a real constant is a check watching nothing."""
    for module, name in _JUDGEMENT_NUMBERS:
        source = (_SRC / module).read_text()
        assert re.search(rf"^{re.escape(name)}\s*[:=]", source, re.M), f"{name} is gone"
