"""Tests for chemistry, intent, and edit-outcome models."""

from __future__ import annotations

import pytest

from alleleforge.types.edit import (
    AlleleOutcome,
    Chemistry,
    EditIntent,
    EditOutcome,
    EditStrategy,
)
from alleleforge.types.variant import Variant


def test_chemistry_and_intent_values() -> None:
    assert Chemistry.PRIME.value == "prime"
    assert EditIntent.CORRECT.value == "correct"


def test_allele_outcome_probability_range() -> None:
    with pytest.raises(ValueError, match="not in"):
        AlleleOutcome(allele="A", probability=1.5)


def test_edit_outcome_complete_distribution() -> None:
    eo = EditOutcome(
        alleles=(
            AlleleOutcome(allele="ACGT", probability=0.7, is_intended=True),
            AlleleOutcome(allele="ACGA", probability=0.3),
        )
    )
    assert eo.p_intended == pytest.approx(0.7)
    assert eo.most_likely.allele == "ACGT"


def test_edit_outcome_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        EditOutcome(alleles=())


def test_edit_outcome_rejects_bad_sum_when_complete() -> None:
    with pytest.raises(ValueError, match="sum"):
        EditOutcome(
            alleles=(
                AlleleOutcome(allele="A", probability=0.3),
                AlleleOutcome(allele="C", probability=0.3),
            )
        )


def test_edit_outcome_partial_allows_undersum() -> None:
    eo = EditOutcome(
        alleles=(AlleleOutcome(allele="A", probability=0.4),),
        partial=True,
    )
    assert eo.p_intended == 0.0


def test_edit_outcome_partial_still_rejects_oversum() -> None:
    with pytest.raises(ValueError, match="> 1"):
        EditOutcome(
            alleles=(
                AlleleOutcome(allele="A", probability=0.7),
                AlleleOutcome(allele="C", probability=0.5),
            ),
            partial=True,
        )


def test_edit_strategy_binds_variant() -> None:
    v = Variant(chrom="c", pos=1, ref="A", alt="G")
    strat = EditStrategy(variant=v, chemistry=Chemistry.BASE_ABE, intent=EditIntent.CORRECT)
    assert strat.chemistry is Chemistry.BASE_ABE
    assert strat.variant.ref == "A"
