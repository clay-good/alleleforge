"""The ranked menu was reachable from the CLI, but only as a stream you had to redirect.

Round 437 gave the web API a `menu` format so a browser could download the full outcome
spectrum. That left the two shells spelling the same capability differently:
`test_the_two_shells_offer_the_same_output_formats` failed, and it was right to. The CLI
could produce the menu — `--json`, fixed in round 435 — but only onto stdout, and only
as a side channel next to `--format`. You could not ask for it the way you ask for every
other document the command writes:

    aforge design VARIANT --format menu --out menu.json

and so the menu was the one output with no provenance sidecar and no place on disk.

`menu` is now an `OutputFormat`. It renders the ranked menu instead of the report built
from it, and is written and sidecar'd like the rest. `--json` keeps working; it is the
stdout shorthand, not the only door.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, OutputFormat, app


@pytest.fixture
def reference(tmp_path: Path) -> Path:
    rng = random.Random(7)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(20000)) + "\n")
    return fasta


def _variant(reference: Path) -> str:
    sequence = "".join(reference.read_text().split("\n")[1:])
    base = sequence[9999]
    return f"chr1:10000:{base}>{'A' if base != 'A' else 'G'}"


def test_menu_is_a_format_the_command_offers() -> None:
    """The spelling the web API already answers to."""
    assert OutputFormat.menu.value == "menu"


def test_the_menu_format_writes_the_full_spectrum_to_a_file(
    reference: Path, tmp_path: Path
) -> None:
    """What `--json` could not do: land the spectrum on disk, sidecar and all."""
    variant = _variant(reference)
    menu_path = tmp_path / "menu.json"
    report_path = tmp_path / "report.json"
    runner = CliRunner()
    base = ["design", variant, "--reference-fasta", str(reference)]

    written = runner.invoke(app, [*base, "--format", "menu", "--out", str(menu_path)])
    assert written.exit_code == ExitCode.OK, written.output + written.stderr
    reported = runner.invoke(app, [*base, "--out", str(report_path)])
    assert reported.exit_code == ExitCode.OK, reported.output + reported.stderr

    menu = json.loads(menu_path.read_text())
    report = json.loads(report_path.read_text())
    shown = report["candidates"][0]["outcome_top"]
    total = report["candidates"][0]["n_outcome_alleles"]
    assert total > len(shown), "the fixture withholds nothing; this check would be vacuous"

    alleles = menu["candidates"][0]["outcome"]["alleles"]
    assert len(alleles) == total, (len(alleles), total)
    sidecar = menu_path.with_suffix(menu_path.suffix + ".provenance.json")
    assert sidecar.exists(), (
        "the menu was written without the sidecar every other format gets: "
        f"{sorted(q.name for q in tmp_path.iterdir())}"
    )


def test_the_menu_format_prints_one_document_to_stdout(reference: Path) -> None:
    """No `--out`, like `--format json`: the named document, and only it."""
    result = CliRunner().invoke(
        app,
        [
            "design",
            _variant(reference),
            "--reference-fasta",
            str(reference),
            "--format",
            "menu",
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    menu = json.loads(result.stdout)  # raises if two documents were concatenated
    assert menu["candidates"][0]["outcome"]["alleles"], "the menu carried no spectrum"
