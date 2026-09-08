"""The browser's cohort table kept losing columns the other shells had gained.

Twice in three rounds a fact was added to the cohort summary row, reached the CLI's TSV
and `/api/batch`, and never reached the page: the resolved `variant`, then the ClinVar
`clinical_significance`. The page is the audience with no terminal to fall back to, and
it is the one whose table is hand-written HTML rather than generated from the row.

So this is the check, rather than another correction: every key `cohort_rows` produces is
either rendered by the page or excused with a reason. The row is the contract; the table
is one renderer of it, and a renderer that silently ignores a new field is how a
capability reaches three audiences out of four.
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")

#: Row keys the cohort table legitimately does not show, each with the reason.
_NOT_A_COLUMN: dict[str, str] = {
    "best_efficiency_low": "rendered inside the efficiency cell as the interval",
    "best_efficiency_high": "rendered inside the efficiency cell as the interval",
    "best_efficiency_in_distribution": "rendered inside the efficiency cell as the OOD flag",
    "chemistries": "the whole menu's chemistries; the table shows the recommended one, "
    "and the per-item report behind it lists the rest",
    "no_candidate_reason": "shown in the error cell's place for a row with no candidate, "
    "which the status column already distinguishes",
}


def _row_keys() -> set[str]:
    """Return the keys a cohort summary row carries, from the function that builds it.

    Read off `cohort_rows`, which is the row's actual contract, rather than off
    `_summarize` plus a guess at what the wrapper adds — the guess omitted `error`, and
    an approximation of the thing under test reports the difference as a defect.
    """
    from alleleforge.design.cohort_summary import cohort_rows

    source = __import__("inspect").getsource(cohort_rows)
    keys = set(re.findall(r'^\s{16}"(\w+)":', source, re.M))
    assert len(keys) > 8, f"parsed {keys} from cohort_rows — this check would be vacuous"
    return keys


def _rendered_by_the_table() -> set[str]:
    """Return the summary keys `renderBatch` reads."""
    match = re.search(r"function renderBatch\((?:.|\n)*?\n\}", _APP_JS)
    assert match, "could not find renderBatch() — this check would be vacuous"
    body = match.group(0)
    return set(re.findall(r"\bs\.(\w+)", body)) | set(re.findall(r"\bit\.(\w+)", body))


def test_the_table_renders_every_fact_the_row_carries() -> None:
    missing = sorted(_row_keys() - _rendered_by_the_table() - set(_NOT_A_COLUMN))
    assert not missing, (
        f"the cohort row carries {missing} and the page's table does not read them. Add "
        "a column, or record each in _NOT_A_COLUMN with the reason it is not one."
    )


def test_the_allowances_name_real_row_keys() -> None:
    """An excuse must not outlive the field it excuses."""
    stale = sorted(set(_NOT_A_COLUMN) - _row_keys())
    assert not stale, f"_NOT_A_COLUMN names keys a cohort row no longer has: {stale}"


def test_the_header_and_the_cells_stay_the_same_width() -> None:
    """A column added to one and not the other shifts every heading after it."""
    header = re.findall(r"<th>([^<]*)</th>", _APP_JS)
    row = re.search(r'return `<tr class="\$\{it\.status\}">(.*?)</tr>`', _APP_JS, re.S)
    assert row, "could not find the cohort row template"
    leading = len(re.findall(r"<td>", row.group(1)))
    detail = re.search(r"\? `(<td>.*?)`\n", _APP_JS, re.S)
    assert detail, "could not find the detail cells"
    assert leading + len(re.findall(r"<td>", detail.group(1))) == len(header), (
        leading,
        len(header),
    )


def _tsv_columns() -> list[str]:
    """Return the TSV's column list, in order, from the writer that emits it."""
    from alleleforge.design import cohort_summary

    source = __import__("inspect").getsource(cohort_summary.cohort_to_tsv)
    cols = re.findall(r'^\s{8}"(\w+)",', source, re.M)
    assert len(cols) > 8, f"parsed {cols} — this check would be vacuous"
    return cols


def test_the_tsv_writes_every_fact_the_row_carries() -> None:
    """The same rule one layer down, where the column list is also hand-written.

    `cohort_to_tsv` keeps an explicit `cols` list, so a key added to the row and not to
    it is dropped from the file in silence — which is how `chemistries` came to be
    available to a Python caller and absent from the artifact the run is read through.
    """
    missing = sorted(set(_row_keys()) - set(_tsv_columns()))
    assert not missing, (
        f"the cohort row carries {missing} and the TSV has no column for them. A key on "
        "the row that the file drops is a fact a Python caller has and a reader does not."
    )


def test_the_tsv_has_no_column_the_row_cannot_fill() -> None:
    """The other direction: a column whose key nothing produces is an always-empty cell."""
    orphan = sorted(set(_tsv_columns()) - set(_row_keys()))
    assert not orphan, f"the TSV writes columns no cohort row carries: {orphan}"
