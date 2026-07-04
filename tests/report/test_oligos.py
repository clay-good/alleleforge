"""Round-trip and correctness tests for cloning oligos (Phase 11)."""

from __future__ import annotations

import pytest

from alleleforge.report.oligos import (
    LENTIGUIDE_BSMBI,
    PEGRNA_GG_BSAI,
    PX330_BBSI,
    PegRNAOligos,
    SgRnaOligos,
    oligos_for,
    pegrna_oligos,
    revcomp,
    sgrna_oligos,
)
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry

SPACER = "ACGTAACGTTACGTAACGTT"


def test_revcomp() -> None:
    assert revcomp("ACGT") == "ACGT"
    assert revcomp("AAACCCGGGTTT") == "AAACCCGGGTTT"
    assert revcomp("ATGCN") == "NGCAT"


@pytest.mark.parametrize("scheme", [LENTIGUIDE_BSMBI, PX330_BBSI])
def test_sgrna_oligo_roundtrip(scheme: object) -> None:
    oligos = sgrna_oligos(SPACER, scheme=scheme)  # type: ignore[arg-type]
    assert oligos.reconstruct() == SPACER
    # The duplex anneals: bottom is the reverse complement of the G + spacer core.
    assert oligos.top == scheme.top_overhang + "G" + SPACER  # type: ignore[attr-defined]
    assert oligos.bottom == scheme.bottom_overhang + revcomp("G" + SPACER)  # type: ignore[attr-defined]


def test_sgrna_oligo_roundtrip_spacer_starting_with_g() -> None:
    spacer = "G" + SPACER[1:]
    oligos = sgrna_oligos(spacer)
    assert oligos.reconstruct() == spacer  # the prepended G is stripped, not the spacer's own


def test_malformed_oligo_rejected() -> None:
    bad = SgRnaOligos(
        kind="sgrna", spacer=SPACER, top="TTTT" + SPACER, bottom="AAAC", scheme=LENTIGUIDE_BSMBI
    )
    with pytest.raises(ValueError, match="5' overhang"):
        bad.reconstruct()


def test_cas9_oligos_from_menu(nuclease_menu: RankedMenu) -> None:
    top = nuclease_menu.candidates[0]
    assert top.chemistry is Chemistry.CAS9_NUCLEASE
    oligos = oligos_for(top)
    assert isinstance(oligos, SgRnaOligos)
    assert oligos.kind == "sgrna"
    assert oligos.reconstruct() == str(top.guide.spacer.sequence)  # type: ignore[union-attr]


def test_base_editor_oligos_from_menu(abe_menu: RankedMenu) -> None:
    top = abe_menu.candidates[0]
    oligos = oligos_for(top)
    assert isinstance(oligos, SgRnaOligos)
    assert oligos.kind == "base-editor-sgrna"
    assert oligos.reconstruct() == str(top.base_edit_window.spacer.sequence)  # type: ignore[union-attr]


def test_pegrna_oligos_roundtrip(prime_menu: RankedMenu) -> None:
    top = prime_menu.candidates[0]
    peg = top.pegrna
    assert peg is not None
    oligos = pegrna_oligos(peg, scheme=PEGRNA_GG_BSAI)
    assert isinstance(oligos, PegRNAOligos)
    spacer, rtt, pbs = oligos.reconstruct()
    assert spacer == str(peg.spacer.sequence)
    assert rtt == str(peg.rtt)
    assert pbs == str(peg.pbs)


def test_pegrna_extension_contains_motif(prime_menu: RankedMenu) -> None:
    top = prime_menu.candidates[0]
    peg = top.pegrna
    assert peg is not None and peg.is_epegrna
    oligos = pegrna_oligos(peg)
    # the 3' extension carries RTT + PBS + the epegRNA motif, in that order
    assert str(peg.rtt) in oligos.ext_top
    assert str(peg.pbs) in oligos.ext_top
    assert oligos.scaffold == str(peg.scaffold)


def test_pegrna_includes_ngrna_when_pe3(prime_menu: RankedMenu) -> None:
    top = prime_menu.candidates[0]
    peg = top.pegrna
    assert peg is not None and peg.nicking_guide is not None
    oligos = pegrna_oligos(peg)
    assert oligos.nicking is not None
    assert oligos.nicking.kind == "ngrna"
    assert oligos.nicking.reconstruct() == str(peg.nicking_guide.spacer.sequence)


def test_oligos_for_no_reagent_returns_none() -> None:
    from alleleforge.types.candidate import DesignCandidate

    assert oligos_for(DesignCandidate(chemistry=Chemistry.PRIME)) is None


def test_sgrna_missing_transcription_g_rejected() -> None:
    bad = SgRnaOligos(
        kind="sgrna",
        spacer=SPACER,
        top="CACC" + SPACER,  # no prepended G though the scheme requires it
        bottom="AAAC" + revcomp(SPACER),
        scheme=LENTIGUIDE_BSMBI,
    )
    with pytest.raises(ValueError, match="transcription-start G"):
        bad.reconstruct()


def test_sgrna_mismatched_bottom_rejected() -> None:
    bad = SgRnaOligos(
        kind="sgrna",
        spacer=SPACER,
        top="CACCG" + SPACER,
        bottom="AAACTTTTTTTTTTTTTTTTTTTTTT",  # not the reverse complement
        scheme=LENTIGUIDE_BSMBI,
    )
    with pytest.raises(ValueError, match="reverse complement"):
        bad.reconstruct()


def test_pegrna_reconstruct_detects_missing_motif(prime_menu: RankedMenu) -> None:
    peg = prime_menu.candidates[0].pegrna
    assert peg is not None
    oligos = pegrna_oligos(peg)
    tampered = oligos.model_copy(update={"ext_top": oligos.ext_top[:-4]})  # drop the motif tail
    with pytest.raises(ValueError, match="3' motif|reverse complement"):
        tampered.reconstruct()


# -- alphabet, scaffold, and boundary safety ----------------------------------


def test_revcomp_rejects_non_dna() -> None:
    for bad in ("ACGU", "ACGR", "AC GT"):
        with pytest.raises(ValueError, match="ACGTN only"):
            revcomp(bad)


@pytest.mark.parametrize(
    "bad_spacer", ["ACGUAACGTTACGTAACGTT", "ACGRAACGTTACGTAACGTT", "ACGT AACGTTACGTAACGT"]
)
def test_sgrna_rejects_non_dna_spacer(bad_spacer: str) -> None:
    with pytest.raises(ValueError, match="ACGTN only"):
        sgrna_oligos(bad_spacer)


def test_valid_dna_spacer_unchanged() -> None:
    # A valid spacer still builds and round-trips exactly as before.
    assert sgrna_oligos(SPACER).reconstruct() == SPACER


def test_pegrna_wrong_scaffold_rejected(prime_menu: RankedMenu) -> None:
    from alleleforge.types.sequence import DNASequence

    peg = prime_menu.candidates[0].pegrna
    assert peg is not None
    bad = peg.model_copy(update={"scaffold": DNASequence("ACGTACGTACGT")})
    with pytest.raises(ValueError, match="scaffold does not match"):
        pegrna_oligos(bad)


def test_pegrna_missplit_extension_detected() -> None:
    from alleleforge.enumerate.prime import SCAFFOLD
    from alleleforge.types.guide import ThreePrimeMotif

    scheme = PEGRNA_GG_BSAI
    spacer_top = scheme.top_overhang + "G" + SPACER
    spacer_bottom = scheme.bottom_overhang + revcomp("G" + SPACER)
    # The extension body carries an extra base, so it no longer equals RTT + PBS.
    body = "AAAA" + "G" + "CCCC"  # declared rtt="AAAA", pbs="CCCC" -> body should be 8 nt
    ext_top = "GTGC" + body
    ext_bottom = "AAAA" + revcomp(body)
    oligos = PegRNAOligos(
        spacer=SPACER,
        rtt="AAAA",
        pbs="CCCC",
        motif=ThreePrimeMotif.NONE,
        scaffold=SCAFFOLD,
        spacer_top=spacer_top,
        spacer_bottom=spacer_bottom,
        ext_top=ext_top,
        ext_bottom=ext_bottom,
        nicking=None,
        scheme=scheme,
    )
    with pytest.raises(ValueError, match="RTT\\+PBS boundary"):
        oligos.reconstruct()
