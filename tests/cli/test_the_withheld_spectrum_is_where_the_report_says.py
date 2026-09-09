"""The report tells a reader where the withheld alleles are. The command dropped them.

Every truncated outcome table carries `WITHHELD_ALLELES_NOTE`:

    showing 3 of 4 predicted alleles (0.95 of the probability mass); the full spectrum
    is on the ranked menu, not in the report export — `aforge design --json` writes it

`--json`'s own help says "Also print the ranked menu as JSON to stdout". It was guarded
by `if as_json and out is not None`, so on the simplest form of the command the note
names — `aforge design VARIANT --json`, no `--out` — the menu was **silently not
printed**. The reader got the report they already had, three alleles of four, and no sign
that the thing they asked for had been withheld.

The guard had a real reason: without `--out` the report goes to stdout too, and two JSON
documents on one stream is precisely what `test_a_json_stream_carries_only_json` exists to
prevent. Dropping one of them silently is not the way out of that. The command now refuses
and names both remedies, so a promise that cannot be kept on this invocation becomes a
sentence the reader can act on rather than a missing document.

The allele withheld in the fixture below is an `indel` byproduct. Which byproducts a
pegRNA produces is the question the outcome table exists to answer.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.report.builder import WITHHELD_ALLELES_NOTE


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


def test_the_note_still_names_this_command() -> None:
    """The test is about a promise; if the wording moves, so must this."""
    assert "--json" in WITHHELD_ALLELES_NOTE, WITHHELD_ALLELES_NOTE
    assert "ranked menu" in WITHHELD_ALLELES_NOTE


def test_the_menu_reaches_stdout_and_carries_the_withheld_alleles(
    reference: Path, tmp_path: Path
) -> None:
    """The route the note names, and what it must deliver: every allele, not the top few."""
    out = tmp_path / "report.json"
    result = CliRunner().invoke(
        app,
        [
            "design",
            _variant(reference),
            "--reference-fasta",
            str(reference),
            "--out",
            str(out),
            "--json",
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    menu = json.loads(result.stdout)
    report = json.loads(out.read_text())

    shown = report["candidates"][0]["outcome_top"]
    total = report["candidates"][0]["n_outcome_alleles"]
    assert total > len(shown), "the fixture withholds nothing; this check would be vacuous"

    alleles = menu["candidates"][0]["outcome"]["alleles"]
    assert len(alleles) == total, (len(alleles), total)
    withheld = {a["allele"] for a in alleles} - {a["allele"] for a in shown}
    assert withheld, "the menu shows no more than the report did"


def test_the_note_s_own_command_delivers_the_spectrum(reference: Path) -> None:
    """`aforge design VARIANT --json`, exactly as the note prints it, with no `--out`.

    A stream cannot carry two JSON documents, so one of them must go. The menu is the
    document the caller named; the report on stdout is the default they did not. It used
    to resolve the other way and silently, so this command printed the truncation instead
    of the full spectrum it points at.
    """
    result = CliRunner().invoke(
        app, ["design", _variant(reference), "--reference-fasta", str(reference), "--json"]
    )
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    menu = json.loads(result.stdout)
    candidate = menu["candidates"][0]
    assert "outcome" in candidate, sorted(candidate)
    assert candidate["outcome"]["alleles"], "the menu carried no allele spectrum"


def test_the_stream_still_carries_exactly_one_document(reference: Path) -> None:
    """The reason the report gives way rather than being printed alongside."""
    result = CliRunner().invoke(
        app, ["design", _variant(reference), "--reference-fasta", str(reference), "--json"]
    )
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    json.loads(result.stdout)  # raises if two documents were concatenated


def test_the_report_alone_still_goes_to_stdout(reference: Path) -> None:
    """The refusal must not cost the ordinary invocation its output."""
    result = CliRunner().invoke(
        app, ["design", _variant(reference), "--reference-fasta", str(reference)]
    )
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    body = json.loads(result.stdout)
    assert body["candidates"], "the default run printed no report"
