"""The Parquet export must carry the notes the TSV carries as `#` comments.

The flat table grew a leading `#` note block in schema v6 for a stated reason: the
HTML, the PDF and the JSON all carry the research-use disclaimer, the reference build
and the coordinate convention, and the TSV — the one surface a result gets forwarded in
— carried none of them, showing efficiencies, specificities and genomic loci with
nothing saying they are uncertain computational predictions, against which genome, in
which coordinate convention.

Parquet holds exactly the same columns and is the format a *batch* consumer reads. It
had no channel for those notes at all, because Parquet has no comment lines. The fix is
the one Parquet provides: file-level key/value metadata. These tests pin both halves —
that the notes are there, and that they are the same notes, since two independently
assembled lists are two lists that drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.export import report_to_parquet, report_to_tsv
from alleleforge.types.candidate import RankedMenu


def _parquet_notes(pl: object, path: Path) -> dict[str, str]:
    """Return the file's key/value metadata, minus Arrow's own schema entry."""
    raw = pl.read_parquet_metadata(path)  # type: ignore[attr-defined]
    return {key: value for key, value in raw.items() if not key.startswith("ARROW:")}


def test_parquet_carries_the_disclaimer_and_provenance(
    prime_menu: RankedMenu, tmp_path: Path
) -> None:
    pl = pytest.importorskip("polars")
    report = build_report(prime_menu)
    notes = _parquet_notes(pl, report_to_parquet(report, tmp_path / "menu.parquet"))

    assert "research" in notes["disclaimer"].lower()
    provenance = " ".join(v for k, v in notes.items() if k.startswith("provenance_"))
    assert "coordinates" in provenance
    assert "reference build" in provenance


def test_the_two_flat_formats_state_the_same_notes(prime_menu: RankedMenu, tmp_path: Path) -> None:
    """The reverse direction: nothing the TSV says may be missing from the Parquet.

    This is the half that keeps the property true. A note added to one writer and not
    the other turns this red, which is the failure that would otherwise ship as two
    tables of identical numbers disagreeing about which genome they are against.
    """
    pl = pytest.importorskip("polars")
    report = build_report(prime_menu)
    notes = _parquet_notes(pl, report_to_parquet(report, tmp_path / "menu.parquet"))

    tsv_notes = [line[2:] for line in report_to_tsv(report).splitlines() if line.startswith("# ")]
    assert tsv_notes
    assert list(notes.values()) == tsv_notes
