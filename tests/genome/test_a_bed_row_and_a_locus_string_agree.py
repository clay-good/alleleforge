""" "chr1:100-100" was a usage error and "chr1<TAB>100<TAB>100" was accepted, in one command.

`GenomicInterval.parse` refuses an interval naming no bases, and says why it exists:
"shared by every surface that accepts a locus from a user, so the CLI and the web API
cannot drift into accepting different spellings". The BED reader was written inline in
`cli/main.py` and constructed intervals directly, so it never reached that check — and a
region list of empty intervals restricts a search to nothing, which reports every guide as
perfectly specific.

`--region` and `--regions-bed` are two spellings of one restriction on one command. They
now go through one function, so they accept and refuse the same things, and a Python
caller scoping a search to a gene panel gets the reader rather than re-deriving which
lines are headers and which end is exclusive.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.genome.bed import merge_region_arguments, read_bed_intervals
from alleleforge.types.sequence import GenomicInterval

_SPACER = "ACGTAACGTTACGTAACGTT"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + _SPACER + "TGG" + ("ACGT" * 200) + "\n")
    return path


def _bed(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "panel.bed"
    path.write_text(body)
    return path


def test_a_valid_panel_parses_with_its_headers_skipped(tmp_path: Path) -> None:
    bed = _bed(tmp_path, "track name=panel\n# comment\n\nchr1\t100\t200\nchr1\t500\t600\n")
    intervals = read_bed_intervals(bed)
    assert [(i.chrom, i.start, i.end) for i in intervals] == [
        ("chr1", 100, 200),
        ("chr1", 500, 600),
    ]


@pytest.mark.parametrize(
    "row, expected",
    [
        ("chr1\t100\t100\n", "names no bases"),
        ("chr1\t200\t100\n", "names no bases"),
        ("chr1\t100\n", "needs chrom, start and end"),
        ("chr1\tx\t200\n", "must be integers"),
    ],
    ids=["empty", "inverted", "short", "non-integer"],
)
def test_a_malformed_row_is_refused_by_line_number(tmp_path: Path, row: str, expected: str) -> None:
    """A panel file is long; "invalid literal for int()" is not a location."""
    with pytest.raises(ValueError) as excinfo:
        read_bed_intervals(_bed(tmp_path, row))
    message = str(excinfo.value)
    assert expected in message, message
    assert "line 1" in message, message


def test_the_two_spellings_refuse_the_same_interval(tmp_path: Path, fasta: Path) -> None:
    """The defect: one command, one restriction, two answers."""
    runner = CliRunner()
    base = ["offtarget", _SPACER, "--reference-fasta", str(fasta)]

    by_locus = runner.invoke(app, [*base, "--region", "chr1:100-100"])
    by_bed = runner.invoke(app, [*base, "--regions-bed", str(_bed(tmp_path, "chr1\t100\t100\n"))])

    assert by_locus.exit_code == ExitCode.USAGE, by_locus.output
    assert by_bed.exit_code == ExitCode.USAGE, by_bed.output + by_bed.stderr


def test_the_two_spellings_accept_the_same_interval(tmp_path: Path, fasta: Path) -> None:
    """Refusing identically is only half of agreeing."""
    runner = CliRunner()
    base = ["offtarget", _SPACER, "--reference-fasta", str(fasta), "--json"]
    by_locus = runner.invoke(app, [*base, "--region", "chr1:0-120"])
    by_bed = runner.invoke(app, [*base, "--regions-bed", str(_bed(tmp_path, "chr1\t0\t120\n"))])
    assert by_locus.exit_code == 0, by_locus.stderr
    assert by_bed.exit_code == 0, by_bed.stderr

    import json

    assert (
        json.loads(by_locus.stdout)["search"]["searched_bases"]
        == json.loads(by_bed.stdout)["search"]["searched_bases"]
    )


def test_no_regions_means_search_everything(tmp_path: Path) -> None:
    """An empty result must stay `None`, not become a list restricting to nothing."""
    assert merge_region_arguments(None, None) is None
    assert merge_region_arguments([], None) is None
    assert merge_region_arguments(None, _bed(tmp_path, "# only a comment\n")) is None


def test_both_inputs_merge_into_one_list(tmp_path: Path) -> None:
    merged = merge_region_arguments(["chr1:0-50"], _bed(tmp_path, "chr1\t100\t200\n"))
    assert merged is not None
    assert [(i.start, i.end) for i in merged] == [(0, 50), (100, 200)]


def test_a_locus_string_still_round_trips(tmp_path: Path) -> None:
    """The library reader must not have changed what `--region` means."""
    interval = GenomicInterval.parse("chr7:28-48(+)")
    assert (interval.chrom, interval.start, interval.end) == ("chr7", 28, 48)
