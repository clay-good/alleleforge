"""`--render-candidates` caps the drawing, not the data.

Stated in three places -- the CLI help ("the json/tsv exports are never capped"), the web
request model, and a comment in the API handler -- and checked in none. The existing test
covers the half that is easy to notice: that the HTML *is* capped and says what it
withheld. The half that matters if it broke is the other one.

A prime design yields ~90 candidates. If the cap leaked into the exports, a run with
`--render-candidates 3` would write three of them to the JSON a pipeline consumes, with
only the HTML mentioning the other eighty-seven -- data loss in the direction that looks
tidier, and invisible to anyone who reads the machine-readable output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

CAP = 3


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _design(runner: CliRunner, fasta: Path, out: Path, fmt: str, *extra: str) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "correct",
            "--no-offtarget",
            "--format",
            fmt,
            "--out",
            str(out),
            *extra,
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output


def test_the_premise_there_are_more_candidates_than_the_cap(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """A floor: with fewer candidates than the cap, nothing below tests anything."""
    out = tmp_path / "all.json"
    _design(runner, prime_fasta, out, "json")
    assert len(json.loads(out.read_text())["candidates"]) > CAP


def test_the_json_export_is_not_capped(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    uncapped, capped = tmp_path / "u.json", tmp_path / "c.json"
    _design(runner, prime_fasta, uncapped, "json")
    _design(runner, prime_fasta, capped, "json", "--render-candidates", str(CAP))

    n_uncapped = len(json.loads(uncapped.read_text())["candidates"])
    n_capped = len(json.loads(capped.read_text())["candidates"])
    assert n_capped == n_uncapped, (
        f"--render-candidates {CAP} cut the JSON export to {n_capped} of {n_uncapped}"
    )


def test_the_tsv_export_is_not_capped(runner: CliRunner, prime_fasta: Path, tmp_path: Path) -> None:
    uncapped, capped = tmp_path / "u.tsv", tmp_path / "c.tsv"
    _design(runner, prime_fasta, uncapped, "tsv")
    _design(runner, prime_fasta, capped, "tsv", "--render-candidates", str(CAP))

    rows_uncapped = len(uncapped.read_text().splitlines())
    rows_capped = len(capped.read_text().splitlines())
    assert rows_capped == rows_uncapped, (
        f"--render-candidates {CAP} cut the TSV to {rows_capped} rows of {rows_uncapped}"
    )


def test_the_html_is_capped_and_says_so(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """The other half of the contract: the drawing is capped, and admits it."""
    page = tmp_path / "r.html"
    _design(runner, prime_fasta, page, "html", "--render-candidates", str(CAP))

    text = page.read_text()
    assert f"the top {CAP} by rank plus every Pareto-front candidate" in text
