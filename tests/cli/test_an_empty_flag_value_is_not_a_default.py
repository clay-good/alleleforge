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

_INVOCATIONS: dict[str, list[str]] = {
    "design": ["chr2:71:A>C", "--no-offtarget"],
    "batch": ["COHORT", "--no-offtarget"],
}


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
        for cmd in _INVOCATIONS
        for flag in _string_flags(cmd)
        for blank in ("", "   ")
    ]


def test_the_flags_are_found() -> None:
    assert "--intent" in _string_flags("design")
    assert "--weights" in _string_flags("batch")


@pytest.mark.parametrize(("command", "flag", "blank"), _cases(), ids=lambda v: repr(v))
def test_a_blank_value_is_refused(
    command: str, flag: str, blank: str, runner: CliRunner, tmp_path: Path
) -> None:
    genome = tmp_path / "g.fa"
    genome.write_text(">chr2\n" + "AT" * 70 + "\n")
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    positional = [a.replace("COHORT", str(cohort)) for a in _INVOCATIONS[command]]
    result = runner.invoke(
        app,
        [command, *positional, "--reference-fasta", str(genome), flag, blank],
    )
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
