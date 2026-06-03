"""Tests for guide, PAM, base-edit window, and pegRNA structural models."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from alleleforge.types.guide import (
    PAM,
    BaseEditWindow,
    Guide,
    NickingGuide,
    PegRNA,
    Spacer,
    ThreePrimeMotif,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand


def _spacer(n: int = 20) -> Spacer:
    return Spacer(sequence=DNASequence("A" * n))


def _interval(n: int = 20) -> GenomicInterval:
    return GenomicInterval(chrom="chr1", start=0, end=n, strand=Strand.PLUS)


def test_pam_uppercased_and_validated() -> None:
    assert PAM(pattern="ngg").pattern == "NGG"


def test_pam_rejects_non_iupac() -> None:
    with pytest.raises(ValueError, match="non-IUPAC"):
        PAM(pattern="NGZ")


def test_pam_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        PAM(pattern="")


@pytest.mark.parametrize(
    ("pattern", "seq", "ok"),
    [
        ("NGG", "AGG", True),
        ("NGG", "TGG", True),
        ("NGG", "AGA", False),
        ("NGG", "AG", False),  # wrong length
        ("TTTV", "TTTA", True),
        ("TTTV", "TTTT", False),  # V excludes T
        ("NAG", "CAG", True),
    ],
)
def test_pam_matches(pattern: str, seq: str, ok: bool) -> None:
    assert PAM(pattern=pattern).matches(seq) is ok


def test_pam_len() -> None:
    assert len(PAM(pattern="NGG")) == 3


def test_spacer_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        Spacer(sequence=DNASequence(""))


def test_guide_valid() -> None:
    g = Guide(
        spacer=_spacer(),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=_interval(),
        cut_site=17,
    )
    assert len(g.spacer) == 20


def test_guide_rejects_mismatched_pam() -> None:
    with pytest.raises(ValueError, match="does not match pattern"):
        Guide(
            spacer=_spacer(),
            pam=PAM(pattern="NGG"),
            pam_sequence=DNASequence("TGA"),
            placement=_interval(),
            cut_site=17,
        )


def test_base_edit_window_valid_and_bystanders() -> None:
    w = BaseEditWindow(
        spacer=_spacer(),
        editor="ABE8e",
        window=(4, 8),
        target_positions=(5,),
        bystander_positions=(6, 7),
    )
    assert w.has_bystanders
    assert not BaseEditWindow(spacer=_spacer(), editor="ABE8e", window=(4, 8)).has_bystanders


def test_base_edit_window_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="exceeds spacer length"):
        BaseEditWindow(spacer=_spacer(5), editor="ABE8e", window=(4, 8))


def test_base_edit_window_rejects_inverted() -> None:
    with pytest.raises(ValueError, match="invalid window"):
        BaseEditWindow(spacer=_spacer(), editor="ABE8e", window=(8, 4))


def test_pegrna_valid_defaults_to_epegrna() -> None:
    peg = PegRNA(
        spacer=_spacer(),
        scaffold=DNASequence("GTTTAGAGCTAGAAATAGCAAG"),
        rtt=DNASequence("A" * 15),
        pbs=DNASequence("A" * 12),
        rtt_homology_3prime=6,
    )
    assert peg.is_epegrna
    assert peg.three_prime_motif is ThreePrimeMotif.TEVOPREQ1


def test_pegrna_no_motif_is_not_epeg() -> None:
    peg = PegRNA(
        spacer=_spacer(),
        scaffold=DNASequence("GTTT"),
        rtt=DNASequence("A" * 15),
        pbs=DNASequence("A" * 12),
        three_prime_motif=ThreePrimeMotif.NONE,
    )
    assert not peg.is_epegrna


@pytest.mark.parametrize("pbs_len", [7, 18])
def test_pegrna_rejects_pbs_out_of_range(pbs_len: int) -> None:
    with pytest.raises(ValueError, match="PBS length"):
        PegRNA(
            spacer=_spacer(),
            scaffold=DNASequence("GTTT"),
            rtt=DNASequence("A" * 15),
            pbs=DNASequence("A" * pbs_len),
        )


@pytest.mark.parametrize("rtt_len", [6, 35])
def test_pegrna_rejects_rtt_out_of_range(rtt_len: int) -> None:
    with pytest.raises(ValueError, match="RTT length"):
        PegRNA(
            spacer=_spacer(),
            scaffold=DNASequence("GTTT"),
            rtt=DNASequence("A" * rtt_len),
            pbs=DNASequence("A" * 12),
        )


def test_pegrna_rejects_insufficient_homology() -> None:
    with pytest.raises(ValueError, match="3' homology"):
        PegRNA(
            spacer=_spacer(),
            scaffold=DNASequence("GTTT"),
            rtt=DNASequence("A" * 15),
            pbs=DNASequence("A" * 12),
            rtt_homology_3prime=3,
        )


def test_pegrna_rejects_homology_exceeding_rtt() -> None:
    with pytest.raises(ValueError, match="exceeds RTT length"):
        PegRNA(
            spacer=_spacer(),
            scaffold=DNASequence("GTTT"),
            rtt=DNASequence("A" * 10),
            pbs=DNASequence("A" * 12),
            rtt_homology_3prime=11,
        )


def test_pegrna_with_nicking_guide() -> None:
    ng = NickingGuide(
        spacer=_spacer(),
        placement=GenomicInterval(chrom="c", start=80, end=100, strand=Strand.MINUS),
        nick_offset=-45,
        seed_disrupting=True,
    )
    peg = PegRNA(
        spacer=_spacer(),
        scaffold=DNASequence("GTTT"),
        rtt=DNASequence("A" * 15),
        pbs=DNASequence("A" * 12),
        nicking_guide=ng,
    )
    assert peg.nicking_guide is not None
    assert peg.nicking_guide.seed_disrupting


@given(st.integers(min_value=8, max_value=17), st.integers(min_value=7, max_value=34))
def test_pegrna_accepts_all_in_range_geometry(pbs_len: int, rtt_len: int) -> None:
    homology = min(5, rtt_len)
    peg = PegRNA(
        spacer=_spacer(),
        scaffold=DNASequence("GTTT"),
        rtt=DNASequence("A" * rtt_len),
        pbs=DNASequence("A" * pbs_len),
        rtt_homology_3prime=homology,
    )
    assert len(peg.pbs) == pbs_len
