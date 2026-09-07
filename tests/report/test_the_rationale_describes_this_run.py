"""The ranking sentence described two mechanisms whether or not either had run.

    …; the safety term uses the worst-affected ancestry and the efficiency term is
    uncertainty-discounted.

Both clauses are conditional in the code and were unconditional in the prose.

`_safety` takes the worst-affected ancestry **only when the off-target report carries
ancestry annotation**; with no population source it takes the worst nominated site. So a
reference-only run — the common case, and the one whose search description elsewhere on
the page says `reference-only` in as many words — asserted the population-aware behaviour
this project exists to provide. That is the overclaim it works hardest to avoid, stated by
the ranking layer while the off-target layer was being careful two lines away.

`_efficiency` discounts **only an out-of-distribution** prediction; an in-distribution one
is ranked on its point estimate. With no OOD candidate, nothing was discounted, and the
menu already carries a separate note when there are OOD candidates — so the blanket clause
was both wrong and redundant with the accurate one.

Each clause now describes the run it is attached to, and names the mechanism that did not
apply so a reader can tell the two situations apart.
"""

from __future__ import annotations

from alleleforge.design.ranking import rank_candidates
from alleleforge.types.candidate import RankedMenu


def test_a_reference_only_run_does_not_claim_ancestry(nuclease_menu: RankedMenu) -> None:
    """The defect. No gnomAD, no ancestry annotation, no per-ancestry worst."""
    rationale = nuclease_menu.rationale
    assert "worst-affected ancestry" not in rationale, rationale
    assert "worst nominated site" in rationale, rationale
    assert "no per-ancestry worst to take" in rationale


def test_an_ancestry_annotated_run_still_says_so(ancestry_menu: RankedMenu) -> None:
    """The clause is not simply deleted — it fires when the mechanism ran."""
    outcome = rank_candidates(list(ancestry_menu.candidates))
    assert any(s.worst_ancestry for s in outcome.scores), "fixture lost its annotation"
    assert "worst-affected ancestry" in outcome.rationale, outcome.rationale


def test_an_all_in_distribution_run_does_not_claim_a_discount(
    nuclease_menu: RankedMenu,
) -> None:
    rationale = nuclease_menu.rationale
    in_dist = all(
        c.efficiency is None or c.efficiency.in_distribution for c in nuclease_menu.candidates
    )
    assert in_dist, "fixture has an OOD candidate; pick another"
    assert "the efficiency term is uncertainty-discounted" not in rationale, rationale
    assert "in-distribution, so the efficiency term is the point estimate" in rationale


def test_an_ood_run_says_the_discount_applied(make_reference: object) -> None:
    """Built, not skipped: a branch guarded by `pytest.skip` is a branch nobody checks.

    An unrecognized cell context puts every prime efficiency out of the scorer's training
    distribution, which is exactly the condition the discount exists for.
    """
    from alleleforge.design.designer import design
    from alleleforge.types.edit import EditIntent

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[58:61] = list("CCA")
    reference = make_reference({"chr2": "".join(seq)})  # type: ignore[operator]
    menu = design(
        "chr2:71:A>C",
        reference=reference,
        intent=EditIntent.INSTALL,
        run_offtarget=False,
        cell_context="NotARealCellLine",
        max_candidates_per_chemistry=3,
    )
    ood = [c for c in menu.candidates if c.efficiency and not c.efficiency.in_distribution]
    assert ood, "the fixture no longer produces an out-of-distribution candidate"
    assert "the efficiency term is uncertainty-discounted" in menu.rationale, menu.rationale


def test_the_absent_mechanism_is_still_named(nuclease_menu: RankedMenu) -> None:
    """A reader must be able to tell "did not apply" from "does not exist"."""
    assert "would be discounted to its lower interval bound" in nuclease_menu.rationale
