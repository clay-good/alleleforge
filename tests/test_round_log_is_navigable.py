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
