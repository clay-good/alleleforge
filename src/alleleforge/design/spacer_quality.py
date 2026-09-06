"""Spacer quality caveats shared by every chemistry.

These are properties of an sgRNA spacer as a *transcribed reagent*, not of the
chemistry that uses it: a U6-driven spacer with 5% GC transcribes and synthesizes
badly whether it sits in a pegRNA, an ABE sgRNA, or a nuclease sgRNA. The checks
lived in the prime vertical only, so an identical problem was flagged on one
chemistry and reported ``clean`` on the other two — and a base-editor candidate with
a 5% GC spacer came back top-ranked, `recommended`, with no caveat at all.
"""

from __future__ import annotations

#: Spacer GC band (Pol III): outside it, U6 transcription and synthesis suffer, so
#: the spacer is annotated (not dropped) as an inspectable quality caveat.
#:
#: **A project default, not a published cutoff.** The direction is well established —
#: very low and very high GC spacers transcribe and synthesize worse — but the exact
#: edges are a convention, and a spacer at 0.29 is not meaningfully different from one
#: at 0.31. That is why crossing the band annotates rather than filters, and why the
#: flag carries the measured GC so a reader judges the margin rather than the verdict.
GC_BAND = (0.30, 0.80)


def spacer_quality_flags(spacer: str) -> list[str]:
    """Return Pol III transcription caveats for ``spacer``.

    Args:
        spacer: The spacer sequence, 5'->3'.

    Returns:
        Flags in a stable order: a missing U6-start G, then an out-of-band GC
        fraction carrying its value. Empty for a spacer with neither problem, so the
        annotation means something when it appears.
    """
    sequence = spacer.upper()
    if not sequence:
        return []
    flags: list[str] = []
    if not sequence.startswith("G"):
        flags.append("no-5prime-g")
    gc = sum(base in "GC" for base in sequence) / len(sequence)
    if not GC_BAND[0] <= gc <= GC_BAND[1]:
        flags.append(f"gc-out-of-band:{gc:.2f}")
    return flags
