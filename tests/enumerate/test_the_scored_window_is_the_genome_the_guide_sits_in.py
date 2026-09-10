"""The efficiency model's window is measured against the genome, on both strands.

`guide_context` builds the sequence a Cas9 efficiency model reads. The trained Rule Set 3
scorer declares `context_flank = (4, 3)` — **asymmetric**, 4 nt 5' and 3 nt 3' of the
protospacer+PAM in the guide's own orientation — and on the minus strand the guide's 5'
flank lies at the *high* plus coordinates, so the two pads swap. Nothing measured that:

* the minus-strand test passed `flank=6`, symmetric, which cannot tell `f3, f5` from
  `f5, f3`;
* the asymmetric test ran on the plus strand and asserted the window's *length* and that
  it contains the protospacer, both of which a swap preserves.

Swapping the minus branch's two pads leaves the whole suite green — 4,211 tests — while
every minus-strand guide is scored on a window shifted one base at each end. That is the
frame-shifted scorer window this repository has met before, and it arrives with no
symptom: the run produces candidates, the ranking looks plausible, the numbers are wrong.

So the window is required to be, base for base, the genome the guide sits in.
"""

from __future__ import annotations

import pkgutil
from collections.abc import Callable
from importlib import import_module

import pytest

import alleleforge.scoring as scoring_pkg
from alleleforge.enumerate.cas9 import guide_context
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

MakeRef = Callable[[dict[str, str]], ReferenceGenome]

_SPACER = "GTCAGGGTTCTGGATATCTG"
_PAM = "TGG"
#: Distinctive on each side, so an assertion about the flanks is about *which* bases
#: they are and not only how many. No run of four repeats, so a window slid by one base
#: cannot land on the same string.
_LEFT = "ACCGTTAGCA"
_RIGHT = "GATTCCAGTA"


def _rc(seq: str) -> str:
    return str(DNASequence(seq).reverse_complement())


def _plus_contig() -> str:
    """A contig holding the same reagent on both strands, well clear of either end."""
    return _LEFT + _SPACER + _PAM + "CCC" + _rc(_SPACER) + _RIGHT


#: Where each guide sits in `_plus_contig()`. The plus guide's protospacer is at the low
#: end with its PAM above it; the minus guide reads the other way, its PAM (`CCA` on the
#: plus strand, `TGG` read on the minus) below its protospacer.
_PLUS_PROTO = len(_LEFT)
_MINUS_PAM = len(_LEFT) + len(_SPACER) + len(_PAM)  # the "CCC" reading as CCA-like NGG
_MINUS_PROTO = _MINUS_PAM + 3


def _guide(strand: Strand, contig: str) -> Guide:
    start = _PLUS_PROTO if strand is Strand.PLUS else _MINUS_PROTO
    pam_start = start + len(_SPACER) if strand is Strand.PLUS else start - 3
    pam_plus = contig[pam_start : pam_start + 3]
    return Guide(
        spacer=Spacer(sequence=DNASequence(_SPACER)),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence(pam_plus if strand is Strand.PLUS else _rc(pam_plus)),
        placement=GenomicInterval(
            chrom="chr2", start=start, end=start + len(_SPACER), strand=strand
        ),
        cut_site=start + 17 if strand is Strand.PLUS else start + 2,
    )


@pytest.fixture
def reference(make_reference: MakeRef) -> ReferenceGenome:
    return make_reference({"chr2": _plus_contig()})


def test_the_fixture_holds_the_reagent_on_both_strands(reference: ReferenceGenome) -> None:
    """A fixture whose minus guide is not really there would make the sweep vacuous."""
    contig = _plus_contig()
    assert contig[_PLUS_PROTO : _PLUS_PROTO + len(_SPACER)] == _SPACER
    assert _rc(contig[_MINUS_PROTO : _MINUS_PROTO + len(_SPACER)]) == _SPACER
    assert _rc(contig[_MINUS_PAM : _MINUS_PAM + 3]).endswith("GG")


@pytest.mark.parametrize("strand", [Strand.PLUS, Strand.MINUS])
@pytest.mark.parametrize(("f5", "f3"), [(4, 3), (3, 4), (6, 6), (0, 5)])
def test_the_window_is_the_guides_own_neighbourhood(
    strand: Strand, f5: int, f3: int, reference: ReferenceGenome
) -> None:
    """Base for base: the 5' pad is the guide's 5' neighbours, in its own orientation.

    Both orders of the asymmetric pair are swept, because a window built with the pads
    exchanged is still the right length and still contains the protospacer — the two
    things the previous tests checked.
    """
    contig = _plus_contig()
    guide = _guide(strand, contig)
    context = guide_context(guide, reference, flank_5=f5, flank_3=f3)

    reagent = _SPACER + str(guide.pam_sequence)
    if strand is Strand.PLUS:
        lo = _PLUS_PROTO
        hi = _PLUS_PROTO + len(_SPACER) + 3
        expected = contig[lo - f5 : lo] + reagent + contig[hi : hi + f3]
    else:
        # The minus guide reads down the plus strand: its 5' flank is the plus bases
        # *above* its protospacer, reverse-complemented, and its 3' flank the plus
        # bases below its PAM.
        proto_end = _MINUS_PROTO + len(_SPACER)
        expected = (
            _rc(contig[proto_end : proto_end + f5])
            + reagent
            + _rc(contig[_MINUS_PAM - f3 : _MINUS_PAM])
        )

    assert context == expected
    assert len(context) == f5 + len(_SPACER) + 3 + f3


def _scorers_declaring_a_window() -> list[tuple[str, tuple[int, int]]]:
    """Every scorer that declares an asymmetric window, from the scoring package.

    Derived rather than listed: the asymmetric path exists *because* a model declared
    `context_flank`, and the next model to declare one is the next one whose minus-strand
    window nobody checked.
    """
    found: list[tuple[str, tuple[int, int]]] = []
    for info in pkgutil.iter_modules(scoring_pkg.__path__):
        module = import_module(f"{scoring_pkg.__name__}.{info.name}")
        for name in dir(module):
            attribute = getattr(module, name)
            flank = getattr(attribute, "context_flank", None)
            if isinstance(flank, tuple) and len(flank) == 2 and isinstance(attribute, type):
                found.append((f"{info.name}.{name}", flank))
    return sorted(set(found))


def test_a_declared_window_is_found() -> None:
    """Rule Set 3 declares (4, 3); a derivation that found none would be vacuous."""
    declared = _scorers_declaring_a_window()
    assert declared, "no scorer declares context_flank; the sweep below covers nothing"
    assert any(flank == (4, 3) for _, flank in declared), declared


@pytest.mark.parametrize("strand", [Strand.PLUS, Strand.MINUS])
def test_every_declared_window_is_served_on_both_strands(
    strand: Strand, reference: ReferenceGenome
) -> None:
    """The window a model says it reads is the window it is handed, on either strand."""
    contig = _plus_contig()
    guide = _guide(strand, contig)
    for name, (f5, f3) in _scorers_declaring_a_window():
        context = guide_context(guide, reference, flank_5=f5, flank_3=f3)
        assert len(context) == f5 + len(_SPACER) + 3 + f3, name
        # The reagent sits at exactly the declared offset, which is what a model that
        # indexes into the window by position depends on.
        assert context[f5 : f5 + len(_SPACER)] == _SPACER, name


def test_a_carried_allele_inside_the_window_is_read_on_the_minus_strand(
    reference: ReferenceGenome,
) -> None:
    """The overlay path, on the strand where the flank arithmetic is the tricky one.

    A precise intent scores against the genome the target *carries*, so a variant one
    base outside the protospacer must appear in the window — reverse-complemented.
    """
    contig = _plus_contig()
    guide = _guide(Strand.MINUS, contig)
    proto_end = _MINUS_PROTO + len(_SPACER)
    ref_base = contig[proto_end]
    allele = "A" if ref_base != "A" else "C"
    context = guide_context(
        guide, reference, flank_5=4, flank_3=3, overlay=(proto_end, ref_base, allele)
    )
    carried = contig[:proto_end] + allele + contig[proto_end + 1 :]
    assert context == (
        _rc(carried[proto_end : proto_end + 4])
        + _SPACER
        + str(guide.pam_sequence)
        + _rc(carried[_MINUS_PAM - 3 : _MINUS_PAM])
    )
    # And the carried base really is the one that moved: the reference window differs.
    assert context != guide_context(guide, reference, flank_5=4, flank_3=3)
