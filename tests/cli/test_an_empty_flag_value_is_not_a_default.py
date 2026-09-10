"""A flag given an empty value must not silently mean "flag not given".

Every string option on `design` and `batch` is read as `value or cfg.get(...)`, so an
explicit `""` is indistinguishable from the flag never being typed:

    $ aforge design "$V" --reference-fasta g.fa --intent "$INTENT"   # INTENT unset
    [designs a `correct` edit, exit 0, nothing said]

That is not a hypothetical typo — it is what a shell script does with an unset variable,
and the flag was typed, so the run is not what was asked for. `--intent` changes what is
designed, `--weights` changes the ranking, `--populations` decides whether any population
analysis happens at all, and `--cell-context` decides whether the out-of-distribution flag
can be raised.

The population is derived from each command's own string options, so a new one is covered
the day it is added; the two shapes are the two an unset variable produces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer
from typer._click.types import StringParamType
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

#: How to reach each command's body. The *commands* are derived below; this only says
#: what each one needs to get past its own required arguments.
_INVOCATIONS: dict[str, list[str]] = {
    "design": ["chr2:71:A>C", "--no-offtarget", "--reference-fasta", "GENOME"],
    "batch": ["COHORT", "--no-offtarget", "--reference-fasta", "GENOME"],
    "offtarget": ["ATATATATATATATATATAT", "--reference-fasta", "GENOME"],
    # Both required options supplied; the case under test appends its own, and
    # click takes the last value for a non-repeatable option.
    "lift": ["chr2:0-20(+)", "--chain", "CHAIN", "--from", "hg38", "--to", "hg19"],
    "bench run": ["cas9-efficiency"],
    "bench gap": ["cas9-efficiency"],
    "bench leaderboard": ["RESULTS"],
}


def _string_option_commands() -> list[str]:
    """Every command with a string option, from the app.

    Derived, because the rule this file checks held for `design` and `batch` and not for
    the other five — `aforge offtarget --populations ""` ran a scan with no populations
    and said nothing. A list of commands written while fixing two of them is the thing
    that goes stale; the app knows which commands have string options.
    """
    found: list[str] = []

    def walk(command: Any, path: list[str]) -> None:
        subcommands = getattr(command, "commands", None)
        if subcommands:
            for name, sub in subcommands.items():
                walk(sub, [*path, name])
            return
        if any(
            isinstance(p.type, StringParamType) and p.opts[0].startswith("-")
            for p in command.params
        ):
            found.append(" ".join(path))

    root = typer.main.get_command(app)
    for name, command in root.commands.items():  # type: ignore[attr-defined]
        walk(command, [name])
    return sorted(found)


def test_every_such_command_is_reachable_here() -> None:
    """The invocation table must cover the derived commands, or a case is untested."""
    missing = [c for c in _string_option_commands() if c not in _INVOCATIONS]
    assert not missing, (
        f"these commands take a string option and are not exercised: {missing}. "
        "Add an invocation, so the blank-value rule is checked there too."
    )


def _string_flags(command: str) -> list[str]:
    cmd: Any = typer.main.get_command(app)
    for part in command.split():
        cmd = cmd.commands[part]
    return sorted(
        p.opts[0]
        for p in cmd.params
        if isinstance(p.type, StringParamType) and p.opts[0].startswith("-")
    )


def _cases() -> list[tuple[str, str, str]]:
    return [
        (cmd, flag, blank)
        for cmd in _string_option_commands()
        if cmd in _INVOCATIONS
        for flag in _string_flags(cmd)
        for blank in ("", "   ")
    ]


def test_the_flags_are_found() -> None:
    assert "--intent" in _string_flags("design")
    assert "--weights" in _string_flags("batch")
    assert "--populations" in _string_flags("offtarget")


@pytest.mark.parametrize(("command", "flag", "blank"), _cases(), ids=lambda v: repr(v))
def test_a_blank_value_is_refused(
    command: str, flag: str, blank: str, runner: CliRunner, tmp_path: Path
) -> None:
    genome = tmp_path / "g.fa"
    genome.write_text(">chr2\n" + "AT" * 70 + "\n")
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    chain = tmp_path / "over.chain"
    chain.write_text("")
    results = tmp_path / "results.json"
    results.write_text("{}")
    substitutions = {
        "GENOME": str(genome),
        "COHORT": str(cohort),
        "CHAIN": str(chain),
        "RESULTS": str(results),
    }
    args = [*command.split()]
    args += [substitutions.get(a, a) for a in _INVOCATIONS[command]]
    result = runner.invoke(app, [*args, flag, blank])
    assert result.exit_code == ExitCode.USAGE, (
        f"{command} {flag} {blank!r} exited {result.exit_code}: {result.stderr}"
    )
    assert flag in result.stderr


def test_omitting_the_flag_still_takes_the_default(runner: CliRunner, tmp_path: Path) -> None:
    """The remedy the message gives has to work."""
    genome = tmp_path / "g.fa"
    genome.write_text(">chr2\n" + "AT" * 70 + "\n")
    result = runner.invoke(
        app,
        ["design", "chr2:71:A>C", "--reference-fasta", str(genome), "--no-offtarget"],
    )
    assert result.exit_code == ExitCode.OK


@pytest.mark.parametrize("value", ["afr,,eas", "afr, ,eas", "afr,eas,"])
def test_a_stray_comma_in_a_list_is_not_a_refusal(
    value: str, runner: CliRunner, tmp_path: Path
) -> None:
    """The half the blank-value rule must not swallow.

    A wholly empty `--populations ""` is an unset variable and is refused. A stray comma
    inside a list is a typo with an unambiguous intent, and this has always dropped the
    empty element and run. Pinned on both shells after the web copy of this rule, applied
    element-wise, made the served page refuse what the CLI accepted.
    """
    genome = tmp_path / "g.fa"
    genome.write_text(">chr2\n" + "AT" * 70 + "\n")
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--populations",
            value,
        ],
    )
    assert result.exit_code == ExitCode.OK, result.stderr
