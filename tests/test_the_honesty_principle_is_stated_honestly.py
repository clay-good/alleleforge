"""The honesty principle claimed every prediction ships with a *calibrated* interval.

Out of the box, none does. The weight-free defaults are heuristics: a design over a
200-candidate menu reports `calibrated=False` on every efficiency and every `p_intended`,
with `method=heuristic`, and that is the correct behaviour — `calibrated` exists precisely
so a scorer can say it has not fitted its interval against held-out coverage. Conformal
recalibration and the trained models are what set it true.

So `SPEC.md`'s principle 2 and `CONTRIBUTING.md`'s bullet — the two places a contributor
learns what the project means by honesty — asserted the one thing the flag exists to deny.
An interval *asserted* to be calibrated when it is not is the confident wrong answer
wearing the honest one's clothes, which is the failure mode the principle is written
against.

The guard is derived from a real run: while the shipped default emits `calibrated=False`,
no document may claim predictions come calibrated without naming the flag.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.resolver import resolve
from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]

#: Claims that a prediction arrives already calibrated.
_CLAIMS = re.compile(
    r"ships with a calibrated interval|carries a calibrated interval"
    r"|every numeric prediction (ships|carries) with a calibrated",
    re.I,
)


@pytest.fixture
def menu(tmp_path: Path):  # type: ignore[no-untyped-def]
    rng = random.Random(41)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(6_000)) + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    bases = "".join(fasta.read_text().split("\n")[1:])
    base = bases[2999]
    variant = f"chr1:3000:{base}>{'A' if base != 'A' else 'G'}"
    return design(resolve(variant, reference=reference), reference=reference, run_offtarget=False)


def test_the_shipped_default_is_not_calibrated(menu) -> None:  # type: ignore[no-untyped-def]
    """The premise, from a real run rather than from the docstrings."""
    assert menu.candidates, "no candidates; this check would be vacuous"
    calibrated = {c.efficiency.calibrated for c in menu.candidates if c.efficiency}
    assert calibrated == {False}, calibrated
    methods = {c.efficiency.method.value for c in menu.candidates if c.efficiency}
    assert methods == {"heuristic"}, methods


def test_every_prediction_still_carries_an_interval(menu) -> None:  # type: ignore[no-untyped-def]
    """The half of the principle that *is* true, and must stay true."""
    scored = [c for c in menu.candidates if c.efficiency is not None]
    assert scored, "no scored candidate; this check would be vacuous"
    for candidate in scored:
        low, high = candidate.efficiency.interval
        assert low <= candidate.efficiency.value <= high, candidate.efficiency


def test_no_document_says_predictions_arrive_calibrated() -> None:
    offenders: list[str] = []
    for path in _prose_files():
        for match in _CLAIMS.finditer(prose_text(path)):
            offenders.append(f"{path.relative_to(_ROOT)}: {match.group(0)!r}")
    assert not offenders, (
        "the shipped default reports `calibrated=False` on every prediction — the flag "
        f"exists to say so — and these documents claim otherwise: {offenders}"
    )


def test_the_principle_names_the_flag() -> None:
    """Not claiming the wrong thing is half of it."""
    for name in ("SPEC.md", "CONTRIBUTING.md"):
        text = (_ROOT / name).read_text(encoding="utf-8")
        principle = next(
            block for block in re.split(r"\n\s*\n", text) if "Honest uncertainty" in block
        )
        assert "calibrated=False" in principle or "`calibrated` flag" in principle, (
            name,
            principle,
        )
