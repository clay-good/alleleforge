""" "Why the other chemistries declined" has to answer with the variant.

Under that heading the report printed the routing rule's `rationale`: a
description of what the chemistry is for, identical on every run of the tool. For
`chr11:1999:T>A` it said adenine base editing is "the cleanest fix when the
required change is an A:T->G:C transition SNV" — true, general, and leaving the
reader to work out for themselves that their required change is A->T. The reader
who most needs that line is the one who wanted a base editor and is now looking at
a prime candidate.

`ChemistryDecision.decline_reason` is the half that is about their variant. The
policy sentence still follows it, because the two answer different questions.
"""

from __future__ import annotations

import pytest

from alleleforge.design import route
from alleleforge.design.routing import PRIME_MAX_EDIT, PRIME_MAX_TEMPLATED_EDIT
from alleleforge.types import EditIntent
from alleleforge.variant.resolver import resolve

_CASES: list[tuple[str, EditIntent]] = [
    ("chr11:2000:T>A", EditIntent.CORRECT),  # transversion: no base editor
    ("chr11:2000:T>C", EditIntent.CORRECT),  # transition: CBE reachable
    ("chr11:2000:A>G", EditIntent.INSTALL),
    ("chr11:2000:T>A", EditIntent.KNOCK_OUT),  # only the nuclease
    (f"chr11:2000:{'A' * (PRIME_MAX_EDIT + 5)}>A", EditIntent.CORRECT),  # over budget
    (f"chr11:2000:A>{'A' * (PRIME_MAX_TEMPLATED_EDIT + 5)}", EditIntent.CORRECT),
]


def _decisions(spec: str, intent: EditIntent) -> list:
    return route(resolve(spec, build="hg38"), intent)


@pytest.mark.parametrize(("spec", "intent"), _CASES, ids=lambda v: str(v)[:24])
def test_a_reason_is_present_exactly_when_the_route_closed(spec: str, intent: EditIntent) -> None:
    decisions = _decisions(spec, intent)
    assert len(decisions) >= 4, decisions
    for decision in decisions:
        if decision.eligible:
            assert decision.decline_reason is None, decision
        else:
            assert decision.decline_reason, decision
            assert not decision.decline_reason.endswith("."), (
                "the renderer appends the sentence break; the reason must not carry one"
            )


def test_the_reason_names_the_change_the_editor_cannot_make() -> None:
    """The concrete fact, not the general policy."""
    by_chemistry = {d.chemistry.value: d for d in _decisions("chr11:2000:T>A", EditIntent.CORRECT)}
    abe = by_chemistry["base_abe"]
    assert not abe.eligible
    # Correcting means writing the reference back, so the required change is A->T.
    assert "A->T" in abe.decline_reason, abe.decline_reason


def test_the_reason_moves_with_the_variant() -> None:
    """The defect this replaces: a sentence that was the same on every run."""
    first = {
        d.chemistry.value: d.decline_reason
        for d in _decisions("chr11:2000:T>A", EditIntent.CORRECT)
    }
    second = {
        d.chemistry.value: d.decline_reason
        for d in _decisions("chr11:2000:G>T", EditIntent.CORRECT)
    }
    assert first["base_abe"] != second["base_abe"], first["base_abe"]


def test_the_reason_names_the_budget_that_bound() -> None:
    over = {
        d.chemistry.value: d
        for d in _decisions(f"chr11:2000:{'A' * (PRIME_MAX_EDIT + 5)}>A", EditIntent.CORRECT)
    }
    prime = over["prime"]
    assert not prime.eligible
    assert str(PRIME_MAX_EDIT) in prime.decline_reason, prime.decline_reason


def test_the_rendered_rationale_leads_with_the_reason() -> None:
    """The heading's promise is kept on the surface a reader actually reads."""
    from alleleforge.design.designer import _menu_rationale

    decisions = _decisions("chr11:2000:T>A", EditIntent.CORRECT)
    eligible = [d.chemistry for d in decisions if d.eligible]
    assert eligible, decisions
    text = _menu_rationale(decisions, eligible, [], "ranked somehow")
    line = next(ln for ln in text.splitlines() if ln.startswith("- base_abe:"))
    assert line.startswith("- base_abe: the required change is A->T"), line
