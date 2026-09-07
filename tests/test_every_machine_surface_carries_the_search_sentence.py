""" "0 sites, specificity 1.000" from a search that examined zero bases.

A BED panel of zero-length intervals restricts a scan to nothing. The tool catches it —
the human line reads "NO SEQUENCE WAS SEARCHED — the reference or region scope yielded no
bases, so this is not a clean result, it is an empty one" — and two of the three
machine-readable surfaces carry that sentence: the design report's JSON in
`offtarget_search`, and the web response in `search_description`.

`aforge offtarget --json` carried `searched_bases: 0` and no sentence. Its own comment
says why that number is there — "`searched_bases: 0` is the one value that makes '0 sites,
specificity 1.000' mean nothing at all" — so the inputs to the inference shipped and the
inference did not, on the surface most likely to be scripted against.

The rule is the reusable part: every machine-readable surface that reports a search
carries its description, not only the numbers the description is derived from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

_SPACER = "ACCTGAAGACTTACGCATAC"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "ref.fa"
    path.write_text(">chr2\n" + _SPACER + "TGG" + ("ACGT" * 300) + "\n")
    return path


@pytest.fixture
def empty_panel(tmp_path: Path) -> Path:
    """A BED whose intervals have zero length: a scan restricted to nothing."""
    path = tmp_path / "empty.bed"
    path.write_text("chr2\t100\t100\nchr2\t500\t500\n")
    return path


def _cli_json(fasta: Path, *extra: str, expect_exit: int = 0) -> dict:
    """Return the parsed `--json` payload, asserting the exit code.

    An empty search exits non-zero *and* still prints its JSON — a separate, correct
    decision (a scan that examined nothing is not a clean exit), and one a caller
    scripting this command has to be able to read the payload through.
    """
    result = CliRunner().invoke(
        app, ["offtarget", _SPACER, "--reference-fasta", str(fasta), "--json", *extra]
    )
    assert result.exit_code == expect_exit, (result.exit_code, result.stderr)
    return json.loads(result.stdout)


def test_the_empty_scan_still_reports_a_perfect_specificity(fasta: Path, empty_panel: Path) -> None:
    """The premise: the number on its own is reassuring and meaningless."""
    payload = _cli_json(fasta, "--regions-bed", str(empty_panel), expect_exit=3)
    assert payload["specificity"] == 1.0
    assert payload["n_sites"] == 0
    assert payload["search"]["searched_bases"] == 0


def test_the_cli_json_says_nothing_was_searched(fasta: Path, empty_panel: Path) -> None:
    payload = _cli_json(fasta, "--regions-bed", str(empty_panel), expect_exit=3)
    description = payload["search"]["description"]
    assert "NO SEQUENCE WAS SEARCHED" in description, description
    assert "not a clean result" in description


def test_the_cli_json_keeps_the_structured_budgets_too(fasta: Path) -> None:
    """The sentence is added beside the numbers, not instead of them."""
    search = _cli_json(fasta)["search"]
    for key in ("mismatch_threshold", "cfd_threshold", "searched_bases", "description"):
        assert key in search, sorted(search)


def test_an_ordinary_search_describes_itself_too(fasta: Path) -> None:
    description = _cli_json(fasta)["search"]["description"]
    assert "mismatches" in description and "bases" in description
    assert "NO SEQUENCE WAS SEARCHED" not in description


def test_the_web_surface_carries_it() -> None:
    """The sibling that already did — pinned so the three cannot diverge again."""
    pytest.importorskip("fastapi")
    from alleleforge.web.api.models import OffTargetResponse

    field = OffTargetResponse.model_fields.get("search_description")
    assert field is not None, sorted(OffTargetResponse.model_fields)
    assert field.description, "the field exists but says nothing about itself"


def test_the_design_report_surface_carries_it(tmp_path: Path) -> None:
    from alleleforge.design.designer import design
    from alleleforge.genome.reference import ReferenceGenome
    from alleleforge.report.builder import build_report
    from alleleforge.report.export import report_to_json

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "r.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    menu = design("chr2:71:A>C", reference=ReferenceGenome(path, build="hg38"))
    payload = json.loads(report_to_json(build_report(menu)))
    searched = [c for c in payload["candidates"] if c.get("offtarget_search")]
    assert searched, "no candidate carried a search description"
    assert "mismatches" in searched[0]["offtarget_search"]
