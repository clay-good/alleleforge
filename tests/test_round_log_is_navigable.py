"""The audit log must be readable in the order the audit happened.

`openspec/changes/README.md` is the project's audit history, and later rounds cite
earlier ones by number constantly ("R117's lesson", "the cap added in R49/R50"). Two
defects made those citations unfollowable, both introduced by the rounds themselves:

* Rounds 1–134 ran in ascending order and 135–145 in **descending** order, because a
  stretch of rounds each prepended its entry ahead of the previous one instead of
  appending. The log read chronologically and then reversed.
* Two numbers (50, 71) had shipped work and citations but no entry at all.

Nothing checked either. These pin the two mechanical properties a numbered log needs:
the numbers ascend, and a cited number resolves to something.
"""

from __future__ import annotations

import re
from pathlib import Path

_LOG = Path(__file__).resolve().parents[1] / "openspec" / "changes" / "README.md"

#: Round numbers deliberately absent, each with the reason a reader needs. A gap may
#: only live here with an explanation, so this cannot become a place to lose an entry.
_SKIPPED: dict[int, str] = {
    117: "number skipped; the work is logged under Round 116, noted in the R118 entry",
}


def _round_numbers() -> list[int]:
    """Return the round numbers in the order they appear in the log."""
    return [int(m) for m in re.findall(r"^## Round (\d+)", _LOG.read_text(), re.M)]


def test_rounds_appear_in_ascending_order() -> None:
    numbers = _round_numbers()
    assert len(numbers) > 100, "no round entries found — this check would be vacuous"
    out_of_order = [(a, b) for a, b in zip(numbers, numbers[1:], strict=False) if b <= a]
    assert not out_of_order, (
        "round entries are not in ascending order; append a new round after the last "
        f"one rather than prepending it. Offending adjacent pairs: {out_of_order}"
    )


def test_every_round_number_in_the_range_resolves() -> None:
    """A cited round must lead somewhere — to an entry, or to a recorded reason."""
    numbers = set(_round_numbers())
    missing = sorted(set(range(min(numbers), max(numbers) + 1)) - numbers - set(_SKIPPED))
    assert not missing, (
        f"round numbers with no entry: {missing}. Write the entry, or record the number "
        "in _SKIPPED with the reason a reader following a citation needs."
    )


def test_documented_skips_are_really_absent() -> None:
    """Guard the guard: an allowance must not outlive the gap it excuses."""
    numbers = set(_round_numbers())
    stale = sorted(n for n in _SKIPPED if n in numbers)
    assert not stale, f"_SKIPPED lists rounds that now have entries: {stale}"


def test_every_round_cited_in_the_conventions_exists() -> None:
    """`project.md` distils the log into rules, and each rule cites its round.

    A citation is the only path from a one-paragraph rule back to the evidence for it,
    so a dangling `R<n>` costs a reader the reason the rule exists. Round 117 is the
    live case: it is cited by two entries and is not a round.
    """
    conventions = _LOG.parent.parent / "project.md"
    cited = {int(n) for n in re.findall(r"\bR(\d{1,3})\b", conventions.read_text())}
    assert cited, "no round citations found in project.md — this check would be vacuous"
    known = set(_round_numbers())
    # `R0`–`R5` in that file also name the post-v0.1.0 roadmap tracks, so numbers below
    # the log's first round are not read as citations. Everything at or above it is —
    # including a number past the last round, which is the typo this most needs to
    # catch. A documented skip resolves: a reader following it lands on the note saying
    # where that work is logged instead.
    dangling = sorted(n for n in cited if n >= min(known) and n not in known and n not in _SKIPPED)
    assert not dangling, (
        f"project.md cites rounds with no entry in the log: {dangling}. Write the entry, "
        f"or record the number in _SKIPPED with its reason. Documented skips: {_SKIPPED}"
    )
