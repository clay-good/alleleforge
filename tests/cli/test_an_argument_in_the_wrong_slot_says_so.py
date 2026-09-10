"""A right input in the wrong argument is not a bad input, and only one of the two has a
remedy.

Round 524 refused a genome handed to `aforge batch` as the cohort. The same transposition
runs in both directions between the two commands that take a variant and the two that take
a file, and neither said what had actually happened:

    $ aforge design cohort.txt --reference-fasta g.fa
    error: unrecognized variant input: 'cohort.txt'

    $ aforge batch 'chr2:71:A>C' --reference-fasta g.fa
    error: input file not found: chr2:71:A>C

Both are accurate. The first sends the reader to check a variant syntax that was never the
problem; the second sends them to look for a file they never meant to make. The remedy in
each case is the *other command*, which no check on the value alone can reach.

The file-shaped test is deliberately shape-only — see `_a_file_in_a_variant_slot`: the
resolver is reachable over HTTP with client-supplied text, and answering differently for a
path that exists would make the refusal an oracle for the server's filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.variant.resolver import parses_as_variant, resolve


@pytest.mark.parametrize(
    "text",
    ["cohort.txt", "./variants.txt", "/data/patients/cohort.vcf", "sample.g.vcf"],
)
def test_a_file_in_the_variant_slot_names_the_commands_that_take_files(text: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve(text)
    message = str(excinfo.value)
    assert "takes one variant, not a file" in message
    # The remedy is the other argument, one per caller.
    assert "aforge batch" in message
    assert "--patient-vcf" in message


def test_the_sentence_is_offered_only_for_that_shape() -> None:
    """An ordinary typo is not told a story about files it has nothing to do with."""
    with pytest.raises(ValueError) as excinfo:
        resolve("chr2:71:A->C")
    assert "not a file" not in str(excinfo.value)


def test_the_refusal_does_not_touch_the_disk(tmp_path: Path) -> None:
    """A path that exists and one that does not must be answered identically.

    Anything else is a file-existence oracle on a resolver an HTTP client can reach.
    """
    real = tmp_path / "here.txt"
    real.write_text("chr2:71:A>C\n")
    missing = tmp_path / "not-here.txt"

    def refusal(path: Path) -> str:
        with pytest.raises(ValueError) as excinfo:
            resolve(str(path))
        return str(excinfo.value).replace(str(path), "<path>")

    assert refusal(real) == refusal(missing)


def test_a_variant_in_the_file_slot_names_the_command_that_takes_variants(
    runner: CliRunner, tmp_path: Path
) -> None:
    fasta = tmp_path / "g.fa"
    fasta.write_text(">chr2\n" + "ACGT" * 60 + "\n")
    result = runner.invoke(app, ["batch", "chr2:71:A>C", "--reference-fasta", str(fasta)])
    assert result.exit_code == ExitCode.MISSING_DATA
    assert "That is a variant, not a path" in result.stderr
    assert "aforge design" in result.stderr


def test_a_genuinely_missing_file_is_still_just_missing(runner: CliRunner, tmp_path: Path) -> None:
    fasta = tmp_path / "g.fa"
    fasta.write_text(">chr2\n" + "ACGT" * 60 + "\n")
    result = runner.invoke(
        app, ["batch", str(tmp_path / "gone.txt"), "--reference-fasta", str(fasta)]
    )
    assert result.exit_code == ExitCode.MISSING_DATA
    assert "not a path" not in result.stderr


@pytest.mark.parametrize(
    "text", ["chr2:71:A>C", "rs334", "VCV000012345", "NC_000023.11:g.32380000A>T", "2 71 . A C"]
)
def test_every_input_form_is_recognized_without_a_database(text: str) -> None:
    """`parses_as_variant` answers which *argument* a string belongs to.

    `rs334` is a variant even with no dbSNP release on the machine: a missing release is
    a different sentence from a misplaced argument.
    """
    assert parses_as_variant(text)


@pytest.mark.parametrize("text", ["cohort.txt", "/data/x.vcf", "", "not a variant"])
def test_a_non_variant_is_not_claimed(text: str) -> None:
    assert not parses_as_variant(text)
