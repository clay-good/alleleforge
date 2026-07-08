"""Tests for SpCas9 guide enumeration, context, and HDR donor."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.enumerate.cas9 import enumerate_cas9, guide_context, hdr_donor
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _resolve_at(ref: ReferenceGenome, contig: str, zero_based: int) -> ResolvedVariant:
    """Resolve a synthetic SNV at ``zero_based`` whose ref matches the build."""
    base = str(
        ref.fetch(
            GenomicInterval(chrom=contig, start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"{contig}:{zero_based + 1}:{base}>G", reference=ref)


def test_plus_guide_strand_and_cut(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})  # plus guide proto [15,35)
    rv = _resolve_at(ref, "chr2", 32)  # the plus cut: pam_start 35, cut 32
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=10)
    plus = [
        g for g in guides if str(g.spacer.sequence) == SPACER and g.placement.strand is Strand.PLUS
    ]
    assert len(plus) == 1
    g = plus[0]
    assert (g.placement.start, g.placement.end) == (15, 35)
    assert g.cut_site == 32  # 3 bp 5' of the PAM
    assert str(g.pam_sequence) == "TGG"


def test_minus_guide_enumerated(make_reference: MakeRef) -> None:
    rc = str(DNASequence(SPACER).reverse_complement())
    ref = make_reference({"chr2": PAD + "CCA" + rc + PAD})  # minus-strand protospacer
    rv = _resolve_at(ref, "chr2", 20)
    guides = enumerate_cas9(rv, EditIntent.KNOCK_OUT, reference=ref)
    minus = [g for g in guides if g.placement.strand is Strand.MINUS]
    assert any(str(g.spacer.sequence) == SPACER for g in minus)
    assert all(str(g.pam_sequence).endswith("GG") for g in minus)


def test_actionable_window_filters_precise(make_reference: MakeRef) -> None:
    # Two plus guides far apart; only the one cutting near the edit is actionable.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + ("A" * 60) + SPACER + "TGG" + PAD})
    rv = _resolve_at(ref, "chr2", 32)
    precise = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=10)
    assert all(abs(g.cut_site - 32) <= 12 for g in precise)
    ko = enumerate_cas9(rv, EditIntent.KNOCK_OUT, reference=ref)
    assert len(ko) > len(precise)  # the wide working interval admits more


def test_ng_fallback_only_on_optin(make_reference: MakeRef) -> None:
    # 'AGT' after the protospacer is an NG (not NGG) PAM; no NGG is actionable.
    ref = make_reference({"chr2": PAD + SPACER + "AGT" + PAD})
    rv = _resolve_at(ref, "chr2", 32)
    assert enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=10) == []
    ng = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=10, allow_ng=True)
    assert any(str(g.spacer.sequence) == SPACER and g.pam.pattern == "NG" for g in ng)


def test_spry_fallback(make_reference: MakeRef) -> None:
    # No NGG and no NG: the protospacer is followed by 'ATT' (NRN/NYN only).
    ref = make_reference({"chr2": PAD + SPACER + "ATT" + PAD})
    rv = _resolve_at(ref, "chr2", 32)
    assert enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, actionable_radius=10) == []
    spry = enumerate_cas9(
        rv, EditIntent.CORRECT, reference=ref, actionable_radius=10, allow_spry=True
    )
    assert any(g.pam.pattern in ("NRN", "NYN") for g in spry)


def test_guide_context_spans_protospacer_and_pam(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    rv = _resolve_at(ref, "chr2", 32)
    g = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if str(g.spacer.sequence) == SPACER
    )
    ctx = guide_context(g, ref, flank=6)
    assert SPACER + "TGG" in ctx  # the protospacer and PAM are present
    assert len(ctx) == 20 + 3 + 12  # protospacer + PAM + 2 x flank


def test_guide_context_minus_strand(make_reference: MakeRef) -> None:
    rc = str(DNASequence(SPACER).reverse_complement())
    ref = make_reference({"chr2": PAD + "CCA" + rc + PAD})
    rv = _resolve_at(ref, "chr2", 20)
    g = next(
        g
        for g in enumerate_cas9(rv, EditIntent.KNOCK_OUT, reference=ref)
        if str(g.spacer.sequence) == SPACER and g.placement.strand is Strand.MINUS
    )
    # context is read 5'->3' on the minus strand, so it contains the spacer + PAM
    ctx = guide_context(g, ref, flank=6)
    assert SPACER in ctx
    assert str(g.pam_sequence) in ctx


def test_guide_context_asymmetric_flanks_rule_set_3_30mer(make_reference: MakeRef) -> None:
    # Rule Set 3's window: 4 nt 5' + 20 nt protospacer + 3 nt PAM + 3 nt 3' = 30.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    rv = _resolve_at(ref, "chr2", 32)
    g = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if str(g.spacer.sequence) == SPACER
    )
    ctx = guide_context(g, ref, flank_5=4, flank_3=3)
    assert len(ctx) == 30
    assert SPACER + "TGG" in ctx


def test_hdr_donor_precise_vs_knockout(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    rv = _resolve_at(ref, "chr2", 32)  # ref allele at 32 is 'C'
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, arm_length=5)
    assert donor is not None
    assert str(donor.sequence)[5] == rv.variant.ref  # correct installs the reference allele
    install = hdr_donor(rv, EditIntent.INSTALL, reference=ref, arm_length=5)
    assert install is not None and str(install.sequence)[5] == rv.variant.alt
    assert hdr_donor(rv, EditIntent.KNOCK_OUT, reference=ref) is None


def test_correct_intent_drops_guide_when_alt_destroys_pam(make_reference: MakeRef) -> None:
    # The reference presents an NGG (TGG) PAM, but the carried alt allele (which a
    # CORRECT intent repairs) turns it into TAG — no guide should be enumerated.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    rv = resolve("chr2:37:G>A", reference=ref)  # 0-based 36 = 2nd PAM base, G>A
    correct = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
    assert not any(str(g.spacer.sequence) == SPACER for g in correct)
    # An INSTALL carries the reference allele, so the PAM (and the guide) is present.
    install = enumerate_cas9(rv, EditIntent.INSTALL, reference=ref)
    assert any(str(g.spacer.sequence) == SPACER for g in install)


def test_correct_intent_finds_guide_when_alt_creates_pam(make_reference: MakeRef) -> None:
    # The reference has TGT (no NGG); the carried alt allele completes an NGG (TGG),
    # so a carried-allele-aware CORRECT enumerates the guide the reference would miss.
    ref = make_reference({"chr2": PAD + SPACER + "TGT" + PAD})
    rv = resolve("chr2:38:T>G", reference=ref)  # 0-based 37 = 3rd PAM base, T>G
    correct = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
    assert any(str(g.spacer.sequence) == SPACER for g in correct)
    # The reference itself carries no such PAM: an INSTALL (on the reference) finds none.
    install = enumerate_cas9(rv, EditIntent.INSTALL, reference=ref)
    assert not any(str(g.spacer.sequence) == SPACER for g in install)


def test_hdr_donor_records_pam_blocking_mutation(make_reference: MakeRef) -> None:
    # A PAM-distal correction leaves the guide's PAM and seed intact, so the repaired
    # allele would be re-cut: the donor must carry a recorded PAM-blocking mutation.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    rv = resolve("chr2:25:T>A", reference=ref)  # 0-based 24, PAM-distal in the protospacer
    guide = next(
        g
        for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if g.placement.strand is Strand.PLUS and str(g.pam_sequence) == "TGG"
    )
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guide)
    assert donor is not None
    assert donor.recut_blocked
    assert donor.blocking_mutation is not None
    assert donor.blocking_mutation.region == "pam"
    assert 35 <= donor.blocking_mutation.position < 38  # inside the guide's PAM


def test_hdr_donor_no_block_needed_when_edit_disrupts_pam(make_reference: MakeRef) -> None:
    # When the correction itself removes the PAM the guide relied on, no blocking
    # mutation is needed — the donor reports the repair is already re-cut-safe.
    ref = make_reference({"chr2": PAD + SPACER + "TGT" + PAD})
    rv = resolve("chr2:38:T>G", reference=ref)  # alt completes NGG; correcting removes it
    guide = next(
        g for g in enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)
        if str(g.spacer.sequence) == SPACER
    )
    donor = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guide)
    assert donor is not None
    assert donor.recut_blocked
    assert donor.blocking_mutation is None


def test_primary_pam_is_ngg(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    rv = _resolve_at(ref, "chr2", 32)
    guides = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref, pam=PAM(pattern="NGG"))
    assert all(g.pam.pattern == "NGG" for g in guides)
