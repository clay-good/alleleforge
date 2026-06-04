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


def test_tsv_cells_have_no_tabs_or_newlines(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    body = report_to_tsv(report).strip().split("\n")[1:]
    for row in body:
        for cell in row.split("\t"):
            assert "\n" not in cell


def test_parquet_export(prime_menu: RankedMenu, tmp_path: Path) -> None:
    pl = pytest.importorskip("polars")
    report = build_report(prime_menu)
    out = report_to_parquet(report, tmp_path / "menu.parquet")
    assert out.exists()
    frame = pl.read_parquet(out)
    assert frame.height == len(report.candidates)
    assert set(TSV_COLUMNS) <= set(frame.columns)
