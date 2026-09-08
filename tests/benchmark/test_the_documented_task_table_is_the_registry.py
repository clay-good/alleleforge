"""The benchmark's task table is hand-written in three documents and checked in none.

The same structural facts — the task's name, its kind, and the primary metric a model is
ranked on — appear in the README, the API reference and the preprint. Each was typed by
hand from `alleleforge.benchmark.tasks`, and nothing compared any of them to it.

This project has already learned what that costs, on the exit codes: the same fact written
down four times, with a guard on the one copy a *test* read and none on the two a *reader*
reads. And these numbers rank worse than exit codes on the scale that matters. A stale
`Spearman` where the harness ranks on `KL` is not a documentation nit; it is a false
statement about how models are compared, in the document written to be cited.

All three agree with the registry today, so this is preventive — and mutation-verified,
which is this project's standing obligation for a check that has never yet caught
anything: renaming a task, or swapping a primary metric, fails it in every document.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.benchmark.tasks import TASKS, get_task

_ROOT = Path(__file__).resolve().parents[2]

#: The documents that print the task table, and what each one is for.
_SURFACES = {
    "README.md": "the front door",
    "docs/api/benchmark.md": "the API reference",
    "docs/paper/preprint.md": "the citable write-up",
}

#: How each document spells a metric name. The registry's identifiers are lower-case;
#: prose capitalises them and marks the descending ones with an arrow.
_SPELLINGS = {
    "spearman": {"Spearman"},
    "kl": {"KL ↓", "KL divergence (↓)"},
    "auroc": {"AUROC"},
}


def _rows(document: str) -> dict[str, list[str]]:
    """Return `task -> cells` for every task row in ``document``'s table."""
    text = (_ROOT / document).read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = re.match(r"^\| `([\w-]+)` \|(.*)\|\s*$", line)
        if match and match.group(1) in TASKS:
            found[match.group(1)] = [c.strip() for c in match.group(2).split("|")]
    return found


@pytest.mark.parametrize("document", sorted(_SURFACES))
def test_the_document_lists_every_task(document: str) -> None:
    rows = _rows(document)
    assert set(rows) == set(TASKS), (
        f"{document} ({_SURFACES[document]}) lists {sorted(rows)}; the harness has "
        f"{sorted(TASKS)}. A task missing from a table is a task nobody knows to run; "
        "one that is listed and gone is a task nobody can."
    )


@pytest.mark.parametrize("document", sorted(_SURFACES))
def test_the_kind_and_primary_metric_match_the_registry(document: str) -> None:
    for name, cells in _rows(document).items():
        task = get_task(name)
        assert task.kind in cells, (
            f"{document} describes {name} as {cells[0]!r}; the registry says {task.kind!r}"
        )
        accepted = _SPELLINGS[task.primary_metric]
        assert accepted & set(cells), (
            f"{document} does not name {name}'s primary metric. The registry ranks it "
            f"on {task.primary_metric!r} (written as one of {sorted(accepted)}); the row "
            f"says {cells}. A table naming the wrong metric states the wrong ordering."
        )


def test_every_registry_metric_has_a_documented_spelling() -> None:
    """Guard the guard: a new primary metric must not silently pass every check above."""
    unknown = sorted({get_task(t).primary_metric for t in TASKS} - set(_SPELLINGS))
    assert not unknown, (
        f"the harness ranks on {unknown}, which no document is checked to spell. Add the "
        "prose form to _SPELLINGS once the tables carry it."
    )


def test_the_spellings_are_all_still_used() -> None:
    """...and an entry for a metric no task ranks on is a stale allowance."""
    stale = sorted(set(_SPELLINGS) - {get_task(t).primary_metric for t in TASKS})
    assert not stale, f"_SPELLINGS names metrics no task ranks on: {stale}"
