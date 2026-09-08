"""The typed flat table must not infer its types from the first hundred rows.

`pl.DataFrame(rows)` reads `infer_schema_length` (100) rows to decide each dtype. On
a real menu the first hundred are not representative: `bystander_burden` is null for
every prime candidate and a float on the one base editor, which ranks last. A
341-candidate design — an ordinary mixed-chemistry run — died with

    polars.exceptions.ComputeError: could not append value: 0.36 of type: f64 to
    the builder; make sure that all rows have the same schema

on `aforge design --format parquet` and on `POST /api/design?format=parquet`, both
documented as handing a pipeline the same table the TSV holds.

Inference is wrong even when it succeeds: a run with no population data leaves
`worst_ancestry` null in every row and gets a Null dtype for it, while the same tool
with a gnomAD file writes a string column — two files a pipeline cannot union. And
the empty frame was built from a separate expression, so a report with no candidates
wrote every column as Null.

`TSV_COLUMN_TYPES` declares them once, for the populated and the empty frame alike.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from alleleforge.report.builder import DesignReport, build_report
from alleleforge.report.export import (
    TSV_COLUMN_TYPES,
    TSV_COLUMNS,
    report_to_parquet,
    report_to_tsv,
)
from alleleforge.types.candidate import RankedMenu

_DTYPES: dict[type, pl.DataType] = {
    bool: pl.Boolean,
    int: pl.Int64,
    float: pl.Float64,
    str: pl.Utf8,
}


def _padded(prime: RankedMenu, abe: RankedMenu, *, nulls: int) -> DesignReport:
    """A report of `nulls` prime rows (null burden) then one base-editor row.

    The real 341-row menu in the same shape, shrunk to the part that matters: the
    float that ends the column arrives past polars' 100-row inference window.
    """
    prime_report, abe_report = build_report(prime), build_report(abe)
    assert prime_report.candidates[0].bystander_burden is None
    assert abe_report.candidates[0].bystander_burden is not None
    rows = [prime_report.candidates[0]] * nulls + [abe_report.candidates[0]]
    return prime_report.model_copy(update={"candidates": tuple(rows)})


def test_every_column_has_a_declared_type() -> None:
    assert len(TSV_COLUMNS) > 30, TSV_COLUMNS
    assert set(TSV_COLUMN_TYPES) == set(TSV_COLUMNS), sorted(
        set(TSV_COLUMN_TYPES) ^ set(TSV_COLUMNS)
    )
    assert set(TSV_COLUMN_TYPES.values()) <= set(_DTYPES), TSV_COLUMN_TYPES


def test_a_column_null_past_the_inference_window_still_holds_its_values(
    tmp_path: Path, prime_menu: RankedMenu, abe_menu: RankedMenu
) -> None:
    report = _padded(prime_menu, abe_menu, nulls=140)
    frame = pl.read_parquet(report_to_parquet(report, tmp_path / "r.parquet"))
    assert frame.height == 141
    assert frame["bystander_burden"].dtype == pl.Float64
    assert frame["bystander_burden"].null_count() == 140
    assert frame["bystander_burden"].max() is not None


def test_a_column_null_in_every_row_keeps_its_declared_type(
    tmp_path: Path, prime_menu: RankedMenu
) -> None:
    """A run with no population data must not write a Null column."""
    frame = pl.read_parquet(report_to_parquet(build_report(prime_menu), tmp_path / "r.parquet"))
    assert frame["worst_ancestry"].null_count() == frame.height
    assert frame["worst_ancestry"].dtype == pl.Utf8
    assert frame["worst_ancestry_score"].dtype == pl.Float64


def test_an_empty_report_writes_the_same_schema_as_a_populated_one(
    tmp_path: Path, prime_menu: RankedMenu
) -> None:
    populated = build_report(prime_menu)
    empty = populated.model_copy(update={"candidates": ()})
    written_full = pl.read_parquet(report_to_parquet(populated, tmp_path / "a.parquet"))
    written_empty = pl.read_parquet(report_to_parquet(empty, tmp_path / "b.parquet"))
    assert written_empty.height == 0
    assert dict(zip(written_empty.columns, written_empty.dtypes, strict=True)) == dict(
        zip(written_full.columns, written_full.dtypes, strict=True)
    )


def test_the_declared_types_are_the_ones_the_data_carries(
    tmp_path: Path, prime_menu: RankedMenu, abe_menu: RankedMenu
) -> None:
    """The declaration is checked against real rows, not trusted."""
    report = _padded(prime_menu, abe_menu, nulls=2)
    frame = pl.read_parquet(report_to_parquet(report, tmp_path / "r.parquet"))
    for column, python_type in TSV_COLUMN_TYPES.items():
        assert frame[column].dtype == _DTYPES[python_type], column


def test_the_tsv_cell_is_unchanged(prime_menu: RankedMenu) -> None:
    """`offtarget_expected_burden` moved from `""` to `None`; the TSV is the same."""
    lines = report_to_tsv(build_report(prime_menu)).splitlines()
    header = next(line for line in lines if line.startswith("schema_version\t"))
    first = lines[lines.index(header) + 1]
    columns = header.split("\t")
    assert first.split("\t")[columns.index("offtarget_expected_burden")] == ""


@pytest.mark.parametrize("column", ["bystander_burden", "worst_ancestry"])
def test_inference_would_have_gotten_these_wrong(
    column: str, prime_menu: RankedMenu, abe_menu: RankedMenu
) -> None:
    """Guard the guard: these columns really are all-null in the leading rows."""
    from alleleforge.report.export import _row

    report = _padded(prime_menu, abe_menu, nulls=140)
    leading = [_row(candidate)[column] for candidate in report.candidates[:100]]
    assert set(leading) == {None}, leading[:3]
