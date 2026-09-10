"""Every flag that takes a path must refuse the wrong file, not crash on it.

Round 525's lesson was that a transposition has as many directions as the command has
arguments. `design` has ten path arguments. Handing each of them a file meant for another
found two that had never been typed:

    $ aforge design chr2:71:A>C --reference-fasta g.fa --dbsnp gnomad.tsv
    error: could not read --dbsnp gnomad.tsv: 'rsid'

    $ aforge design chr2:71:A>C --reference-fasta g.fa --config gnomad.tsv
    TOMLDecodeError: Expected '=' after a key in a key/value pair (at line 2, column 6)
    [with tomllib's own source frames]

A bare `'rsid'` names neither the file, the schema it has, nor the schema it needs; the
second is a traceback, which on this command's argument list was the last one left.

The population is **derived from the command**, not listed here, because a list written by
someone looking at today's flags is the thing this project keeps finding stale. The
property is the weakest one that holds for every path argument including the output ones:
whatever a wrong file does, it does not reach the user as an unhandled exception.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.models import TyperPath
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

#: The commands that take a genome and a variant, with the arguments each needs to get
#: past its own required options. Every path *flag* on each is then derived from the
#: command, which is the population that goes stale; the invocations are a fixture.
_INVOCATIONS: dict[str, list[str]] = {
    "design": ["chr2:71:A>C", "--no-offtarget"],
    "batch": ["COHORT", "--no-offtarget"],
    "offtarget": ["ATATATATATATATATATAT"],
    "resolve": ["chr2:71:A>C"],
}


def _path_flags(command: str) -> list[str]:
    """The path-taking options of ``command``, from the command itself."""
    root = typer.main.get_command(app)
    cmd = root.commands[command]  # type: ignore[attr-defined]
    return sorted(
        p.opts[0] for p in cmd.params if isinstance(p.type, TyperPath) and p.opts[0].startswith("-")
    )


def _cases() -> list[tuple[str, str]]:
    return [(cmd, flag) for cmd in _INVOCATIONS for flag in _path_flags(cmd)]


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    # 1-based position 71 is an `A`, so the variant below resolves and every case
    # here fails (or does not) for the reason the flag under test gives it.
    path.write_text(">chr2\n" + "AT" * 70 + "\n")
    return path


@pytest.fixture
def wrong_file(tmp_path: Path) -> Path:
    """A gnomAD frequency table: real, well-formed, and meant for exactly one flag."""
    path = tmp_path / "gnomad.tsv"
    path.write_text("#chrom\tpos\tref\talt\tafr\tnfe\nchr2\t71\tA\tC\t0.1\t0.2\n")
    return path


def test_the_flags_are_found() -> None:
    """A derivation that returns nothing would make every case below vacuous."""
    flags = _path_flags("design")
    assert "--dbsnp" in flags and "--config" in flags and "--reference-fasta" in flags


@pytest.mark.parametrize(("command", "flag"), _cases(), ids=lambda v: str(v))
def test_a_wrong_file_is_refused_not_crashed_on(
    command: str, flag: str, runner: CliRunner, genome: Path, wrong_file: Path, tmp_path: Path
) -> None:
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    positional = [a.replace("COHORT", str(cohort)) for a in _INVOCATIONS[command]]
    reference = str(wrong_file) if flag == "--reference-fasta" else str(genome)
    args = [command, *positional, "--reference-fasta", reference]
    if flag != "--reference-fasta":
        args += [flag, str(wrong_file)]
    result = runner.invoke(app, args)

    # `typer.Exit` / `SystemExit` is a refusal; anything else is a traceback the user saw.
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"{flag} raised {result.exception!r}"
    )
    assert "Traceback" not in result.stderr
    if result.exit_code not in (0, ExitCode.OK):
        # A refusal names the offending path, so the reader knows which of ten was
        # wrong — the flag's own name where the message has room for it.
        assert str(wrong_file) in result.stderr or flag in result.stderr, result.stderr


def test_the_dbsnp_schema_is_named_both_ways(
    runner: CliRunner, genome: Path, wrong_file: Path
) -> None:
    """The header check says what it needs *and* what it found."""
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--dbsnp",
            str(wrong_file),
        ],
    )
    assert result.exit_code != ExitCode.OK
    assert "rsid  chrom  pos  ref  alt" in result.stderr
    assert "found: chrom  pos  ref  alt  afr  nfe" in result.stderr


def test_the_config_refusal_says_what_the_flag_reads(
    runner: CliRunner, genome: Path, wrong_file: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--config",
            str(wrong_file),
        ],
    )
    assert result.exit_code == ExitCode.USAGE
    assert "not readable as TOML" in result.stderr
    assert "--gnomad" in result.stderr  # where this file was meant to go


def test_an_output_path_of_the_wrong_kind_is_refused_before_the_run(
    runner: CliRunner, genome: Path, tmp_path: Path
) -> None:
    """`--output-dir` at a file crashed with a bare `FileExistsError` and empty stderr.

    Checked before the cohort starts, not when the write happens: a three-hundred-variant
    run that discovers at the end that it cannot write its summary has done an hour of
    work it cannot hand over.
    """
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    a_file = tmp_path / "not-a-dir"
    a_file.write_text("")
    a_dir = tmp_path / "a-dir"
    a_dir.mkdir()
    base = ["batch", str(cohort), "--reference-fasta", str(genome), "--no-offtarget"]

    at_a_file = runner.invoke(app, [*base, "--output-dir", str(a_file)])
    assert at_a_file.exit_code == ExitCode.USAGE
    assert "is not a directory" in at_a_file.stderr
    assert at_a_file.exception is None or isinstance(at_a_file.exception, SystemExit)

    at_a_dir = runner.invoke(app, [*base, "--summary-tsv", str(a_dir)])
    assert at_a_dir.exit_code == ExitCode.USAGE
    assert "this flag names a file" in at_a_dir.stderr
    # And the check ran before any work: nothing was designed.
    assert "requested" not in at_a_dir.stdout
