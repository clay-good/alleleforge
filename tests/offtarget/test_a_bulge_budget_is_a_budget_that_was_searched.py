"""A bulge budget names a search; the search has to be the one that ran.

Round 572's lesson was that a constant naming a range is a promise, and the code that
has to reach it is usually somewhere else. Asking it of every other budget in the
library found this: ``dna_bulges`` and ``rna_bulges`` are ``int`` on every shell — the
CLI took any non-negative number, the web schema advertised ``le=4`` — while both
alignment kernels consider exactly three alignments per PAM (ungapped, one DNA bulge,
one RNA bulge). A budget of 2 was not rejected and did not search: it returned the hits
a budget of 1 returns, and the report then printed

    up to 4 mismatches, 2 DNA / 2 RNA bulges

over a search that had looked for one of each. A caller screening a guide for two-bulge
off-targets got a clean report that says nothing at all about two-bulge off-targets.

The measurement below is the finding — a site built with two extra genomic bases is
invisible at every budget — and the rest asserts the refusal now reaches each shell.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.offtarget import MAX_BULGES
from alleleforge.offtarget._search import check_bulge_budget, scan_sequence
from alleleforge.types.guide import PAM

_SPACER = "GTCAGGGTTCTGGATATCTG"
_PAM = PAM(pattern="NGG")


def _site(extra: int) -> str:
    """A target carrying ``extra`` inserted genomic bases inside the protospacer."""
    return "TTTT" + _SPACER[:10] + "A" * extra + _SPACER[10:] + "TGG" + "TTTT"


def test_one_bulge_is_found_and_two_is_not_at_any_budget() -> None:
    """The measurement. Raising the budget changes nothing, which is the whole point."""
    one = scan_sequence("c", _site(1), _SPACER, _PAM, mismatches=0, dna_bulges=1, rna_bulges=1)
    assert [(h.mismatches, h.dna_bulges) for h in one] == [(0, 1)]

    # The two-bulge site is not reachable at the largest budget the shells accept, nor
    # at any budget above it — so a budget above one cannot be honoured, only printed.
    for budget in range(MAX_BULGES + 1, 5):
        with pytest.raises(ValueError, match="never searched"):
            scan_sequence("c", _site(2), _SPACER, _PAM, mismatches=0, dna_bulges=budget)
    assert scan_sequence("c", _site(2), _SPACER, _PAM, mismatches=0, dna_bulges=MAX_BULGES) == []


def test_the_refusal_names_both_spellings_and_the_offending_budget() -> None:
    """A remedy a caller has to translate is half a remedy (the MIT refusal's rule)."""
    with pytest.raises(ValueError) as excinfo:
        check_bulge_budget(dna_bulges=0, rna_bulges=2)
    message = str(excinfo.value)
    assert "rna_bulges" in message and "dna_bulges" not in message.split("(")[0]
    assert "--dna-bulges 1 --rna-bulges 1" in message  # the command-line spelling
    assert "rna_bulges=1" in message  # the Python one


def test_a_budget_in_range_is_untouched() -> None:
    """The half a refusal test cannot see: a guard that refused everything would pass."""
    for dna in range(MAX_BULGES + 1):
        for rna in range(MAX_BULGES + 1):
            check_bulge_budget(dna_bulges=dna, rna_bulges=rna)


def test_the_engine_refuses_before_it_touches_a_genome() -> None:
    """A whole-genome run must not spend its setup to learn the budget was unsearchable."""
    from alleleforge.offtarget import search

    class Explodes:
        """Any use of the reference is a failure of this test."""

        build = "hg38"

        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"the reference was consulted ({name}) before the refusal")

    with pytest.raises(ValueError, match="never searched"):
        search(_SPACER, _PAM, reference=Explodes(), dna_bulges=2)  # type: ignore[arg-type]


def test_the_web_schema_does_not_advertise_a_budget_that_cannot_run() -> None:
    """A generated client reads this schema; ``le=4`` offered a search that cannot happen."""
    from alleleforge.web.api.models import OffTargetRequest

    for field in ("dna_bulges", "rna_bulges"):
        schema = OffTargetRequest.model_json_schema()["properties"][field]
        assert schema["maximum"] == MAX_BULGES, schema


def test_the_cli_refuses_rather_than_reporting_an_unsearched_budget(tmp_path: Path) -> None:
    """And the message reaches the user, not a traceback."""
    from alleleforge.cli.main import ExitCode, app

    genome = tmp_path / "g.fa"
    genome.write_text(">chr2\n" + "AT" * 200 + "\n")
    result = CliRunner().invoke(
        app,
        ["offtarget", _SPACER, "--reference-fasta", str(genome), "--dna-bulges", "2"],
    )
    assert result.exit_code != ExitCode.OK
    assert "never searched" in result.stderr, result.stderr
    assert "Traceback" not in result.stderr


def test_the_help_says_what_the_flag_accepts() -> None:
    """The flag's own text, so the ceiling is visible before a run rather than after."""
    from alleleforge.cli.main import app

    result = CliRunner().invoke(app, ["offtarget", "--help"])
    assert "Max DNA bulges (0 or 1)" in result.stdout.replace("\n", " ").replace("  ", " ")
