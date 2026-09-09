"""A cohort is the result that goes into a dataframe, and it had only the text form.

The per-candidate table — the one a human scrolls — has shipped as TSV *and* Parquet for
months. The cohort table, one row per patient and hundreds of rows long, is the more
pipeline-shaped of the two and had only the TSV. `BatchFormat`'s own docstring recorded
the deferral and named its price: "adding it means a new writer plus the guard that its
columns match the TSV's in order — two tables of the same numbers disagreeing about their
columns is a defect this project has already had once".

So the guard comes with the writer. Both encodings are built from one declared
`COHORT_COLUMNS`, and these tests check that the file each one actually writes agrees —
names, order, and the two cells where a rendering decision could quietly diverge:

* `offtarget_sources`, where `{}` means "searched, reference-only" and `None` means "not
  searched", and collapsing them is the one thing this project spends its effort not
  doing; and
* the note block, which in the TSV is the leading `#` lines and in Parquet the file-level
  key/value metadata. A table of specificities with no statement of which genome was
  searched, under which seed, is not interpretable in either encoding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort_summary import (
    COHORT_COLUMN_TYPES,
    COHORT_COLUMNS,
    cohort_to_parquet,
    cohort_to_tsv,
)

_PROVENANCE = {"seed": 20240501, "intent": "correct", "reference_build": "hg38"}


def _rows() -> list[dict[str, Any]]:
    """Two rows exercising both branches of every rendering decision."""
    blank = dict.fromkeys(COHORT_COLUMNS)
    designed = blank | {
        "item_id": "patient-1",
        "status": "ok",
        "variant": "chr1:10000:A>T",
        "best_chemistry": "prime",
        "chemistries": ["prime", "base_abe"],
        "best_efficiency": 0.44999999999999996,
        "best_efficiency_in_distribution": True,
        "best_caveats": ["pol3-terminator", "gc-out-of-band:0.20"],
        # Searched, and no optional source was supplied.
        "offtarget_sources": {},
        "n_candidates": 4,
        "best_specificity": 0.87,
    }
    failed = blank | {"item_id": "patient-2", "status": "error", "error": "unresolvable\tvariant"}
    return [designed, failed]


def _frame(tmp_path: Path) -> Any:
    pl = pytest.importorskip("polars")
    cohort_to_parquet(_rows(), tmp_path / "cohort.parquet", _PROVENANCE)
    return pl.read_parquet(tmp_path / "cohort.parquet")


def test_both_encodings_hold_the_same_columns_in_the_same_order(tmp_path: Path) -> None:
    """The defect the deferral named: one adjacent swap and a column index means two things."""
    lines = cohort_to_tsv(_rows(), _PROVENANCE).splitlines()
    header = next(line for line in lines if not line.startswith("#")).split("\t")
    assert header == list(COHORT_COLUMNS)
    assert _frame(tmp_path).columns == list(COHORT_COLUMNS)


def test_the_declared_types_are_the_types_written(tmp_path: Path) -> None:
    """Declared, not inferred: on a real cohort the first rows are not representative."""
    pl = pytest.importorskip("polars")
    expected = {bool: pl.Boolean, int: pl.Int64, float: pl.Float64, str: pl.Utf8}
    frame = _frame(tmp_path)
    assert dict(zip(frame.columns, frame.dtypes, strict=True)) == {
        col: expected[COHORT_COLUMN_TYPES[col]] for col in COHORT_COLUMNS
    }


def test_numbers_stay_numbers(tmp_path: Path) -> None:
    """The whole reason to have the second encoding; the TSV renders them as text."""
    frame = _frame(tmp_path)
    assert frame["best_efficiency"][0] == pytest.approx(0.45)
    assert frame["n_candidates"][0] == 4
    assert frame["best_efficiency_in_distribution"][0] is True
    # A failed item is null, not a substituted zero: "not measured" is not "measured clean".
    assert frame["best_efficiency"][1] is None
    assert frame["n_candidates"][1] is None


def test_searched_but_reference_only_is_not_not_searched(tmp_path: Path) -> None:
    """The one axis where the two encodings agreeing actually protects someone."""
    frame = _frame(tmp_path)
    assert frame["offtarget_sources"][0] == "reference-only"
    assert frame["offtarget_sources"][1] is None

    tsv_rows = [
        line.split("\t")
        for line in cohort_to_tsv(_rows(), _PROVENANCE).splitlines()
        if not line.startswith("#")
    ][1:]
    column = COHORT_COLUMNS.index("offtarget_sources")
    assert tsv_rows[0][column] == "reference-only"
    assert tsv_rows[1][column] == ""


def test_the_structured_columns_render_the_same_way_in_both(tmp_path: Path) -> None:
    frame = _frame(tmp_path)
    assert frame["chemistries"][0] == "prime;base_abe"
    assert frame["best_caveats"][0] == "pol3-terminator;gc-out-of-band:0.20"


def test_the_notes_travel_with_the_parquet(tmp_path: Path) -> None:
    """In the TSV they are `#` lines; Parquet has a place for them and must use it."""
    pl = pytest.importorskip("polars")
    cohort_to_parquet(_rows(), tmp_path / "cohort.parquet", _PROVENANCE)
    metadata = pl.read_parquet_metadata(tmp_path / "cohort.parquet")  # type: ignore[attr-defined]
    notes = [metadata[key] for key in sorted(metadata) if key.startswith("note_")]
    assert notes, sorted(metadata)
    assert "not a medical device" in notes[0], notes[0]
    assert any("seed 20240501" == note for note in notes), notes
    assert any("hg38" in note for note in notes), notes

    tsv_lines = cohort_to_tsv(_rows(), _PROVENANCE).splitlines()
    tsv_notes = [line[2:] for line in tsv_lines if line.startswith("#")]
    assert notes == tsv_notes, "the two encodings carry different notes"


def test_the_note_order_is_the_document_order(tmp_path: Path) -> None:
    """A Parquet reader gets a mapping and sorts it; the notes are an ordered document."""
    pl = pytest.importorskip("polars")
    cohort_to_parquet(_rows(), tmp_path / "cohort.parquet", _PROVENANCE)
    metadata = pl.read_parquet_metadata(tmp_path / "cohort.parquet")  # type: ignore[attr-defined]
    keys = [key for key in sorted(metadata) if key.startswith("note_")]
    assert keys == sorted(keys), keys
    assert len(keys) > 4, keys
