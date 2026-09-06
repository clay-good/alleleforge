"""A standalone off-target result must say which genome it searched.

`aforge offtarget --json` is the machine-readable artifact for the capability this
project is built around, and it carried none of the document-level context every other
artifact now does:

    not a medical device   offtarget.json:.
    coordinate convention  offtarget.json:.
    reference identity     offtarget.json:.

Its per-search honesty is good — `on_target_excluded`, `searched_bases`,
`effective_matrix`, the ancestry stratification — but a consumer holding the file knows
the budgets and cut-offs and not the genome. Two scans over two different FASTAs
produce different specificities and, before this, indistinguishable payloads. The
`locus` strings are 0-based half-open, which a genome browser reads as 1-based
inclusive, and nothing said so.

It is not a `DesignReport`, so the fact-by-surface check that covers the report renders
never looked at it — the same reason the cohort summary was missed one round earlier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

SPACER = "TATATATATATACCAATATA"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _fasta(tmp_path: Path, name: str, extra: str = "") -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / name
    path.write_text(">chr2\n" + "".join(seq) + extra + "\n")
    return path


def _run(runner: CliRunner, fasta: Path, *extra: str) -> tuple[dict, str]:
    result = runner.invoke(
        app,
        [
            "offtarget",
            SPACER,
            "--reference-fasta",
            str(fasta),
            "--on-target",
            "chr2:43-63",
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    human = result.output
    result_json = runner.invoke(
        app,
        [
            "offtarget",
            SPACER,
            "--reference-fasta",
            str(fasta),
            "--on-target",
            "chr2:43-63",
            "--json",
            *extra,
        ],
    )
    assert result_json.exit_code == 0, result_json.output
    return json.loads(result_json.stdout), human


def test_the_payload_identifies_the_genome(runner: CliRunner, tmp_path: Path) -> None:
    payload, _ = _run(runner, _fasta(tmp_path, "a.fa"))
    shape = payload["reference"]
    assert shape["contigs"] == 1
    assert shape["bases"] == 140
    assert len(shape["sha256"]) == 64
    assert "length" in shape["pins"]


def test_two_genomes_do_not_share_a_payload(runner: CliRunner, tmp_path: Path) -> None:
    """The premise: the two scans really do disagree about the answer."""
    plain, _ = _run(runner, _fasta(tmp_path, "a.fa"))
    decoy, _ = _run(
        runner, _fasta(tmp_path, "b.fa", "TATATATATATACCAATATA" + "TGG" + "T" * 20)
    )
    assert plain["specificity"] != decoy["specificity"]
    assert plain["reference"] != decoy["reference"]


def test_the_payload_states_its_coordinate_system(runner: CliRunner, tmp_path: Path) -> None:
    """Every `locus` in `sites` is in it, and a browser reads the digits differently."""
    payload, _ = _run(runner, _fasta(tmp_path, "a.fa"))
    assert payload["coordinate_system"] == "0-based-half-open"


def test_the_payload_carries_the_research_use_disclaimer(
    runner: CliRunner, tmp_path: Path
) -> None:
    payload, _ = _run(runner, _fasta(tmp_path, "a.fa"))
    assert "not a medical device" in payload["disclaimer"]


def test_the_human_output_names_the_genome_and_the_convention(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The terminal reader needs it too, and gets it once rather than per row."""
    _, human = _run(runner, _fasta(tmp_path, "a.fa"))
    assert "reference build" in human
    assert "shape " in human
    assert "0-based half-open" in human
