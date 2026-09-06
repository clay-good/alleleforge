"""Outcome caveats shared by every chemistry.

`P(intended)` is the number a reader is actually deciding on — of everything this
reagent produces, how much is the edit that was asked for — and it had no caveat at
any value. A real report printed `P(intended) = 0.05` beside an outcome table whose
most likely row was a bystander-only edit at 0.288, and the CAVEATS block, which is
what a reader scans for what should worry them, said nothing about it.

The flag here is deliberately **not** a threshold. "Low" would need a number nobody
can defend, and the honest statement is a comparison the data already makes: whether
the single most likely outcome is the requested edit. When it is not, that is a fact
about the reagent, not a judgement about how small a probability is too small — and it
is the fact a bench scientist needs before ordering oligos.
"""

from __future__ import annotations

from alleleforge.types.edit import EditOutcome


def outcome_flags(outcome: EditOutcome | None) -> list[str]:
    """Return the outcome caveats for one candidate's predicted allele distribution.

    Args:
        outcome: The predicted outcome distribution, or ``None`` when none was
            predicted.

    Returns:
        ``["intended-not-modal:<p>"]`` when an intended allele exists and some other
        allele is more likely, carrying `P(intended)` so the reader sees the size of
        the gap. Empty otherwise — including when no allele is marked intended at all,
        which is the NHEJ-spectrum case that already has its own flag.
    """
    if outcome is None or not outcome.alleles:
        return []
    intended = [a for a in outcome.alleles if a.is_intended]
    if not intended:
        return []
    modal = max(outcome.alleles, key=lambda a: a.probability)
    if modal.is_intended:
        return []
    return [f"intended-not-modal:{outcome.p_intended:.2f}"]
