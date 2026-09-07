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
