"""The TSV and the Parquet are documented as the same table. Column *order* counts.

`docs/api/cli.md`: "The columns are identical to the TSV's." The TSV projects each row
onto `TSV_COLUMNS`; the Parquet writer handed polars a list of dicts and took whatever
order `_row` happened to build. They had already drifted by one adjacent swap:

    TSV      ... offtarget_specificity  offtarget_expected_burden ...
    Parquet  ... offtarget_expected_burden  offtarget_specificity ...

A named-column reader never notices. A positional one — `frame[:, 17]`, a `polars`
`select(pl.nth(17))`, an R `df[[18]]` — reads a specificity where the sibling table
holds an expected burden, two numbers on unrelated scales, silently.

The guard that existed asked `set(TSV_COLUMNS) <= set(frame.columns)`: a subset of a
set, which is true under any permutation and would also be true if Parquet grew extra
columns. Both halves are now pinned as sequences, including the empty case — which was
built from `TSV_COLUMNS` directly and so had a *different* order from a populated file
written by the same function.

Order was all that was pinned. "The same table" is also a claim about the *cells*, and
the two writers reach them differently: Parquet writes `_row`'s typed values, while the
TSV puts each through `_cell`, which renders `None` as `""` and flattens tabs and
newlines to spaces. A change there is a change to one table and not the other, and this
project has already shipped that exact defect once — rendering empty collections as
empty cells collapsed "searched, no optional source" into "never searched", two
different facts in one blank. Every column-order test stays green through it. So the
cells are compared too, with the null rule stated rather than assumed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.export import TSV_COLUMNS, report_to_parquet, report_to_tsv
from alleleforge.types.candidate import RankedMenu


def _tsv_header(report: object) -> list[str]:
    lines = [line for line in report_to_tsv(report).splitlines() if not line.startswith("#")]
    return lines[0].split("\t")


def _frame(report: object, tmp_path: Path) -> object:
    """Return the written Parquet as a polars frame, skipping if polars is absent."""
    pl = pytest.importorskip("polars")
    return pl.read_parquet(report_to_parquet(report, tmp_path / "menu.parquet"))


def test_the_tsv_header_is_the_declared_column_order(prime_menu: RankedMenu) -> None:
    assert _tsv_header(build_report(prime_menu)) == list(TSV_COLUMNS)


def test_the_parquet_columns_are_the_tsv_columns_in_order(
    prime_menu: RankedMenu, tmp_path: Path
) -> None:
    pl = pytest.importorskip("polars")
    report = build_report(prime_menu)
    frame = pl.read_parquet(report_to_parquet(report, tmp_path / "menu.parquet"))
    assert frame.height > 0, "an empty table would pass this vacuously"
    assert frame.columns == _tsv_header(report)


def test_an_empty_parquet_has_the_same_columns_as_a_populated_one(
    prime_menu: RankedMenu, tmp_path: Path
) -> None:
    """The two branches of one writer must not disagree about the schema."""
    pl = pytest.importorskip("polars")
    populated = pl.read_parquet(
        report_to_parquet(build_report(prime_menu), tmp_path / "full.parquet")
    )
    empty_menu = prime_menu.model_copy(update={"candidates": (), "pareto_front": ()})
    empty = pl.read_parquet(report_to_parquet(build_report(empty_menu), tmp_path / "empty.parquet"))
    assert empty.height == 0
    assert empty.columns == populated.columns


def _tsv_rows(report: object) -> tuple[list[str], list[list[str]]]:
    """Return ``(header, data rows)`` from the TSV, skipping its `#` note block."""
    lines = [line for line in report_to_tsv(report).splitlines() if not line.startswith("#")]
    return lines[0].split("\t"), [line.split("\t") for line in lines[1:]]


def test_the_two_tables_hold_the_same_cells(prime_menu: RankedMenu, tmp_path: Path) -> None:
    """Same columns *and* same values — the second half of "the same table".

    The correspondence is exact, not approximate: a Parquet null is the TSV's empty
    string and nothing else is, so a writer that started rendering an absent value as
    `0`, `"None"` or `"-"` in one table and not the other fails here. That collapse is
    the defect this project has already shipped once, in a different pair of surfaces.
    """
    report = build_report(prime_menu)
    frame = _frame(report, tmp_path)
    header, rows = _tsv_rows(report)
    assert rows, "the fixture wrote no data rows; this check would be vacuous"
    assert frame.height == len(rows), (frame.height, len(rows))

    differences: list[str] = []
    for index, row in enumerate(rows):
        for column, text in zip(header, row, strict=True):
            value = frame[column][index]
            if value is None:
                matches = text == ""
            elif isinstance(value, bool):
                matches = text == str(value)
            elif isinstance(value, float):
                matches = text != "" and float(text) == pytest.approx(value)
            else:
                matches = text == str(value)
            if not matches:
                differences.append(f"row {index} {column}: tsv={text!r} parquet={value!r}")
    assert not differences, differences[:8]


def test_the_tsv_leaves_a_cell_empty_exactly_when_parquet_has_nothing_to_show(
    prime_menu: RankedMenu, tmp_path: Path
) -> None:
    """The rule the comparison above rests on, checked in both directions.

    Without it the comparison could pass while every cell was blank in one table and
    null in the other — agreement about nothing.

    "Nothing to show" is two states, not one, and the TSV renders both as an empty cell:
    a **null** (`worst_ancestry` on a candidate with no ancestry annotation — the axis
    was not measured) and an **empty string** (`oligo_warnings` when a screen ran and
    raised none). Parquet keeps them apart; TSV cannot, and this is where that is said
    out loud. Both states must be present in the fixture, or the test is asserting a
    rule over a case it never sees.
    """
    report = build_report(prime_menu)
    frame = _frame(report, tmp_path)
    header, rows = _tsv_rows(report)
    nulls = empties = 0
    for index, row in enumerate(rows):
        for column, text in zip(header, row, strict=True):
            value = frame[column][index]
            assert (text == "") == (value is None or value == ""), (index, column, text, value)
            nulls += value is None
            empties += value == ""
    assert nulls, "no null in the fixture; the absent-value half of the rule is untested"
    assert empties, "no empty string in the fixture; the other half is untested"


def test_the_parquet_keeps_a_distinction_the_tsv_cannot(
    prime_menu: RankedMenu, tmp_path: Path
) -> None:
    """What the columnar table is *for*: an absent measurement and a measured nothing
    are one blank in the TSV and two different values here."""
    frame = _frame(build_report(prime_menu), tmp_path)
    values = {column: frame[column][0] for column in frame.columns}
    assert any(v is None for v in values.values()), values
    assert any(v == "" for v in values.values()), values
