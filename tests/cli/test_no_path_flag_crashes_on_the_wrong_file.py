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
from typing import Any

import pytest
import typer
from typer.models import TyperPath
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

#: The commands that take a genome and a variant, with the arguments each needs to get
#: past its own required options. Every path *flag* on each is then derived from the
#: command, which is the population that goes stale; the invocations are a fixture.
_INVOCATIONS: dict[str, list[str]] = {
    "design": ["chr2:71:A>C", "--no-offtarget", "--reference-fasta", "GENOME"],
    "batch": ["COHORT", "--no-offtarget", "--reference-fasta", "GENOME"],
    "offtarget": ["ATATATATATATATATATAT", "--reference-fasta", "GENOME"],
    "resolve": ["chr2:71:A>C", "--reference-fasta", "GENOME"],
    # The two benchmark commands write *after* the work: `bench run` scores a whole
    # split before it touches `--out`. They take no genome.
    "bench run": ["cas9-efficiency"],
    "bench leaderboard": ["RESULTS"],
    "lift": ["chr2:0-20(+)", "--from", "hg38", "--to", "hg19"],
    "verify": ["DESIGN_JSON"],
}


def _path_option_commands() -> list[str]:
    """Every command with a path option, from the app.

    Derived, because the *command* list is the one that went stale: this sweep covered
    six commands while `lift` and `verify` also take paths, and `aforge lift --chain`
    given a file that is not a chain file reported every locus `UNMAPPED` — a wrong
    answer, not a missing one.
    """
    found: list[str] = []

    def walk(command: Any, path: list[str]) -> None:
        subcommands = getattr(command, "commands", None)
        if subcommands:
            for name, sub in subcommands.items():
                walk(sub, [*path, name])
            return
        if any(isinstance(p.type, TyperPath) and p.opts[0].startswith("-") for p in command.params):
            found.append(" ".join(path))

    root = typer.main.get_command(app)
    for name, command in root.commands.items():  # type: ignore[attr-defined]
        walk(command, [name])
    return sorted(found)


def test_every_such_command_is_reachable_here() -> None:
    missing = [c for c in _path_option_commands() if c not in _INVOCATIONS]
    assert not missing, (
        f"these commands take a path option and are not exercised: {missing}. "
        "Add an invocation, so a wrong file is checked there too."
    )


#: The three shapes a path argument can be wrong. A wrong-kind *file* is the
#: transposition rounds 524-526 chased; a **directory** and a path under a directory that
#: does not exist are the two an output argument meets, and both crashed.
_SHAPES = ("wrong-kind file", "a directory", "under a missing directory")


def _path_flags(command: str) -> list[str]:
    """The path-taking options of ``command``, from the command itself."""
    cmd: Any = typer.main.get_command(app)
    for part in command.split():
        cmd = cmd.commands[part]
    return sorted(
        p.opts[0] for p in cmd.params if isinstance(p.type, TyperPath) and p.opts[0].startswith("-")
    )


def _cases() -> list[tuple[str, str, str]]:
    return [
        (cmd, flag, shape) for cmd in _INVOCATIONS for flag in _path_flags(cmd) for shape in _SHAPES
    ]


@pytest.fixture(scope="module")
def design_json(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real design report, so `verify` fails on the flag under test and not on its
    positional argument."""
    directory = tmp_path_factory.mktemp("verify")
    genome = directory / "g.fa"
    genome.write_text(">chr2\n" + "AT" * 70 + "\n")
    out = directory / "report.json"
    CliRunner().invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert out.is_file()
    return out


@pytest.fixture(scope="module")
def bench_result(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real benchmark result JSON, so `bench leaderboard` fails on `--out` and not on
    its positional argument."""
    path = tmp_path_factory.mktemp("bench") / "result.json"
    CliRunner().invoke(app, ["bench", "run", "cas9-efficiency", "--out", str(path)])
    assert path.is_file()
    return path


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


@pytest.mark.parametrize(("command", "flag", "shape"), _cases(), ids=lambda v: str(v))
def test_a_wrong_file_is_refused_not_crashed_on(
    command: str,
    flag: str,
    shape: str,
    runner: CliRunner,
    genome: Path,
    wrong_file: Path,
    bench_result: Path,
    design_json: Path,
    tmp_path: Path,
) -> None:
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    if shape == "a directory":
        probe = tmp_path / "a-dir"
        probe.mkdir()
    elif shape == "under a missing directory":
        probe = tmp_path / "no-such-dir" / "x.json"
    else:
        probe = wrong_file

    substitutions = {
        "COHORT": str(cohort),
        "GENOME": str(genome),
        "RESULTS": str(bench_result),
        "DESIGN_JSON": str(design_json),
    }
    args = [*command.split()]
    args += [substitutions.get(a, a) for a in _INVOCATIONS[command]]
    if flag in args:
        args[args.index(flag) + 1] = str(probe)
    else:
        args += [flag, str(probe)]
    result = runner.invoke(app, args)

    # `typer.Exit` / `SystemExit` is a refusal; anything else is a traceback the user saw.
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"{flag} raised {result.exception!r}"
    )
    assert "Traceback" not in result.stderr
    if result.exit_code not in (0, ExitCode.OK):
        # A refusal names the offending path, so the reader knows which of ten was
        # wrong — the flag's own name where the message has room for it.
        assert str(probe) in result.stderr or flag in result.stderr, result.stderr


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


@pytest.mark.parametrize("flag", ["--gnomad", "--dbsnp", "--regions-bed"])
def test_the_right_file_still_goes_through(
    flag: str, runner: CliRunner, genome: Path, tmp_path: Path
) -> None:
    """The half a sweep of wrong inputs cannot see.

    Every case above hands a flag something it should refuse, and a flag that refused
    *everything* would pass all of them. Three of these refusals were tightened in this
    file's own rounds — the dbSNP header check, the BED line prefix, the gnomAD header —
    so each is asked, here, to still accept the file it is for.
    """
    files = {
        "--gnomad": (
            "gnomad.tsv",
            "#chrom\tpos\tref\talt\taf\tafr\nchr2\t71\tA\tC\t0.02\t0.03\n",
        ),
        "--dbsnp": ("dbsnp.tsv", "#rsid\tchrom\tpos\tref\talt\nrs1\tchr2\t71\tA\tC\n"),
        "--regions-bed": ("regions.bed", "chr2\t0\t140\n"),
    }
    name, content = files[flag]
    path = tmp_path / name
    path.write_text(content)
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            flag,
            str(path),
        ],
    )
    assert result.exit_code == ExitCode.OK, result.stderr
