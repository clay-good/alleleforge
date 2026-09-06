"""A supplied cell context that a chemistry cannot consider must be declared.

`cell_context` is taken by the prime vertical alone. `design_cas9` and
`design_base_editor` have no such parameter, so for those chemistries a supplied
context is never examined. Nothing said so, and the reports positively asserted the
opposite -- with a context no scorer recognizes:

    prime          -> ood flag, in_distribution=False
    cas9_nuclease  -> no flag,  in_distribution=True
    base_abe       -> no flag,  in_distribution=True

Those two `True`s are truthful about what they measure: `context_in_distribution`
checks the *guide* context (no ambiguous base, long enough for the head to read), and
it is never hardcoded. That is exactly what makes it misleading. A reader who asked for
K562 sees `in_distribution: True` beside a nuclease candidate -- a column a pipeline
filters on -- and reads it as a statement about K562. It is not one.

The fix is a declaration, not an invented OOD check: fabricating a cell-context
distribution for scorers that have none would be worse than the silence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent

#: One scenario per vertical: contig, variant, intent, and the chemistry it must yield.
SCENARIOS: dict[str, tuple[str, str, EditIntent, Chemistry]] = {
    "cas9_nuclease": (
        "T" * 20 + "ACGTAACGTTACGTAACGTT" + "TGG" + "T" * 20,
        "chr2:26:A>G",
        EditIntent.KNOCK_OUT,
        Chemistry.CAS9_NUCLEASE,
    ),
    "base_editor": (
        "T" * 20 + "TTTAAACGTTTTTTTTTTTT" + "TGG" + "T" * 20,
        "chr2:26:A>G",
        EditIntent.INSTALL,
        Chemistry.BASE_ABE,
    ),
}


def _prime_contig() -> str:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    return "".join(seq)


def _menu(tmp_path: Path, key: str, **kwargs: object) -> RankedMenu:
    contig, variant, intent, _ = SCENARIOS[key]
    fasta = tmp_path / f"{key}.fa"
    fasta.write_text(">chr2\n" + contig + "\n")
    return design(variant, reference=ReferenceGenome(fasta, build="hg38"), intent=intent, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_the_fixture_produces_the_vertical_it_claims(tmp_path: Path, key: str) -> None:
    """Guard the guard: a scenario yielding nothing would test nothing."""
    produced = {c.chemistry for c in _menu(tmp_path, key).candidates}
    assert SCENARIOS[key][3] in produced, f"got {produced}"


@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_a_chemistry_that_cannot_use_the_context_says_so(tmp_path: Path, key: str) -> None:
    menu = _menu(tmp_path, key, cell_context="K562")
    assert "cell context 'K562' was supplied" in menu.rationale
    assert SCENARIOS[key][3].value in menu.rationale


@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_no_note_when_no_context_was_supplied(tmp_path: Path, key: str) -> None:
    """A caveat that fires always is a caveat nobody reads."""
    assert "was supplied but is only consumed by" not in _menu(tmp_path, key).rationale


def test_prime_consumes_the_context_and_raises_no_note(tmp_path: Path) -> None:
    """The premise: prime really does examine it, so it needs no disclaimer."""
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + _prime_contig() + "\n")
    reference = ReferenceGenome(fasta, build="hg38")

    odd = design(
        "chr2:71:A>C",
        reference=reference,
        intent=EditIntent.CORRECT,
        cell_context="not-a-real-cell-line",
    )
    assert "ood" in odd.candidates[0].flags
    assert odd.candidates[0].efficiency is not None
    assert odd.candidates[0].efficiency.in_distribution is False
    # ...and prime alone means no "not considered" note is warranted.
    assert "was supplied but is only consumed by" not in odd.rationale


@pytest.mark.parametrize("key", sorted(SCENARIOS))
def test_the_unexamined_axis_is_the_reason_the_note_exists(tmp_path: Path, key: str) -> None:
    """Pin the misleading state itself, so a future OOD check makes this test fail loudly.

    If a cell-context distribution is ever wired into these scorers, `in_distribution`
    stops being True here and this test fails -- which is the right moment to revisit
    the note rather than leave it describing something no longer true.
    """
    menu = _menu(tmp_path, key, cell_context="not-a-real-cell-line")
    candidate = menu.candidates[0]
    assert candidate.efficiency is not None
    assert candidate.efficiency.in_distribution is True
    assert "ood" not in candidate.flags
    assert "was supplied but is only consumed by" in menu.rationale
