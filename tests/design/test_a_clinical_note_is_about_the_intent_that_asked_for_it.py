"""Each clinical note names an intent, and must only be attached to that intent.

`_clinical_notes` writes three sentences that put the requested intent beside what a
database asserts. Each is guarded by a conjunction — *this intent* **and** *this fact* —
and every fixture in the suite satisfies both arms at once, because a note is written
about the case it was designed for. Drop either arm and the suite stays green while the
note is attached to a run it is not about:

* the modifier-impact note says "confirm this is the change you mean to make", which is
  advice for a **correction**. Without its intent arm an `install` — deliberately
  writing a variant in, where a modifier consequence is often the whole point — is
  asked to reconsider.
* the disease-model note says "intent install writes an allele ClinVar classifies as
  pathogenic — a disease model, not a correction". `EditIntent` has four members, and
  the `elif` it sits in is reached by **knock-out** as well as install, so without its
  intent arm a knock-out is told it is installing. Without its significance arm the
  same sentence is printed for a **benign** allele, which is the opposite claim.

Each case below has its negative beside it: a note that fires for everything is no more
informative than one that fires for nothing.
"""

from __future__ import annotations

import pytest

from alleleforge.design.designer import _clinical_notes
from alleleforge.types.edit import EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import (
    ClinicalAssertion,
    ClinicalSignificance,
    Variant,
)
from alleleforge.variant.effect import Consequence, Impact, VariantEffect
from alleleforge.variant.resolver import ResolvedVariant

_VARIANT = Variant(chrom="chr2", pos=70, ref="A", alt="C", build="hg38")
_INTERVAL = GenomicInterval(chrom="chr2", start=20, end=120, strand=Strand.PLUS)


def _resolved(
    *,
    effect: VariantEffect | None = None,
    assertion: ClinicalAssertion | None = None,
) -> ResolvedVariant:
    return ResolvedVariant(
        variant=_VARIANT,
        working_interval=_INTERVAL,
        source="coordinates",
        effect=effect,
        clinical_assertion=assertion,
    )


def _effect(impact: Impact) -> VariantEffect:
    consequence = Consequence.INTERGENIC if impact is Impact.MODIFIER else Consequence.STOP_GAINED
    return VariantEffect(consequence=consequence, impact=impact, transcript="MANE_SELECT")


_MODIFIER_NOTE = "predicted to have modifier"
_DISEASE_MODEL_NOTE = "a disease model, not a correction"


@pytest.mark.parametrize("intent", [EditIntent.CORRECT, EditIntent.REVERT])
def test_a_correction_of_a_modifier_variant_is_flagged(intent: EditIntent) -> None:
    notes = _clinical_notes(_resolved(effect=_effect(Impact.MODIFIER)), intent)
    assert any(_MODIFIER_NOTE in n for n in notes), notes


@pytest.mark.parametrize("intent", [EditIntent.INSTALL, EditIntent.KNOCK_OUT])
def test_an_intent_that_is_not_a_correction_is_not_asked_to_reconsider(
    intent: EditIntent,
) -> None:
    notes = _clinical_notes(_resolved(effect=_effect(Impact.MODIFIER)), intent)
    assert not any(_MODIFIER_NOTE in n for n in notes), notes


def test_a_correction_of_a_high_impact_variant_is_not_flagged() -> None:
    """The other arm: the note is about the impact, not about every correction."""
    notes = _clinical_notes(_resolved(effect=_effect(Impact.HIGH)), EditIntent.CORRECT)
    assert not any(_MODIFIER_NOTE in n for n in notes), notes


@pytest.mark.parametrize(
    "significance",
    [ClinicalSignificance.PATHOGENIC, ClinicalSignificance.LIKELY_PATHOGENIC],
)
def test_installing_a_pathogenic_allele_is_called_a_disease_model(
    significance: ClinicalSignificance,
) -> None:
    notes = _clinical_notes(
        _resolved(assertion=ClinicalAssertion(significance=significance)),
        EditIntent.INSTALL,
    )
    assert any(_DISEASE_MODEL_NOTE in n for n in notes), notes


def test_a_knock_out_is_not_told_it_is_installing() -> None:
    """`KNOCK_OUT` reaches the same `elif`, and writes no allele at all."""
    notes = _clinical_notes(
        _resolved(assertion=ClinicalAssertion(significance=ClinicalSignificance.PATHOGENIC)),
        EditIntent.KNOCK_OUT,
    )
    assert not any(_DISEASE_MODEL_NOTE in n for n in notes), notes


@pytest.mark.parametrize(
    "significance",
    [ClinicalSignificance.BENIGN, ClinicalSignificance.UNCERTAIN],
)
def test_installing_an_allele_that_is_not_pathogenic_is_not_a_disease_model(
    significance: ClinicalSignificance,
) -> None:
    notes = _clinical_notes(
        _resolved(assertion=ClinicalAssertion(significance=significance)),
        EditIntent.INSTALL,
    )
    assert not any(_DISEASE_MODEL_NOTE in n for n in notes), notes
