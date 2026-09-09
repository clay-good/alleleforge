"""Thirty percent of the ranking weight was a constant, and the rationale did not say so.

`_safety` gives a candidate with no off-target report a full `1.0` — "the reassuring
extreme for an axis nobody measured" — deliberately, because choosing a penalty for an
unmeasured axis is a policy this project has no basis for, and every vertical flags such a
candidate `offtarget-not-searched`.

That is the right choice about the *number*. What was missing was the consequence for the
*ordering*: run with `--no-offtarget` and every candidate takes the same maximum on
safety, so its 0.30 weight cannot separate any two of them and the order is decided
entirely by efficiency, cleanliness and simplicity. The rationale meanwhile said "the
safety term uses the worst nominated site" — describing a computation that did not happen,
in the sentence a reader consults to learn what the ranking means.

The tell was in the same sentence: it already qualified the *lesser* version of this ("no
candidate here carries ancestry annotation, so there is no per-ancestry worst to take")
while stating the larger one as fact.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.resolver import resolve


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(29)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(6_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _variant(reference: ReferenceGenome) -> str:
    bases = "".join(Path(reference.path).read_text().split("\n")[1:])
    base = bases[2999]
    return f"chr1:3000:{base}>{'A' if base != 'A' else 'G'}"


def test_an_unsearched_menu_says_the_safety_weight_separated_nothing(
    reference: ReferenceGenome,
) -> None:
    menu = design(
        resolve(_variant(reference), reference=reference), reference=reference, run_offtarget=False
    )
    assert menu.candidates, "no candidates; this check would be vacuous"
    assert all(c.offtarget is None for c in menu.candidates)

    rationale = menu.rationale
    assert "no off-target search was run" in rationale, rationale
    assert "separates none of them" in rationale, rationale
    assert "offtarget-not-searched" in rationale, rationale
    # And it must not describe the computation it did not do.
    assert "uses the worst nominated site" not in rationale, rationale


def test_a_searched_menu_still_describes_the_term_it_used(reference: ReferenceGenome) -> None:
    """The floor: the new clause must not swallow the ordinary case."""
    menu = design(resolve(_variant(reference), reference=reference), reference=reference)
    assert menu.candidates
    assert any(c.offtarget is not None for c in menu.candidates)

    rationale = menu.rationale
    assert "no off-target search was run" not in rationale, rationale
    assert "the safety term uses" in rationale, rationale


def test_the_candidates_still_carry_the_flag(reference: ReferenceGenome) -> None:
    """The per-candidate half of the disclosure, which the rationale now points at."""
    menu = design(
        resolve(_variant(reference), reference=reference), reference=reference, run_offtarget=False
    )
    assert all("offtarget-not-searched" in c.flags for c in menu.candidates)
