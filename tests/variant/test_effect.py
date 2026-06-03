"""Tests for the consequence model and the static effect predictor."""

from __future__ import annotations

from alleleforge.types.variant import Variant
from alleleforge.variant.effect import (
    Consequence,
    Impact,
    StaticEffectPredictor,
    VariantEffect,
    impact_of,
)


def test_impact_ordering_is_severity() -> None:
    assert Impact.HIGH > Impact.MODERATE > Impact.LOW > Impact.MODIFIER


def test_impact_of_known_consequences() -> None:
    assert impact_of(Consequence.STOP_GAINED) is Impact.HIGH
    assert impact_of(Consequence.MISSENSE) is Impact.MODERATE
    assert impact_of(Consequence.SYNONYMOUS) is Impact.LOW
    assert impact_of(Consequence.INTRON) is Impact.MODIFIER


def test_static_predictor_returns_registered_effect() -> None:
    var = Variant(chrom="chr2", pos=60099, ref="A", alt="T")
    effect = VariantEffect(consequence=Consequence.MISSENSE, impact=Impact.MODERATE, gene="HBB")
    predictor = StaticEffectPredictor()
    predictor.add(var, effect)
    assert predictor.predict(var).gene == "HBB"


def test_static_predictor_defaults_to_other() -> None:
    var = Variant(chrom="chr2", pos=1, ref="A", alt="G")
    effect = StaticEffectPredictor().predict(var, transcript="ENST1")
    assert effect.consequence is Consequence.OTHER
    assert effect.impact is Impact.MODIFIER
    assert effect.transcript == "ENST1"


def test_static_predictor_seeded_table() -> None:
    var = Variant(chrom="chr2", pos=10, ref="G", alt="A")
    table = {str(var): VariantEffect(consequence=Consequence.SPLICE_DONOR, impact=Impact.HIGH)}
    assert StaticEffectPredictor(table).predict(var).impact is Impact.HIGH
