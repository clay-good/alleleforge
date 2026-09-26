"""Every range validator, measured at the value it is supposed to admit.

Mutation sweeps over `types/guide.py` and `types/variant.py` left survivors that were all
the same shape: a strict comparison in a validator relaxed by one — `>` to `>=`, `<` to
`<=`. Each such mutation makes the validator reject the boundary value itself, and every
one survived, because the tests reached for the value *past* the boundary and never for
the boundary.

That asymmetry is the point. A validator is tested by feeding it something illegal and
watching it raise, which is the satisfying half to write; the half that matters to a user
is the legal input at the edge, and refusing it is a harder failure to diagnose than
accepting one too many — the input is correct, the error names a rule it does not break,
and nothing upstream produced it, so there is nobody to ask.

These models are public and carry published JSON schemas, so the inputs here are the ones
a caller constructs or deserializes rather than ones the enumerators emit. That is exactly
why the boundary needs stating: `BaseEditWindow`'s own comment says "the pipeline never
produces such a window, but a hand-built or deserialized one can", and a pipeline that
cannot reach a case cannot defend it either.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alleleforge.types.guide import PAM, BaseEditWindow, PegRNA, Spacer
from alleleforge.types.sequence import DNASequence
from alleleforge.types.variant import Variant

_SPACER_LEN = 20


def _spacer() -> Spacer:
    return Spacer(sequence=DNASequence("A" * _SPACER_LEN))


def _window(**kw: object) -> BaseEditWindow:
    base: dict[str, object] = {
        "spacer": _spacer(),
        "editor": "ABE8e",
        "window": (1, _SPACER_LEN),
        "target_positions": (1,),
        "pam": PAM(pattern="NGG"),
    }
    base.update(kw)
    return BaseEditWindow(**base)  # type: ignore[arg-type]


def _pegrna(*, h5: int, h3: int, rtt: int = 16) -> PegRNA:
    return PegRNA(
        spacer=_spacer(),
        scaffold=DNASequence("GTTTAGAGCTAGAAATAGCAAG"),
        rtt=DNASequence("A" * rtt),
        pbs=DNASequence("A" * 12),
        rtt_homology_5prime=h5,
        rtt_homology_3prime=h3,
    )


# -- base-edit window positions ------------------------------------------------


def test_an_edit_position_at_either_end_of_the_spacer_is_legal() -> None:
    """`position < 1 or position > len(spacer)` must admit 1 and `len(spacer)`.

    Position 1 is the PAM-distal base and `len(spacer)` the PAM-proximal one; both are
    inside every editor's reach at some window. Relaxing either comparison rejects a
    guide the enumerator is entitled to build.
    """
    assert _window(target_positions=(1,)).target_positions == (1,)
    assert _window(target_positions=(_SPACER_LEN,)).target_positions == (_SPACER_LEN,)


@pytest.mark.parametrize("position", [0, _SPACER_LEN + 1])
def test_an_edit_position_off_the_spacer_is_refused(position: int) -> None:
    """The other side of the same check, so the pair states a range rather than a floor."""
    with pytest.raises(ValidationError, match="outside spacer"):
        _window(target_positions=(position,))


def test_a_bystander_position_is_held_to_the_same_range() -> None:
    """Both position tuples go through one check; neither may be the only one tested."""
    assert _window(target_positions=(1,), bystander_positions=(_SPACER_LEN,))
    with pytest.raises(ValidationError, match="outside spacer"):
        _window(target_positions=(1,), bystander_positions=(_SPACER_LEN + 1,))


def test_a_single_position_activity_window_is_legal() -> None:
    """`end < start` rejects a reversed window, not a one-base one.

    Relaxed to `end <= start`, an editor with a one-position window cannot be described
    at all — and the window is a per-editor datum the registry is meant to make a data
    change.
    """
    assert _window(window=(4, 4), target_positions=(4,)).window == (4, 4)


def test_a_reversed_or_sub_one_window_is_refused() -> None:
    with pytest.raises(ValidationError, match="invalid window"):
        _window(window=(8, 4), target_positions=(4,))
    with pytest.raises(ValidationError, match="invalid window"):
        _window(window=(0, 8), target_positions=(4,))


# -- pegRNA homology arms ------------------------------------------------------


def test_homology_arms_may_exactly_fill_the_rtt() -> None:
    """The RTT is 5' homology + templated allele + 3' homology.

    A templated allele of zero length — a pure deletion — makes the two arms sum to the
    whole RTT, so `5' + 3' == len(rtt)` is the legal extreme, not an overrun. Relaxing
    `>` to `>=` refuses it, and refuses the all-3'-homology form with it.
    """
    assert _pegrna(h5=6, h3=10).rtt_homology_5prime == 6
    assert _pegrna(h5=0, h3=16).rtt_homology_3prime == 16


def test_homology_arms_one_base_over_the_rtt_are_refused() -> None:
    with pytest.raises(ValidationError, match="exceed RTT length"):
        _pegrna(h5=7, h3=10)


def test_three_prime_homology_may_equal_the_whole_rtt() -> None:
    """`rtt_homology_3prime > rtt_len` is the overrun check, so equality is admissible."""
    assert _pegrna(h5=0, h3=16).rtt_homology_3prime == 16
    with pytest.raises(ValidationError, match="exceeds RTT length"):
        _pegrna(h5=0, h3=17)


# -- variant normalization -----------------------------------------------------


@pytest.mark.parametrize(
    ("ref", "alt"),
    [
        # Asymmetric, one allele already at the floor. These are the cases that
        # distinguish the two guards: each loop tests `len(ref) > 1 and len(alt) > 1`,
        # and relaxing *one* of them still leaves the other to stop the loop whenever
        # the alleles are the same length. A symmetric pair therefore cannot tell a
        # single relaxed guard from none — so an insertion whose ref is one base
        # (`T>GT`) normalizes to an **empty ref**, while `AT>AT` looks untouched.
        ("T", "GT"),  # insertion; suffix loop, ref at the floor
        ("GT", "T"),  # deletion; suffix loop, alt at the floor
        ("A", "AG"),  # insertion; prefix loop, ref at the floor
        ("AG", "A"),  # deletion; prefix loop, alt at the floor
        # Symmetric, where both guards would have to go at once.
        ("AT", "AT"),
        ("GCGC", "GCGC"),
        ("A", "A"),
    ],
)
def test_normalization_never_empties_an_allele(ref: str, alt: str) -> None:
    """Both trim loops stop at one base: `len(ref) > 1 and len(alt) > 1`.

    Relaxed, a loop trims an allele to the empty string — a variant with no ref, or no
    alt, which is not a variant. The loops are guarded rather than the result, so the
    boundary is the only place the guard is visible.
    """
    normalized = Variant(chrom="chr1", pos=100, ref=ref, alt=alt).normalized()
    assert normalized.ref, f"{ref}>{alt} normalized to an empty ref"
    assert normalized.alt, f"{ref}>{alt} normalized to an empty alt"


@pytest.mark.parametrize(("ref", "alt"), [("T", "GT"), ("GT", "T"), ("A", "AG"), ("AG", "A")])
def test_an_allele_already_at_the_floor_is_left_alone(ref: str, alt: str) -> None:
    """Stronger than non-empty: neither loop may run at all when one allele is one base.

    There is nothing to trim that would not empty something, so the variant must come
    back exactly as it went in — position included, since the prefix loop advances it.
    """
    normalized = Variant(chrom="chr1", pos=100, ref=ref, alt=alt).normalized()
    assert (normalized.ref, normalized.alt, normalized.pos) == (ref, alt, 100)


def test_normalization_still_trims_what_it_should() -> None:
    """The positive case, so the guard above is not satisfied by never trimming."""
    assert Variant(chrom="chr1", pos=100, ref="AT", alt="GT").normalized().ref == "A"
    trimmed = Variant(chrom="chr1", pos=100, ref="GA", alt="GT").normalized()
    assert (trimmed.ref, trimmed.alt, trimmed.pos) == ("A", "T", 101)
