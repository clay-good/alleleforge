"""The guard that stops a scorer being handed a frame-shifted window.

`guide_context` deliberately locates the guide's protospacer+PAM *by content* rather
than by arithmetic on its recorded placement. Its own docstring says why: "a
length-changing overlay shifts everything 3' of the edit, so slicing fixed offsets
around a reference placement would hand the scorer a frame-shifted context — silently,
and of the wrong length."

The refusal is what makes that anchoring honest. `plus.find(anchor)` returns `-1` when
the reagent is not in the carried sequence, and `-1` is a *legal* slice index in Python.
Delete the raise and the next line runs as

    plus[max(0, -1 - low_pad) : -1 + len(anchor) + high_pad]

which returns a window — a real string, of plausible length, starting in the wrong
place. That is precisely the frame-shifted context the by-content anchoring exists to
prevent, reintroduced by the deletion of the one line that reports the anchoring failed.
Nothing downstream can detect it: an efficiency model given a shifted 30-mer returns a
number, not an error, and that number reaches a candidate's score and the menu.

This module could not be measured before R689's no-op control was in place: the package
list contains `test_the_cas9_defaults_and_donor_promises.py`, which reads this module's
source text, so every mutant died on reformatting and `cas9.py` scored a meaningless
100%. With that file excluded this was the sole `raise` site, and it survived.

Found by deleting the refusal (`scripts/mutate.py --mode raise`).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alleleforge.enumerate.cas9 import enumerate_cas9, guide_context
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import Guide
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

#: A second contig whose sequence shares no 23-mer with the one the guide comes from.
_OTHER = "ACACACACACACACACACACACACACACACACACACACACACACACACACACACACACACACAC"


def _resolve_at(ref: ReferenceGenome, contig: str, zero_based: int) -> ResolvedVariant:
    """Resolve a synthetic SNV at ``zero_based`` whose ref matches the build."""
    base = str(
        ref.fetch(
            GenomicInterval(chrom=contig, start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"{contig}:{zero_based + 1}:{base}>G", reference=ref)


def _a_guide(reference: ReferenceGenome) -> Guide:
    rv = _resolve_at(reference, "chr2", 32)
    return next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=reference)
        if str(g.spacer.sequence) == SPACER
    )


def test_a_guide_present_in_the_window_gets_its_context(make_reference: MakeRef) -> None:
    """The premise, and the case the guard must not fire on."""
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    context = guide_context(_a_guide(reference), reference, flank=6)
    assert SPACER + "TGG" in context
    assert len(context) == 20 + 3 + 12


def test_a_guide_absent_from_the_reference_being_scored_is_refused(
    make_reference: MakeRef,
) -> None:
    """A guide from one genome, scored against another, must not return a window.

    This is the realistic route in: a guide deserialized from a previous run, or one
    designed against a different build, handed to a scorer alongside today's reference.
    """
    designed_in = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    guide = _a_guide(designed_in)
    # Same contig name, no occurrence of the protospacer anywhere in it.
    scored_against = make_reference({"chr2": _OTHER * 4})

    with pytest.raises(ValueError, match="absent from the sequence being scored"):
        guide_context(guide, scored_against, flank=6)


def test_an_overlay_that_destroys_the_protospacer_is_refused(make_reference: MakeRef) -> None:
    """The overlay path, which is the one the by-content anchoring was written for.

    An overlay that rewrites bases inside the protospacer means the reagent is no longer
    in the sequence being scored. Refusing is the only honest answer: the guide as
    designed does not bind the sequence this window represents.
    """
    reference = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    guide = _a_guide(reference)
    spacer_start = len(PAD)
    # Replace the middle of the protospacer, so the 23-mer anchor cannot be found.
    original = SPACER[8:14]
    replacement = "".join("A" if base != "A" else "C" for base in original)
    assert replacement != original

    with pytest.raises(ValueError, match="absent from the sequence being scored"):
        guide_context(
            guide,
            reference,
            flank=6,
            overlay=(spacer_start + 8, original, replacement),
        )


def test_the_refusal_names_the_guide_it_could_not_place(make_reference: MakeRef) -> None:
    """A caller scoring many guides needs to know *which* one was not in the genome.

    `design_cas9` calls this inside a loop over a menu's candidates. A refusal that said
    only "absent from the sequence being scored" would leave the operator to work out
    which of twenty reagents the message was about.
    """
    designed_in = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    guide = _a_guide(designed_in)
    scored_against = make_reference({"chr2": _OTHER * 4})

    with pytest.raises(ValueError) as refused:
        guide_context(guide, scored_against, flank=6)
    assert SPACER in str(refused.value), (
        "the refusal does not name the spacer it failed to place, so a caller scoring a "
        "menu of guides cannot tell which reagent the message is about",
        str(refused.value),
    )


def test_a_minus_strand_window_is_anchored_by_content_too(make_reference: MakeRef) -> None:
    """Kept beside the refusals because the guard sits before the strand is resolved.

    The `find` happens on the plus strand and the reverse-complement happens after, so a
    refactor that moved the strand handling above the anchor lookup would make the guard
    unreachable for minus-strand guides while every test above still passed.
    """
    rc = str(DNASequence(SPACER).reverse_complement())
    reference = make_reference({"chr2": PAD + "CCA" + rc + PAD})
    rv = _resolve_at(reference, "chr2", 20)
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.KNOCK_OUT, reference=reference)
        if str(g.spacer.sequence) == SPACER and g.placement.strand is Strand.MINUS
    )
    assert SPACER in guide_context(guide, reference, flank=6)

    other = make_reference({"chr2": _OTHER * 4})
    with pytest.raises(ValueError, match="absent from the sequence being scored"):
        guide_context(guide, other, flank=6)


def test_the_guard_is_what_stands_between_find_and_a_shifted_slice() -> None:
    """Name the mechanism, so the guard is not read as defensive clutter.

    `-1` is a legal slice index, which is the entire reason this needs a test: the
    failure mode of deleting the raise is not an exception later, it is a window of
    plausible length starting in the wrong place. This pins the arithmetic so a reader
    can see that for themselves without reconstructing it.
    """
    anchor = SPACER + "TGG"
    low_pad, high_pad = 6, 6
    at = -1  # what `plus.find(anchor)` returns when the reagent is not there

    sequence = "N" * 200
    shifted = sequence[max(0, at - low_pad) : at + len(anchor) + high_pad]

    assert shifted, (
        "a `find` miss no longer yields a non-empty slice, so the deleted guard would "
        "fail loudly on its own; re-derive what the guard is protecting"
    )
    assert len(shifted) != len(anchor) + low_pad + high_pad, (
        "the shifted slice happens to be the right length, which would make the "
        "regression even harder to see downstream"
    )
