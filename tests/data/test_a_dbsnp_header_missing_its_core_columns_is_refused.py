"""A dbSNP TSV whose header is short must say so, not silently load nothing.

`DbSnpDB.from_tsv` reads an `rsid chrom pos ref alt` table and checks the header names
every one of those five columns before it reads a data row. The sibling refusal — a file
with *no* `#` header at all — was tested; a header that is present but missing a column
was not, and deleting its guard survived `tests/data`.

The failure that guard prevents is the quiet kind. `_parse` builds each row with
`dict(zip(header, cols, strict=False))`, and `strict=False` is deliberate: a real dbSNP
export carries columns this loader does not use, so a longer row is normal. The cost is
that a *shorter* header is also normal-looking. Drop the guard and a file whose header
says `rsid chrom pos ref` — one column clipped, which is what a truncated download or a
hand-edited export looks like — yields rows with no `alt` key, and the first row fails
somewhere inside `Variant` construction with a message about a missing field rather than
about the file.

The worse version is a header with the right *count* and a wrong *name* (`position`
instead of `pos`): every row then parses into a dict keyed by the wrong names, and what
the user gets is not an error about their file but an error about this library.

Found by deleting the refusal (`scripts/mutate.py --mode raise`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.dbsnp import DbSnpDB

_GOOD_HEADER = "#rsid\tchrom\tpos\tref\talt"
_ROW = "rs1\t2\t100\tA\tT"


def _tsv(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "dbsnp.tsv"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_a_complete_header_loads(tmp_path: Path) -> None:
    """The premise, and the case the guard must not fire on."""
    db = DbSnpDB.from_tsv(_tsv(tmp_path, _GOOD_HEADER, _ROW))
    assert len(db) == 1
    assert db.locus("rs1").rsid is not None


def test_extra_columns_are_still_accepted(tmp_path: Path) -> None:
    """Why the guard checks for *missing* names rather than an exact column set.

    A real dbSNP export carries columns this loader ignores. A guard that demanded an
    exact header would reject every genuine file, so the check is one-directional — and
    this pins that direction, so tightening it breaks here rather than at a user's shell.
    """
    db = DbSnpDB.from_tsv(_tsv(tmp_path, _GOOD_HEADER + "\tqual\tfilter", _ROW + "\t60\tPASS"))
    assert db.locus("rs1").rsid is not None


@pytest.mark.parametrize(
    "header, missing",
    [
        ("#rsid\tchrom\tpos\tref", "alt"),
        ("#rsid\tchrom\tpos\talt", "ref"),
        ("#chrom\tpos\tref\talt", "rsid"),
        ("#rsid\tchrom\tref\talt", "pos"),
        # The one with the right column count and a plausible wrong name.
        ("#rsid\tchrom\tposition\tref\talt", "pos"),
    ],
    ids=["no-alt", "no-ref", "no-rsid", "no-pos", "pos-misnamed-position"],
)
def test_a_header_missing_a_core_column_is_refused(
    tmp_path: Path, header: str, missing: str
) -> None:
    """Every column on its own, because the guard is a loop over all five."""
    with pytest.raises(ValueError, match="header is missing") as refused:
        DbSnpDB.from_tsv(_tsv(tmp_path, header, _ROW))
    assert missing in str(refused.value), (missing, str(refused.value))


def test_the_refusal_shows_both_what_was_expected_and_what_was_found(tmp_path: Path) -> None:
    """The user is holding a file; the remedy is a diff, not a column name.

    Naming only the missing column leaves someone staring at a header that looks right
    to them. Printing the expected header beside the one found is what turns the message
    into something they can act on without opening this source file.
    """
    with pytest.raises(ValueError) as refused:
        DbSnpDB.from_tsv(_tsv(tmp_path, "#rsid\tchrom\tposition\tref\talt", _ROW))
    message = str(refused.value)

    for expected in ("rsid", "chrom", "pos", "ref", "alt"):
        assert expected in message, (expected, message)
    assert "position" in message, (
        "the refusal does not show the header that was actually found, so a user whose "
        "column is merely misnamed cannot see the difference",
        message,
    )


def test_a_file_with_no_header_at_all_is_a_different_message(tmp_path: Path) -> None:
    """The sibling refusal, kept beside this one so the two are not confused.

    Both are `ValueError`, and a test matching only the type would pass against either
    guard while the other was deleted.
    """
    with pytest.raises(ValueError, match="missing its '#rsid ...' header line"):
        DbSnpDB.from_tsv(_tsv(tmp_path, _ROW))
