"""A search that examined nothing must not exit 0.

Over a truncated reference -- a contig header with no bases, i.e. an interrupted
download -- `aforge offtarget` prints:

    0 site(s), worst score 0.000, specificity 1.000
      search: ... NO SEQUENCE WAS SEARCHED -- the reference or region scope yielded no
      bases, so this is not a clean result, it is an empty one

...and exited 0. The human reading the terminal is told plainly. A pipeline branching on
`$?` sees a spotless guide, which is the same "not measured printed as clean" the warning
above it exists to prevent, one surface over.

`aforge batch` already draws the distinction this needs: a run whose items failed
*completes* without having *succeeded*, and exits non-zero. A truncated reference or a
scope that resolves to nothing is missing data, which is what MISSING_DATA is for.

The `--json` payload had the matching gap: its `search` block carried the budgets and
cut-offs and not the extent, so a machine consumer could not tell a genome-wide scan from
a 140-base one, nor see the zero that makes every other number meaningless.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

SPACER = "TTTAAACGTTTTTTTTTTTT"
#: The spacer, an NGG PAM, and padding -- a reference with something to find.
REAL_CONTIG = SPACER + "TGG" + "T" * 10


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _fasta(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(f">chr1\n{body}\n" if body else ">chr1\n")
    return path


def _args(fasta: Path) -> list[str]:
    return [
        "offtarget",
        SPACER,
        "--reference-fasta",
        str(fasta),
        "--dna-bulges",
        "0",
        "--rna-bulges",
        "0",
    ]


def test_a_search_over_no_sequence_exits_missing_data(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, _args(_fasta(tmp_path, "empty.fa", "")))
    assert result.exit_code == ExitCode.MISSING_DATA, result.output


def test_it_still_says_why_before_exiting(runner: CliRunner, tmp_path: Path) -> None:
    """The exit code is the addition, not a replacement for the explanation."""
    result = runner.invoke(app, _args(_fasta(tmp_path, "empty.fa", "")))
    assert "NO SEQUENCE WAS SEARCHED" in result.output
    assert "not a clean result" in result.output


def test_a_real_search_still_exits_zero(runner: CliRunner, tmp_path: Path) -> None:
    """Guard the guard: the new exit must fire on emptiness, not on every run."""
    result = runner.invoke(app, _args(_fasta(tmp_path, "real.fa", REAL_CONTIG)))
    assert result.exit_code == ExitCode.OK, result.output
    assert "site(s)" in result.output


def test_the_json_payload_carries_the_extent(runner: CliRunner, tmp_path: Path) -> None:
    """The machine-readable counterpart of the human 'over N bases' line."""
    result = runner.invoke(app, [*_args(_fasta(tmp_path, "real.fa", REAL_CONTIG)), "--json"])
    assert result.exit_code == ExitCode.OK, result.output
    search = json.loads(result.output)["search"]
    assert search["searched_bases"] == len(REAL_CONTIG)
    assert search["resolved_bases"] == len(REAL_CONTIG)
    # ...and the population cut-off, which is None when no ancestry source applied.
    assert "maf_threshold" in search


def test_the_json_consumer_can_see_the_empty_search(runner: CliRunner, tmp_path: Path) -> None:
    """A non-zero exit is only actionable if the payload says what was wrong."""
    result = runner.invoke(app, [*_args(_fasta(tmp_path, "empty.fa", "")), "--json"])
    assert result.exit_code == ExitCode.MISSING_DATA
    payload = json.loads(result.output)
    assert payload["search"]["searched_bases"] == 0
    # The reassuring numbers are still there -- which is precisely why the zero has to be.
    assert payload["specificity"] == 1.0
    assert payload["sites"] == []
