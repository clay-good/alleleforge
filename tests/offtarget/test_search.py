"""Tests for PAM-anchored, mismatch- and bulge-tolerant search."""

from __future__ import annotations

from alleleforge.offtarget._search import scan_sequence
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import DNASequence, Strand

SP = "GACCATGCAACCTTGAACGT"
PAD = "T" * 10
NRG = PAM(pattern="NRG")


def _scan(seq: str, *, mm: int = 4, dnab: int = 1, rnab: int = 1) -> list:
    return scan_sequence("chr2", seq, SP, NRG, mismatches=mm, dna_bulges=dnab, rna_bulges=rnab)


def _sub(seq: str, pos: int, base: str) -> str:
    return seq[:pos] + base + seq[pos + 1 :]


def test_exact_plus_hit() -> None:
    hits = _scan(PAD + SP + "TGG" + PAD)
    plus = [h for h in hits if h.strand is Strand.PLUS and h.mismatches == 0]
    assert len(plus) == 1
    h = plus[0]
    assert (h.start, h.end) == (10, 30)
    assert h.pam_sequence == "TGG"
    assert h.aligned_spacer == SP and h.aligned_target == SP


def test_two_mismatch_hit() -> None:
    mut = _sub(_sub(SP, 2, "A"), 15, "C")  # SP[2]='C'->A, SP[15]='A'->C
    hits = _scan(PAD + mut + "TGG" + PAD)
    plus = [h for h in hits if h.strand is Strand.PLUS]
    assert plus and plus[0].mismatches == 2


def test_mismatch_budget_excludes_distant_sites() -> None:
    mut = "".join("A" if i % 2 else b for i, b in enumerate(SP))  # ~10 mismatches
    hits = _scan(PAD + mut + "TGG" + PAD, mm=4)
    assert all(h.mismatches <= 4 for h in hits)
    assert not any((h.start, h.end) == (10, 30) and h.strand is Strand.PLUS for h in hits)


def test_minus_strand_hit() -> None:
    rc = str(DNASequence(SP).reverse_complement())
    hits = _scan(PAD + "CCA" + rc + PAD)  # minus-strand protospacer + revcomp(TGG)
    minus = [h for h in hits if h.strand is Strand.MINUS and h.mismatches == 0]
    assert minus and minus[0].pam_sequence.endswith("GG")
    assert minus[0].aligned_target == SP


def test_dna_bulge_hit() -> None:
    proto = SP[:10] + "A" + SP[10:]  # 21-nt target with one extra base
    hits = _scan(PAD + proto + "TGG" + PAD, rnab=0)
    bulged = [h for h in hits if h.dna_bulges == 1]
    assert bulged and bulged[0].mismatches == 0
    assert len(bulged[0].aligned_target) == len(SP)


def test_rna_bulge_hit() -> None:
    proto = SP[:10] + SP[11:]  # 19-nt target (one spacer base unpaired)
    hits = _scan(PAD + proto + "TGG" + PAD, dnab=0)
    bulged = [h for h in hits if h.rna_bulges == 1]
    assert bulged and bulged[0].mismatches == 0
    assert len(bulged[0].aligned_spacer) == len(SP) - 1


def test_padded_n_region_is_skipped() -> None:
    seq = PAD + SP[:10] + "N" + SP[11:] + "TGG" + PAD  # an N inside the protospacer
    hits = _scan(seq)
    assert not any((h.start, h.end) == (10, 30) and h.strand is Strand.PLUS for h in hits)


def test_no_pam_no_hit() -> None:
    hits = _scan(PAD + SP + "CAT" + PAD)  # CAT is not NRG
    assert not any(h.mismatches == 0 and h.strand is Strand.PLUS for h in hits)
