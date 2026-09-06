"""Off-target caveats shared by every chemistry.

A guide's off-target risk is a property of its spacer against the genome, not of the
chemistry that carries it, and the three verticals had drifted into flagging it three
different ways: cas9 and the base editor emitted ``population-offtarget``, prime did
not, and **none of them flagged a high-scoring site at all**.

That last gap is the one that matters. The numbers were always there — a report prints
``off-target sites: 2 (specificity 0.376)`` — but the CAVEATS block, which is what a
reader scans for *what should worry me*, listed spacer GC and bystander bases while
saying nothing about a site elsewhere in the genome scoring 1.000. A perfect match
somewhere else is the most alarming thing a guide can have, and it was the one hazard
with no label. The ranking consumed it (the safety objective drops to 0.00), so a
guide like that sinks in a full menu — and is still returned `recommended` when it is
the only candidate, with no caveat naming why it should not be trusted.
"""

from __future__ import annotations

from alleleforge.types.offtarget import OffTargetReport

#: Single-site score at or above which a nominated off-target is called out by name.
#: A **triage band, not a published cutoff**: CFD is a continuous estimate and no
#: threshold separates "safe" from "unsafe". It is set where a site stops being one of
#: many weak nominations and becomes the thing a bench scientist would validate first,
#: and the flag carries the actual score so the reader judges rather than trusting the
#: band. Sites below it are still counted, scored, and reported — they simply do not
#: raise a caveat of their own.
HIGH_SCORE_BAND = 0.5


def offtarget_flags(report: OffTargetReport | None) -> list[str]:
    """Return the off-target caveats for one candidate's search result.

    Args:
        report: The candidate's off-target report, or ``None`` when no search ran.

    Returns:
        Flags, in a fixed order: whether a search happened at all, whether any
        nominated site is high-scoring (with its score), and whether population
        variation contributed sites.
    """
    if report is None:
        return ["offtarget-not-searched"]
    flags: list[str] = []
    worst = report.worst_score()
    if worst >= HIGH_SCORE_BAND:
        flags.append(f"offtarget-high:{worst:.2f}")
    if report.population_sites:
        flags.append("population-offtarget")
    return flags
