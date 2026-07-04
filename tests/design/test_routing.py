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


def test_small_deletion_not_routed_to_prime_until_enumerable() -> None:
    # An indel is biologically a prime edit, but enumeration templates SNVs only,
    # so routing must not advertise prime for it (that would silently under-deliver
    # the flagship). No chemistry is eligible, and prime's decision states why.
    rv = _rv("ACGT", "A")
    elig = eligible_chemistries(rv, EditIntent.CORRECT)
    assert Chemistry.PRIME not in elig
    assert elig == []  # not a base-editable SNV, not a knock-out, not yet enumerable by prime
    prime = next(d for d in route(rv, EditIntent.CORRECT) if d.chemistry is Chemistry.PRIME)
    assert prime.eligible is False
    assert "SNV" in prime.rationale and "not yet enumerated" in prime.rationale


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
