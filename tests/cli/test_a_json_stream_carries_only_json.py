"""`aforge design --out x.json --json > menu.json` produced a file no parser accepts.

`--json` prints the ranked menu — the only surface carrying the *full* outcome spectrum,
which is what the report's own "showing 3 of 65 alleles" note sends a reader to. It went
to stdout, and so did the `wrote <path>` confirmation, so the redirect captured a status
line followed by JSON:

    wrote /tmp/x.json and /tmp/x.json.provenance.json
    {
      "candidates": [ ...

The test that covered this path documented the defect rather than failing on it: it
dropped the first line before parsing. Every other message this CLI emits about what it
is doing already goes to stderr; the confirmation is one of those, not data.

Asserted on `result.stdout`, never `result.output` — the latter is click's *mixed*
stream, which is why the original workaround still "passed" after the fix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.types.candidate import RankedMenu


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "prime.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


def _design(fasta: Path, out: Path, *extra: str) -> tuple[str, str]:
    result = CliRunner().invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "2",
            "--no-offtarget",
            "--out",
            str(out),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.stderr
    return result.stdout, result.stderr


def test_the_menu_stream_parses_with_nothing_stripped(fasta: Path, tmp_path: Path) -> None:
    stdout, _ = _design(fasta, tmp_path / "report.json", "--json")
    menu = RankedMenu.model_validate_json(stdout)
    assert menu.candidates


def test_the_confirmation_is_on_stderr_where_a_status_message_belongs(
    fasta: Path, tmp_path: Path
) -> None:
    out = tmp_path / "report.json"
    stdout, stderr = _design(fasta, out, "--json")
    assert "wrote" in stderr and str(out) in stderr
    assert "wrote" not in stdout


def test_a_written_format_leaves_stdout_empty(fasta: Path, tmp_path: Path) -> None:
    """Without `--json` there is no data for stdout, so nothing should be on it."""
    stdout, stderr = _design(fasta, tmp_path / "report.json")
    assert stdout.strip() == "", stdout
    assert "wrote" in stderr


def test_the_menu_stream_is_the_one_with_the_whole_spectrum(fasta: Path, tmp_path: Path) -> None:
    """Why this stream matters: it is where the report's allele note points."""
    out = tmp_path / "report.json"
    stdout, _ = _design(fasta, out, "--json")
    menu = json.loads(stdout)
    report = json.loads(out.read_text())

    spectra = [len(c["outcome"]["alleles"]) for c in menu["candidates"] if c.get("outcome")]
    assert spectra and max(spectra) > 3, "no candidate has a spectrum to withhold"
    shown = max(len(c["outcome_top"]) for c in report["candidates"])
    assert max(spectra) > shown, (
        "the report export carries the full spectrum after all — the note that sends "
        "readers to the menu should say the report instead"
    )
