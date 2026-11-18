"""The per-chemistry cap takes the first N, so what it keeps depends on the sort.

`design_cas9` sorts its candidates — highest efficiency first, then lowest worst-case
off-target — and *then* truncates to `max_candidates`. A statement-deletion sweep
removed the sort with the whole suite green, because the composite ranker downstream
re-orders whatever it is handed: the *order* of an uncapped menu is restored either way,
so every ordering assertion in the suite still passes.

What the ranker cannot restore is a candidate that was never returned. With the sort
gone the cap keeps the first N in enumeration order — which is genomic position — so a
run asking for the best three guides gets the three nearest the start of the window, and
the ranker dutifully orders those three. The result is correct about everything except
which guides it is about, and nothing downstream can tell.

Checked on the cap, not on the full menu: an uncapped menu contains the same candidates
in either case, which is exactly why the uncapped assertions could not see this.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.cas9 import design_cas9
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.variant.resolver import resolve


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _candidates(reference: ReferenceGenome, cap: int | None) -> list[object]:
    resolved = resolve("chr2:1050:G>A", reference=reference)
    return list(
        design_cas9(
            resolved,
            EditIntent.KNOCK_OUT,
            reference=reference,
            run_offtarget=False,
            max_candidates=cap,
        )
    )


def _efficiencies(candidates: list[object]) -> list[float]:
    return [c.efficiency.value for c in candidates]  # type: ignore[attr-defined]


def test_the_fixture_produces_more_candidates_than_the_cap(
    reference: ReferenceGenome,
) -> None:
    """The premise: without more candidates than the cap, a cap decides nothing."""
    assert len(_candidates(reference, None)) > 3


def test_the_uncapped_vertical_returns_them_best_first(reference: ReferenceGenome) -> None:
    efficiencies = _efficiencies(_candidates(reference, None))
    assert efficiencies == sorted(efficiencies, reverse=True), efficiencies


@pytest.mark.parametrize("cap", [1, 3])
def test_a_cap_keeps_the_best_ones_not_the_first_ones(reference: ReferenceGenome, cap: int) -> None:
    """The claim the sort exists for, and the one an uncapped menu cannot make."""
    everything = _efficiencies(_candidates(reference, None))
    kept = _efficiencies(_candidates(reference, cap))
    assert len(kept) == cap
    assert kept == sorted(everything, reverse=True)[:cap], (kept, everything[:5])
