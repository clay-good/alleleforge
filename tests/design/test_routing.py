"""Tests for the Phase 10 chemistry router."""

from __future__ import annotations

from alleleforge.design.routing import ROUTING_RULES, eligible_chemistries, route
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import ResolvedVariant


def _rv(ref: str, alt: str, *, chrom: str = "chr1", pos: int = 100) -> ResolvedVariant:
    var = Variant(chrom=chrom, pos=pos, ref=ref, alt=alt)
    wi = GenomicInterval(chrom=chrom, start=max(0, pos - 10), end=pos + 10, strand=Strand.PLUS)
    return ResolvedVariant(variant=var, working_interval=wi, source="test")


def test_install_transition_routes_to_abe_and_prime() -> None:
    # Installing A->G is an adenine transition: ABE + prime, not CBE, not nuclease.
    elig = eligible_chemistries(_rv("A", "G"), EditIntent.INSTALL)
    assert Chemistry.BASE_ABE in elig
    assert Chemistry.PRIME in elig
    assert Chemistry.BASE_CBE not in elig
    assert Chemistry.CAS9_NUCLEASE not in elig


def test_correct_transition_routes_to_cbe() -> None:
    # The genome carries the alt G; correcting restores ref A => a G->A change,
    # which a cytosine base editor installs (on the complementary strand).
    elig = eligible_chemistries(_rv("A", "G"), EditIntent.CORRECT)
    assert Chemistry.BASE_CBE in elig
    assert Chemistry.PRIME in elig
    assert Chemistry.BASE_ABE not in elig


def test_transversion_excludes_base_editing() -> None:
    elig = eligible_chemistries(_rv("A", "C"), EditIntent.INSTALL)
    assert Chemistry.BASE_ABE not in elig
    assert Chemistry.BASE_CBE not in elig
    assert Chemistry.PRIME in elig  # a precise transversion still suits prime


def test_knock_out_routes_to_nuclease_only() -> None:
    elig = eligible_chemistries(_rv("A", "G"), EditIntent.KNOCK_OUT)
    assert elig == [Chemistry.CAS9_NUCLEASE]


def test_small_indel_routes_to_prime_only() -> None:
    # An indel is a prime edit and the variable-length RTT path enumerates it, so
    # routing advertises prime — and only prime: a base editor cannot make an
    # indel, and disruption is the nuclease's job.
    rv = _rv("ACGT", "A")
    elig = eligible_chemistries(rv, EditIntent.CORRECT)
    assert elig == [Chemistry.PRIME]
    prime = next(d for d in route(rv, EditIntent.CORRECT) if d.chemistry is Chemistry.PRIME)
    assert prime.eligible is True
    assert "insertion, deletion" in prime.rationale


def test_insertion_and_delins_route_to_prime() -> None:
    for ref, alt in (("A", "AGGCT"), ("ACGT", "TT"), ("ACG", "TTA"), ("", "GGC"), ("ACG", "")):
        elig = eligible_chemistries(_rv(ref, alt), EditIntent.INSTALL)
        assert elig == [Chemistry.PRIME], f"{ref}>{alt}"


def test_untemplatable_allele_excludes_prime() -> None:
    # The RTT must carry the whole written allele plus its 3' homology inside
    # RTT_RANGE. A 40-nt insertion fits PRIME_MAX_EDIT but no RT template, so
    # routing must not advertise what enumeration cannot produce.
    rv = _rv("A", "A" + "CGTA" * 10)
    assert Chemistry.PRIME not in eligible_chemistries(rv, EditIntent.INSTALL)
    # Correcting the same variant only writes the single reference base back.
    assert Chemistry.PRIME in eligible_chemistries(rv, EditIntent.CORRECT)


def test_large_edit_excludes_prime() -> None:
    big = "A" + "C" * 60
    elig = eligible_chemistries(_rv(big, "A"), EditIntent.CORRECT)
    assert Chemistry.PRIME not in elig  # beyond the practical RTT length


def test_route_explains_every_rule() -> None:
    decisions = route(_rv("A", "G"), EditIntent.INSTALL)
    assert len(decisions) == len(ROUTING_RULES)
    for d in decisions:
        assert d.rationale  # every chemistry carries a biological rationale
    abe = next(d for d in decisions if d.chemistry is Chemistry.BASE_ABE)
    assert abe.eligible is True


def test_eligible_order_is_cleanest_first() -> None:
    # Both ABE and prime apply; the menu order puts the base editor first.
    elig = eligible_chemistries(_rv("A", "G"), EditIntent.INSTALL)
    assert elig.index(Chemistry.BASE_ABE) < elig.index(Chemistry.PRIME)


def test_a_large_precise_edit_falls_back_to_nuclease_plus_hdr() -> None:
    """The case that used to return an empty menu: a 41-base restoration.

    No RT template can write it and no base editor can make an indel, so the only
    remaining route is a break plus an HDR donor. It is a genuinely worse option —
    which is why it is offered *only* here, and why it is the last rule in the
    table rather than a peer of the break-free chemistries.
    """
    rv = _rv("A" + "CGTA" * 10, "A")
    elig = eligible_chemistries(rv, EditIntent.CORRECT)
    assert elig == [Chemistry.CAS9_NUCLEASE]
    nuclease = next(
        d for d in route(rv, EditIntent.CORRECT) if d.chemistry is Chemistry.CAS9_NUCLEASE
    )
    assert "last resort" in nuclease.rationale


def test_nuclease_stays_out_of_a_menu_a_break_free_chemistry_can_serve() -> None:
    """HDR must not crowd menus where prime or a base editor already reaches."""
    for ref, alt, intent in (
        ("A", "G", EditIntent.INSTALL),  # ABE + prime
        ("ACGT", "A", EditIntent.CORRECT),  # a small indel: prime
        ("A", "AGGCT", EditIntent.INSTALL),  # a small insertion: prime
    ):
        elig = eligible_chemistries(_rv(ref, alt), intent)
        assert Chemistry.CAS9_NUCLEASE not in elig, f"{ref}>{alt} {intent.value}"


def test_an_empty_menu_says_why_each_chemistry_declined() -> None:
    """A blank menu with four `no`s tells the reader nothing they can act on.

    Routing itself now always admits something (the nuclease backstops every
    precise intent), so an empty *menu* arises when the caller restricts the
    chemistries — the rationale assembly must still explain itself there.
    """
    from alleleforge.design.designer import _menu_rationale

    decisions = route(_rv("A", "G"), EditIntent.INSTALL)
    text = _menu_rationale(decisions, [], [], "ranking blurb")
    assert "No chemistry can make this edit. Why each declined:" in text
    for decision in decisions:
        assert decision.rationale in text


def test_a_non_empty_menu_does_not_repeat_every_rationale() -> None:
    from alleleforge.design.designer import _menu_rationale

    decisions = route(_rv("A", "G"), EditIntent.INSTALL)
    text = _menu_rationale(decisions, [Chemistry.PRIME], [], "ranking blurb")
    assert "No chemistry can make this edit" not in text
