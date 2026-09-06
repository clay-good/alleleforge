"""A refusal over a closed set of values must name the set.

Five CLI inputs are validated against a fixed vocabulary. Three already told the
caller what the vocabulary is:

    --scorer nope      -> unknown scorer 'nope'; choose one of: cfd, cfd-cas12a, mit
    bench run nope     -> unknown task 'nope'; known: ('be-outcome', ...)
    data show nope     -> unknown dataset 'nope'; known: ('1000g', ...)

Two did not, and they are the two flags on the primary command a first-time caller is
most likely to get wrong:

    --intent fixit     -> unknown intent 'fixit'
    --chemistry PRIME  -> unknown chemistry: 'PRIME' is not a valid Chemistry

The second also leaked a Python type name into a user-facing message. `Chemistry` is
the class; it is not a word in the vocabulary the caller is being asked to use.

Both sets are small enums the code has in hand at the moment it refuses, which is the
recurring shape: the remedy for a refusal is usually already in a local variable. The
web API's equivalents are covered too — a `422` a client cannot act on is worse than a
CLI message, because there is no `--help` on the other end of an HTTP call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.types.edit import Chemistry, EditIntent


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "prime.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


def _invoke(runner: CliRunner, fasta: Path, *extra: str) -> str:
    result = runner.invoke(
        app,
        ["design", "chr2:71:A>C", "--reference-fasta", str(fasta), "--no-offtarget", *extra],
    )
    assert result.exit_code != 0
    return result.output + result.stderr


def test_an_unknown_intent_lists_the_intents(runner: CliRunner, fasta: Path) -> None:
    output = _invoke(runner, fasta, "--intent", "fixit")
    assert "fixit" in output
    for intent in EditIntent:
        assert intent.value in output, intent


def test_an_unknown_chemistry_lists_the_chemistries(runner: CliRunner, fasta: Path) -> None:
    output = _invoke(runner, fasta, "--chemistry", "PRIME")
    assert "PRIME" in output
    for chemistry in Chemistry:
        assert chemistry.value in output, chemistry


def test_the_chemistry_refusal_does_not_leak_the_class_name(runner: CliRunner, fasta: Path) -> None:
    """`'PRIME' is not a valid Chemistry` names an implementation detail."""
    output = _invoke(runner, fasta, "--chemistry", "PRIME")
    assert "is not a valid Chemistry" not in output


@pytest.mark.parametrize(
    "argv, bad, expected",
    [
        (["offtarget", "ACGTACGTACGTACGTACGT", "--scorer", "nope"], "nope", "cfd"),
        (["bench", "run", "nosuchtask"], "nosuchtask", "cas9-efficiency"),
        (["data", "show", "nosuchdataset"], "nosuchdataset", "gnomad"),
    ],
    ids=["scorer", "bench-task", "dataset"],
)
def test_the_refusals_that_already_listed_still_do(
    runner: CliRunner, fasta: Path, argv: list[str], bad: str, expected: str
) -> None:
    """Guard the three that were already right, so the rule holds across all five."""
    full = [*argv, "--reference-fasta", str(fasta)] if argv[0] == "offtarget" else argv
    result = runner.invoke(app, full)
    assert result.exit_code != 0
    combined = result.output + result.stderr
    assert bad in combined and expected in combined
