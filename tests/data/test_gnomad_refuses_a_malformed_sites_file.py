"""A malformed gnomAD sites TSV must be refused, not raise `KeyError`.

`--gnomad` is the input that makes the off-target scan population-aware — the whole
reason this project exists — and it was the one user-supplied format whose parse
errors were not caught:

    chrom  pos  ref  alt        (a row with the trailing columns lost)
    KeyError: 'af'              (a raw traceback)

`zip(header, cols, strict=False)` truncates silently, so the row dict simply lacked
the keys the parser then indexed. Every sibling format already does better. The
haplotype loader is the standard to match — it names the missing column *and* prints
the expected header — while the BED and bedGraph loaders at least surface a caught
`ValueError`.

Three shapes are covered, because they want three different answers:

* a **header** missing a core column — nothing in the file is usable, say what is
  expected;
* a **row** with fewer fields than the core columns — name the line, so a truncated
  download or a hand-edited row can be found;
* a **duplicate** column name — `dict(zip(...))` keeps the last silently, and a file
  where `afr` appears twice with two frequencies has no single meaning.

A row that merely omits *trailing population* columns stays legal: the parser already
treats an absent per-population value as absent, and ragged tails are ordinary in
hand-assembled panels.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB

_HEADER = "#chrom\tpos\tref\talt\taf\tafr\tnfe\n"
_GOOD = "chr2\t60\tA\tG\t0.05\t0.08\t0.02\n"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sites.tsv"
    path.write_text(text)
    return path


def test_a_well_formed_file_still_parses(tmp_path: Path) -> None:
    """Guard the guard: the fixture must be usable before its mutations mean anything."""
    db = GnomadDB.from_sites_tsv(_write(tmp_path, _HEADER + _GOOD))
    assert db.available_populations == frozenset({"afr", "nfe"})


def test_a_row_missing_its_trailing_population_columns_is_still_read(tmp_path: Path) -> None:
    """A ragged tail is ordinary; only the core columns are required."""
    db = GnomadDB.from_sites_tsv(_write(tmp_path, _HEADER + "chr2\t60\tA\tG\t0.05\n"))
    assert db.available_populations == frozenset()


def test_a_short_row_names_the_line(tmp_path: Path) -> None:
    path = _write(tmp_path, _HEADER + _GOOD + "chr2\t61\tA\tG\n")
    with pytest.raises(ValueError, match=r"line 3") as excinfo:
        GnomadDB.from_sites_tsv(path)
    assert "4" in str(excinfo.value)  # the field count found


def test_a_header_missing_a_core_column_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "#chrom\tpos\tref\talt\nchr2\t60\tA\tG\n")
    with pytest.raises(ValueError, match=r"af"):
        GnomadDB.from_sites_tsv(path)


def test_a_duplicated_column_is_refused(tmp_path: Path) -> None:
    """Two `afr` columns with two frequencies is a file with no single meaning."""
    path = _write(
        tmp_path, "#chrom\tpos\tref\talt\taf\tafr\tafr\n" + "chr2\t60\tA\tG\t0.05\t0.08\t0.99\n"
    )
    with pytest.raises(ValueError, match=r"afr"):
        GnomadDB.from_sites_tsv(path)


def test_a_row_with_more_fields_than_the_header_is_refused(tmp_path: Path) -> None:
    """An unnamed column is data being dropped; `zip` would have discarded it."""
    path = _write(tmp_path, _HEADER + _GOOD.rstrip("\n") + "\t0.5\n")
    with pytest.raises(ValueError, match=r"line 2"):
        GnomadDB.from_sites_tsv(path)
