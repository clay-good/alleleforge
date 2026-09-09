"""Three empty safety columns look the same whether nothing was found or nothing was run.

`aforge batch --no-offtarget` writes a per-patient table whose `worst_offtarget`,
`best_specificity` and `offtarget_sources` cells are all blank. Each cell is honest — a
search that did not happen must not report `0.0` and `1.000`, and it does not — and the
file as a whole is not: a collaborator opening it sees empty safety columns across every
row and has nothing to tell them why.

That is what the `#` note block is for. It already carries the reference genome, the
coordinate convention, the seed, the intent and the datasets, on the stated grounds that
"a row per patient with a bare `best_specificity` and no statement of which genome was
searched is not interpretable". Whether the genome was searched *at all* belongs in the
same block, and the rows already carry the answer: `offtarget_sources` is `None` when no
report exists and `"reference-only"` when one does with no optional source.

The mixed case gets its own sentence, because "some of these rows were searched" is a
different fact from either extreme, and the partial case is the one this project has
repeatedly found unhandled after the total one was.
"""

from __future__ import annotations

from typing import Any

from alleleforge.design.cohort_summary import COHORT_COLUMNS, cohort_to_tsv


def _row(item_id: str, *, searched: bool, status: str = "ok") -> dict[str, Any]:
    blank = dict.fromkeys(COHORT_COLUMNS)
    return blank | {
        "item_id": item_id,
        "status": status,
        "variant": "chr1:1:A>T",
        "best_chemistry": "prime",
        "offtarget_sources": {} if searched else None,
        "best_specificity": 0.9 if searched else None,
    }


def _notes(rows: list[dict[str, Any]]) -> list[str]:
    return [line[2:] for line in cohort_to_tsv(rows, {}).splitlines() if line.startswith("#")]


def test_a_wholly_unsearched_cohort_says_so() -> None:
    notes = _notes([_row("a", searched=False), _row("b", searched=False)])
    assert any("no off-target search was run for any item" in note for note in notes), notes
    assert any("not because nothing was found" in note for note in notes), notes


def test_a_searched_cohort_says_nothing_extra() -> None:
    """The floor: the note must not appear on the ordinary run."""
    notes = _notes([_row("a", searched=True), _row("b", searched=True)])
    assert not any("no off-target search" in note for note in notes), notes


def test_a_partly_searched_cohort_counts_them() -> None:
    notes = _notes([_row("a", searched=True), _row("b", searched=False), _row("c", searched=False)])
    assert any("2 of 3 designed item(s) had no off-target search" in note for note in notes), notes


def test_a_failed_item_is_not_an_unsearched_one() -> None:
    """A failed item has no off-target columns either, and for a different reason.

    Counting it as unsearched would report a search that did not happen for an item that
    never got as far as one, and would make a cohort of one failure read as a cohort that
    was never searched.
    """
    notes = _notes([_row("a", searched=True), _row("b", searched=False, status="error")])
    assert not any("no off-target search was run for any item" in note for note in notes), notes
    assert not any("had no off-target search" in note for note in notes), notes
