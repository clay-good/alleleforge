"""Shared rejection accounting for the enumerators.

An enumerator that returns nothing knows why — the reasons are sitting in its
``continue`` statements, discarded one branch at a time. Reporting "no actionable
candidate" and stopping collapses next steps that differ: *no PAM in range* means try
another PAM or chemistry, *the target base is outside the activity window* means try a
different editor, *no editor installs this substitution* means the chemistry is simply
wrong for the edit.

Each enumerator owns its own reason labels, in the words a user needs; this module owns
only the tallying and the rendering, so the three do not drift into three spellings of
the same sentence.

The tally is opt-in throughout. Anything added inside an enumeration loop costs per
call, and a caller that does not want a diagnosis pays a single ``is not None``.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping


def note(tally: MutableMapping[str, int] | None, reason: str) -> None:
    """Record one rejection, when a caller asked for the tally."""
    if tally is not None:
        tally[reason] = tally.get(reason, 0) + 1


def summarize(tally: Mapping[str, int], reasons: Mapping[str, str]) -> str:
    """Render a rejection tally as one sentence, most common reason first.

    Unknown keys are dropped rather than printed raw: a label with no sentence behind
    it is not something to show a reader, and its absence is caught by the test that
    pins every enumerator's `continue` against its reason table.
    """
    counted = [(n, key) for key, n in tally.items() if n and key in reasons]
    if not counted:
        return "no candidate was examined"
    counted.sort(key=lambda pair: (-pair[0], pair[1]))
    return "; ".join(f"{reasons[key]} ({n})" for n, key in counted)
