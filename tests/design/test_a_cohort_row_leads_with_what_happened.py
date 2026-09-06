"""A cohort row for an empty menu buried the one sentence about that variant.

Found by running `aforge batch` over a five-line cohort and reading the output. The row
for a no-op input — reference and alternate alleles identical — read:

    chr2:1200:A>A  ok  best=-  eff=-  n=0  — base_abe: Adenine base editing installs an
    A->G / T->C transition in a narrow window with no double-strand break — the cleanest
    fix when ... | base_cbe: ... | cas9_nuclease: ... | prime: eligible but no actionable
    candidate enumerated — the requested edit does not change the sequence ...

Three definitions of what a chemistry is *for*, and then, 700 characters in, the one
sentence about what is wrong with this input. `_decline_reason` collected every `- `
bullet in rationale order, and routing rationales are written first because the report
reads top-down while a cohort row is scanned left to right.

Both blocks are kept — a cohort row is often the only thing a reader sees for that
variant — but the run notes lead. They became separable when the rationale gained its own
heading for them.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.cohort import _decline_reason
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_the_run_note_leads_the_reason(reference: ReferenceGenome) -> None:
    menu = design("chr2:1200:A>A", reference=reference, run_offtarget=False)
    assert not menu.candidates, "the fixture must produce an empty menu"
    reason = _decline_reason(menu)
    assert reason is not None
    assert reason.startswith("prime: eligible but no actionable candidate")
    assert "does not change the sequence" in reason.split(" | ")[0]


def test_nothing_is_dropped(reference: ReferenceGenome) -> None:
    """Reordered, not filtered: every bullet in the rationale still reaches the row."""
    menu = design("chr2:1200:A>A", reference=reference, run_offtarget=False)
    bullets = [
        line.strip().removeprefix("- ").strip()
        for line in menu.rationale.splitlines()
        if line.strip().startswith("- ")
    ]
    reason = _decline_reason(menu)
    assert reason is not None
    assert sorted(reason.split(" | ")) == sorted(bullets)


def test_a_menu_with_no_rationale_has_no_reason() -> None:
    from alleleforge.types.candidate import RankedMenu

    assert _decline_reason(RankedMenu(candidates=(), rationale="")) is None
