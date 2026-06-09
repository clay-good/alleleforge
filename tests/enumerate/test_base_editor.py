"""Tests for base-editor enumeration and the declarative registry."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.enumerate.base_editor import (
    BASE_EDITORS,
    enumerate_base_edits,
)
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
PAD = "T" * 20


def _resolve(ref: ReferenceGenome, zero_based: int, alt: str) -> ResolvedVariant:
    base = str(
        ref.fetch(
            GenomicInterval(chrom="chr2", start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"chr2:{zero_based + 1}:{base}>{alt}", reference=ref)


# -- registry -----------------------------------------------------------------


def test_registry_seeded_editors() -> None:
    names = {e.name for e in BASE_EDITORS}
    assert names == {"ABE8e", "CBE4max", "evoCDA1"}
    abe = next(e for e in BASE_EDITORS if e.name == "ABE8e")
    assert abe.chemistry is Chemistry.BASE_ABE
    assert (abe.target_base, abe.result_base) == ("A", "G")


def test_editor_installs_strand_logic() -> None:
    abe = next(e for e in BASE_EDITORS if e.name == "ABE8e")
    assert abe.installs("A", "G") is Strand.PLUS  # plus A->G
    assert abe.installs("T", "C") is Strand.MINUS  # minus edit gives plus T->C
    assert abe.installs("C", "T") is None  # transversion / wrong chemistry
    cbe = next(e for e in BASE_EDITORS if e.name == "CBE4max")
    assert cbe.installs("C", "T") is Strand.PLUS
    assert cbe.installs("G", "A") is Strand.MINUS


# -- enumeration --------------------------------------------------------------


def test_empty_editors_returns_empty_not_crash(make_reference: MakeRef) -> None:
    # The margin computation max()es over the editors' PAM lengths; with no
    # editors it must degrade to an empty result, not raise on an empty max().
    proto = "TTTTAACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    assert enumerate_base_edits(rv, reference=ref, intent=EditIntent.INSTALL, editors=()) == []


def test_abe_plus_enumeration(make_reference: MakeRef) -> None:
    proto = "TTTTAACGTTTTTTTTTTTT"  # editable A's at protospacer positions 5 and 6
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")  # target A at genomic 25 (proto idx5 -> position 6)
    windows = enumerate_base_edits(rv, reference=ref, intent=EditIntent.INSTALL)
    abe = [w for w in windows if w.editor == "ABE8e"]
    assert abe
    w = abe[0]
    assert w.placement is not None and w.placement.strand is Strand.PLUS
    assert w.target_positions == (6,)
    assert 5 in w.bystander_positions  # the neighboring in-window A is a bystander
    assert w.window_bases == str(w.spacer.sequence)[3:8]


def test_cbe_enumeration(make_reference: MakeRef) -> None:
    proto = "TTTTCACGTTTTTTTTTTTT"  # editable C at position 5
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 24, "T")  # C->T (INSTALL)
    windows = enumerate_base_edits(rv, reference=ref, intent=EditIntent.INSTALL)
    cbe = [w for w in windows if w.editor in ("CBE4max", "evoCDA1")]
    assert cbe
    assert all(w.placement is not None for w in cbe)
    assert not any(w.editor == "ABE8e" for w in windows)  # ABE cannot do C->T


def test_correct_intent_edits_alt_to_ref(make_reference: MakeRef) -> None:
    # Reference carries T; the variant (alt=C) is corrected back to T by a CBE.
    proto = "TTTTTACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 24, "C")  # ref=T, alt=C; correct => C->T
    windows = enumerate_base_edits(rv, reference=ref, intent=EditIntent.CORRECT)
    cbe = [w for w in windows if w.editor in ("CBE4max", "evoCDA1")]
    assert cbe
    # the spacer carries the alt (C) at the target, since that is what gets edited
    w = cbe[0]
    assert str(w.spacer.sequence)[w.target_positions[0] - 1] == "C"


def test_minus_strand_abe(make_reference: MakeRef) -> None:
    from alleleforge.types.sequence import DNASequence

    proto = "TTTTAACGTTTTTTTTTTTT"
    rc = str(DNASequence(proto).reverse_complement())
    ref = make_reference({"chr2": PAD + "CCA" + rc + PAD})
    # the editable A sits on the minus strand; on plus it reads as a T
    target = 20 + 3 + (len(proto) - 1 - 5)  # proto idx5 -> rc index, genomic plus coord
    rv = _resolve(ref, target, "C")  # plus T->C (ABE minus)
    windows = enumerate_base_edits(rv, reference=ref, intent=EditIntent.INSTALL)
    assert any(w.editor == "ABE8e" and w.placement.strand is Strand.MINUS for w in windows)


def test_transversion_not_base_editable(make_reference: MakeRef) -> None:
    proto = "TTTTAACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 25, "C")  # A->C is a transversion: no editor applies
    assert enumerate_base_edits(rv, reference=ref, intent=EditIntent.INSTALL) == []


def test_non_snv_not_base_editable(make_reference: MakeRef) -> None:
    proto = "TTTTAACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = resolve("chr2:26:AA>A", reference=ref)  # a deletion (non-SNV)
    assert enumerate_base_edits(rv, reference=ref, intent=EditIntent.CORRECT) == []


def test_window_override(make_reference: MakeRef) -> None:
    proto = "TTTTAACGTTTTTTTTTTTT"
    ref = make_reference({"chr2": PAD + proto + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    custom = next(e for e in BASE_EDITORS if e.name == "ABE8e")
    windows = enumerate_base_edits(
        rv, reference=ref, intent=EditIntent.INSTALL, editors=(custom,), window=(1, 10)
    )
    assert all(w.window == (1, 10) for w in windows)
