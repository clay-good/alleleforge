"""Tests for the Phase 11 machine-readable exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.export import (
    TSV_COLUMNS,
    menu_to_json,
    report_to_json,
    report_to_parquet,
    report_to_tsv,
)
from alleleforge.types.candidate import RankedMenu


def test_menu_json_validates_against_phase1_schema(prime_menu: RankedMenu) -> None:
    # The menu round-trips through its own Phase 1 pydantic schema.
    text = menu_to_json(prime_menu)
    restored = RankedMenu.model_validate_json(text)
    assert restored == prime_menu


def test_report_json_is_valid_json(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    data = json.loads(report_to_json(report))
    assert data["disclaimer"]
    assert len(data["candidates"]) == len(prime_menu.candidates)


def test_tsv_has_header_and_one_row_per_candidate(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    lines = report_to_tsv(report).strip().split("\n")
    assert lines[0].split("\t") == list(TSV_COLUMNS)
    assert len(lines) == len(report.candidates) + 1
    # every data row has exactly the right number of columns
    for row in lines[1:]:
        assert len(row.split("\t")) == len(TSV_COLUMNS)


def test_tsv_carries_calibrated_column(prime_menu: RankedMenu) -> None:
    # The flat export exposes in_distribution but had no calibrated column, so a
    # machine consumer could not tell a calibrated band from a nominal heuristic one.
    # Default scorers are uncalibrated, so the column reads False (not blank).
    report = build_report(prime_menu)
    lines = report_to_tsv(report).strip().split("\n")
    header = lines[0].split("\t")
    assert "calibrated" in header
    col = header.index("calibrated")
    scored = [r.split("\t") for r in lines[1:] if r.split("\t")[header.index("efficiency")]]
    assert scored, "fixture should have at least one scored candidate"
    for row in scored:
        assert row[col] == "False"


def test_tsv_cells_have_no_tabs_or_newlines(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    body = report_to_tsv(report).strip().split("\n")[1:]
    for row in body:
        for cell in row.split("\t"):
            assert "\n" not in cell and "\r" not in cell


def test_tsv_cell_neutralizes_every_delimiter() -> None:
    # A user-influenced cell (ancestry label, flags) must not smuggle a row/column
    # break into the TSV. A bare \r is a line separator to Excel and csv.reader, so
    # it must be neutralized alongside \t and \n — the sibling batch emitter already
    # does, and dropping it broke one logical row into several physical lines.
    from alleleforge.report.export import _cell

    for raw in ("a\tb", "a\nb", "a\rb", "a\r\nb", "EUR\rINJECT\tcol"):
        out = _cell(raw)
        assert "\t" not in out and "\n" not in out and "\r" not in out


def test_parquet_export(prime_menu: RankedMenu, tmp_path: Path) -> None:
    pl = pytest.importorskip("polars")
    report = build_report(prime_menu)
    out = report_to_parquet(report, tmp_path / "menu.parquet")
    assert out.exists()
    frame = pl.read_parquet(out)
    assert frame.height == len(report.candidates)
    assert set(TSV_COLUMNS) <= set(frame.columns)


def test_tsv_export_carries_schema_version(prime_menu: RankedMenu) -> None:
    from alleleforge.report.builder import build_report
    from alleleforge.report.export import EXPORT_SCHEMA_VERSION, report_to_tsv

    report = build_report(prime_menu)
    lines = report_to_tsv(report).strip().splitlines()
    assert lines[0].split("\t")[0] == "schema_version"
    # every data row carries the current export schema version in the first column
    for row in lines[1:]:
        assert row.split("\t")[0] == str(EXPORT_SCHEMA_VERSION)
