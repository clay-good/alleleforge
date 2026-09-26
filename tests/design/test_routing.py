"""Tests for the Phase 10 chemistry router."""

from __future__ import annotations

from alleleforge.design.routing import ROUTING_RULES, eligible_chemistries, route
from alleleforge.enumerate.prime import PRIME_MAX_EDIT, PRIME_MAX_TEMPLATED_EDIT
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


# -- the advertised prime budget, at its own boundary ---------------------------
#
# Routing decides which chemistry a variant is offered, and for prime that decision is two
# size limits: `PRIME_MAX_EDIT` on the alleles and `PRIME_MAX_TEMPLATED_EDIT` on what the
# RTT has to write. Both are advertised numbers. Every existing fixture sits far past them
# (a 61-nt allele, a 41-nt insertion), so tightening either comparison by one — refusing an
# edit of exactly the budget — changed nothing in 991 tests. The refusal is silent: the
# chemistry simply is not offered, with a decline reason that reads correctly.
#
# The same pair of comparisons appears twice, once in `_prime_eligible` and once in
# `_why_not_prime`, so the gate and the sentence explaining the gate are required to agree.


def _decline(rv: ResolvedVariant, intent: EditIntent, chemistry: Chemistry) -> str | None:
    return next(d for d in route(rv, intent) if d.chemistry is chemistry).decline_reason


def test_an_edit_of_exactly_the_prime_budget_is_still_offered() -> None:
    """`len(ref) > PRIME_MAX_EDIT` rejects what is *over* the budget, not what fills it.

    The intent matters, and picking the wrong one measures the other limit instead:
    *correcting* a long deletion means writing the whole reference allele back, which the
    29-nt templated budget refuses first. Installing it writes only the short alt, so this
    fixture reaches the allele-size limit and nothing else.
    """
    at_budget = _rv("A" * PRIME_MAX_EDIT, "A")
    assert Chemistry.PRIME in eligible_chemistries(at_budget, EditIntent.INSTALL)
    assert _decline(at_budget, EditIntent.INSTALL, Chemistry.PRIME) is None

    over = _rv("A" * (PRIME_MAX_EDIT + 1), "A")
    assert Chemistry.PRIME not in eligible_chemistries(over, EditIntent.INSTALL)


def test_the_budget_applies_to_whichever_allele_is_longer() -> None:
    """Both `len(ref)` and `len(alt)` are checked, so neither may be the only one tested."""
    # Each intent writes the *other* allele, so one intent per side reaches this limit
    # without the templated-edit budget firing first.
    long_alt = _rv("A", "A" * (PRIME_MAX_EDIT + 1))
    assert Chemistry.PRIME not in eligible_chemistries(long_alt, EditIntent.CORRECT)

    long_ref = _rv("A" * (PRIME_MAX_EDIT + 1), "A")
    assert Chemistry.PRIME not in eligible_chemistries(long_ref, EditIntent.INSTALL)


def test_a_templated_edit_of_exactly_the_rtt_budget_is_still_offered() -> None:
    """`len(desired) <= PRIME_MAX_TEMPLATED_EDIT` admits the budget itself.

    This is the limit on what the RTT must *write*, which for an install is the alt allele.
    Tightened to `<`, the longest insertion the template can carry is declined as
    untemplatable.
    """
    at_budget = _rv("A", "A" * PRIME_MAX_TEMPLATED_EDIT)
    assert Chemistry.PRIME in eligible_chemistries(at_budget, EditIntent.INSTALL)

    over = _rv("A", "A" * (PRIME_MAX_TEMPLATED_EDIT + 1))
    assert Chemistry.PRIME not in eligible_chemistries(over, EditIntent.INSTALL)


def test_the_decline_reason_agrees_with_the_gate_at_the_boundary() -> None:
    """One rule, two implementations: `_prime_eligible` and `_why_not_prime`.

    The size comparison is written twice. If they disagree, a variant is declined with a
    reason that does not apply to it, or admitted while the explaining branch thinks it is
    over budget — and only the sentence is visible to a reader.
    """
    for length in (PRIME_MAX_EDIT - 1, PRIME_MAX_EDIT, PRIME_MAX_EDIT + 1, PRIME_MAX_EDIT + 20):
        rv = _rv("A" * length, "A")
        eligible = Chemistry.PRIME in eligible_chemistries(rv, EditIntent.INSTALL)
        reason = _decline(rv, EditIntent.INSTALL, Chemistry.PRIME)
        assert eligible is (reason is None), f"gate and reason disagree at {length} nt"
        if not eligible:
            assert "practical RTT budget" in (reason or ""), reason


def test_the_decline_reason_reports_the_longer_allele() -> None:
    """`max(len(ref), len(alt))` — `min` understates the edit that was refused.

    The sentence is the only place the size appears, so a reader checking whether their
    edit is near the limit is reading this number. Asserted with the long allele on each
    side, since a symmetric pair cannot tell `max` from `min`.
    """
    over = PRIME_MAX_EDIT + 6
    long_ref = _decline(_rv("A" * over, "A"), EditIntent.INSTALL, Chemistry.PRIME)
    assert f"spans {over} nt" in (long_ref or ""), long_ref

    long_alt = _decline(_rv("A", "A" * over), EditIntent.CORRECT, Chemistry.PRIME)
    assert f"spans {over} nt" in (long_alt or ""), long_alt


# -- the reason a base-editing route was closed --------------------------------


def test_a_transversion_is_declined_for_its_transition_not_its_class() -> None:
    """`_why_not_base` checks `is not SNV`; inverted, an SNV is told it is not one.

    A transversion *is* an SNV, so the fact that closed the route is the required change,
    not the variant class. Inverted, the reader is told "the variant class is snv; a base
    editor edits a single base" about a single-base variant — a sentence that is both
    wrong and unactionable.
    """
    reason = _decline(_rv("A", "T"), EditIntent.INSTALL, Chemistry.BASE_ABE) or ""
    assert "A->T" in reason
    assert "no adenine base editor installs" in reason
    assert "the variant class is snv" not in reason


def test_a_non_snv_is_declined_for_its_class() -> None:
    """The other branch, so the check above cannot pass by never naming a class."""
    reason = _decline(_rv("AT", "A"), EditIntent.CORRECT, Chemistry.BASE_ABE) or ""
    assert "a base editor edits a single base" in reason


def test_an_alt_allele_of_exactly_the_prime_budget_is_still_offered() -> None:
    """The alt side of `len(ref) > MAX or len(alt) > MAX`, at the boundary.

    The over-budget case cannot separate the two comparisons — 45 is over on either
    reading — so each side needs its own at-the-boundary check. Correcting a long
    insertion writes only the short reference allele back, which keeps the templated-edit
    budget out of the way.
    """
    at_budget = _rv("A", "A" * PRIME_MAX_EDIT)
    assert Chemistry.PRIME in eligible_chemistries(at_budget, EditIntent.CORRECT)
    assert _decline(at_budget, EditIntent.CORRECT, Chemistry.PRIME) is None


def test_a_decline_at_the_allele_budget_names_the_limit_that_actually_applied() -> None:
    """`_why_not_prime` repeats the size comparison, and can blame the wrong limit.

    An allele of exactly `PRIME_MAX_EDIT` is within the allele budget but its *write* may
    still exceed the templated-edit budget, which is what declines it. Relax the reason
    function's comparison to `>=` and it reports the allele size instead — telling a
    caller to shorten an edit that is already inside the limit the message names, while
    the real constraint goes unmentioned.

    Both sides are covered, because the reason function repeats the comparison twice and
    only one of them is reached per intent.
    """
    templated = "templated-edit budget"

    # Correcting a deletion writes the whole reference allele back.
    long_ref = _rv("A" * PRIME_MAX_EDIT, "A")
    assert Chemistry.PRIME not in eligible_chemistries(long_ref, EditIntent.CORRECT)
    reason = _decline(long_ref, EditIntent.CORRECT, Chemistry.PRIME) or ""
    assert templated in reason, reason
    assert "practical RTT budget" not in reason

    # Installing an insertion writes the whole alt allele.
    long_alt = _rv("A", "A" * PRIME_MAX_EDIT)
    assert Chemistry.PRIME not in eligible_chemistries(long_alt, EditIntent.INSTALL)
    reason = _decline(long_alt, EditIntent.INSTALL, Chemistry.PRIME) or ""
    assert templated in reason, reason
    assert "practical RTT budget" not in reason
