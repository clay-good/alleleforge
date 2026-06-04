"""Chemistry routing: which edits each chemistry can biologically address.

The router is the first half of the variant-first promise. Given a resolved
variant and an intent, it decides — through a small set of **transparent,
inspectable rules** — which chemistries are even worth enumerating, so the
designer never wastes work on a chemistry that physically cannot make the edit.

Each :class:`RoutingRule` pairs a chemistry with a one-line biological rationale
and a pure predicate over ``(resolved, intent)``. The rule table is data, so
adding a chemistry or relaxing a rule is a one-line change and the reasoning is
always visible in the output via :func:`route`.

The rules encode four facts about today's editing toolbox:

* **Nuclease** makes double-strand breaks repaired by error-prone NHEJ — the
  canonical way to *knock out* a gene, and useless for a precise correction.
* **Base editors** install a single transition (ABE: A->G / T->C; CBE:
  C->T / G->A) within a narrow window, without a break — eligible only for a
  transition SNV whose required change one of the editors can chemically make.
* **Prime editing** writes an arbitrary small edit (substitution, short
  insertion, short deletion) from an RTT template without a break — eligible for
  any precise small edit up to the practical RTT length.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from alleleforge.enumerate.base_editor import BASE_EDITORS
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.variant import VariantClass
from alleleforge.variant.resolver import ResolvedVariant

#: Practical upper bound (bp) on an edit prime editing can template in an RTT.
#: Beyond this the edit is better served by nuclease-plus-HDR or a larger tool.
PRIME_MAX_EDIT = 44


def _required_change(resolved: ResolvedVariant, intent: EditIntent) -> tuple[str, str]:
    """Return the plus-strand ``(from_allele, to_allele)`` an intent requires.

    Mirrors the enumeration layer: correcting or reverting restores the
    reference (the genome carries the alt), while installing writes the alt.
    """
    var = resolved.variant
    if intent in (EditIntent.CORRECT, EditIntent.REVERT):
        return var.alt, var.ref
    return var.ref, var.alt


def _nuclease_eligible(resolved: ResolvedVariant, intent: EditIntent) -> bool:
    """Nuclease is for disruption: a knock-out via NHEJ-induced frameshifts."""
    return intent is EditIntent.KNOCK_OUT


def _base_eligible(resolved: ResolvedVariant, intent: EditIntent, chemistry: Chemistry) -> bool:
    """A base editor of ``chemistry`` can make the intent's transition in-window."""
    if intent is EditIntent.KNOCK_OUT:
        return False  # disruption is the nuclease's job, not a clean transition
    if resolved.variant.variant_class is not VariantClass.SNV:
        return False
    frm, to = _required_change(resolved, intent)  # single bases for an SNV
    return any(
        editor.installs(frm, to) is not None
        for editor in BASE_EDITORS
        if editor.chemistry is chemistry
    )


def _prime_eligible(resolved: ResolvedVariant, intent: EditIntent) -> bool:
    """Prime editing handles any precise small edit (not bulk disruption)."""
    if intent is EditIntent.KNOCK_OUT:
        return False
    var = resolved.variant
    return len(var.ref) <= PRIME_MAX_EDIT and len(var.alt) <= PRIME_MAX_EDIT


@dataclass(frozen=True)
class RoutingRule:
    """One transparent eligibility rule for a chemistry.

    Attributes:
        chemistry: The chemistry this rule admits.
        name: A short, stable rule identifier (audit aid).
        rationale: The biological reason the rule exists.
        predicate: Pure ``(resolved, intent) -> bool`` eligibility test.
    """

    chemistry: Chemistry
    name: str
    rationale: str
    predicate: Callable[[ResolvedVariant, EditIntent], bool]

    def applies(self, resolved: ResolvedVariant, intent: EditIntent) -> bool:
        """Return ``True`` when this rule admits ``(resolved, intent)``."""
        return self.predicate(resolved, intent)


#: The routing table, in default menu order (cleanest chemistry first). Ranking
#: produces the final order; this only fixes a deterministic enumeration order.
ROUTING_RULES: tuple[RoutingRule, ...] = (
    RoutingRule(
        chemistry=Chemistry.BASE_ABE,
        name="abe-transition",
        rationale=(
            "Adenine base editing installs an A->G / T->C transition in a narrow "
            "window with no double-strand break — the cleanest fix when the "
            "required change is an A:T->G:C transition SNV."
        ),
        predicate=lambda r, i: _base_eligible(r, i, Chemistry.BASE_ABE),
    ),
    RoutingRule(
        chemistry=Chemistry.BASE_CBE,
        name="cbe-transition",
        rationale=(
            "Cytosine base editing installs a C->T / G->A transition in a narrow "
            "window with no double-strand break — eligible when the required "
            "change is a G:C->A:T transition SNV."
        ),
        predicate=lambda r, i: _base_eligible(r, i, Chemistry.BASE_CBE),
    ),
    RoutingRule(
        chemistry=Chemistry.PRIME,
        name="prime-precise-small-edit",
        rationale=(
            "Prime editing writes an arbitrary small edit (substitution, short "
            "insertion or deletion) from an RTT template without a break — "
            "eligible for any precise edit up to the practical RTT length."
        ),
        predicate=_prime_eligible,
    ),
    RoutingRule(
        chemistry=Chemistry.CAS9_NUCLEASE,
        name="nuclease-disruption",
        rationale=(
            "An SpCas9 double-strand break repaired by error-prone NHEJ yields "
            "frameshifting indels that ablate gene function — the canonical "
            "knock-out route, eligible only for disruption intent."
        ),
        predicate=_nuclease_eligible,
    ),
)


@dataclass(frozen=True)
class ChemistryDecision:
    """The routing verdict for one chemistry, with its reasoning.

    Attributes:
        chemistry: The chemistry judged.
        eligible: Whether the rule admitted this ``(variant, intent)``.
        rule: The rule that was evaluated.
    """

    chemistry: Chemistry
    eligible: bool
    rule: RoutingRule

    @property
    def rationale(self) -> str:
        """Return the rule's biological rationale."""
        return self.rule.rationale


def route(resolved: ResolvedVariant, intent: EditIntent) -> list[ChemistryDecision]:
    """Evaluate every routing rule and return its verdict (eligible or not).

    This is the inspectable form: it explains why each chemistry was kept or
    dropped. Use :func:`eligible_chemistries` for just the admitted set.

    Args:
        resolved: The resolved variant to route.
        intent: What the edit must accomplish.

    Returns:
        One :class:`ChemistryDecision` per rule, in routing-table order.
    """
    return [
        ChemistryDecision(
            chemistry=rule.chemistry, eligible=rule.applies(resolved, intent), rule=rule
        )
        for rule in ROUTING_RULES
    ]


def eligible_chemistries(resolved: ResolvedVariant, intent: EditIntent) -> list[Chemistry]:
    """Return the chemistries eligible to address ``(resolved, intent)``.

    Args:
        resolved: The resolved variant to route.
        intent: What the edit must accomplish.

    Returns:
        Eligible chemistries in default menu order (cleanest first). May be
        empty when no chemistry can make the requested edit.
    """
    return [d.chemistry for d in route(resolved, intent) if d.eligible]
