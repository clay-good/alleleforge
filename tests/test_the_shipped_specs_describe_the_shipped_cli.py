"""The capability specs must describe the product that shipped.

`openspec/specs/` holds nineteen capability specifications — the requirements a change
folds into when it ships, per `openspec/changes/README.md`: *"When a change ships, fold
its deltas into `specs/` and archive the folder."* They are the most canonical documents
in the repository.

Nothing read them. Not one test in the suite touched `openspec/specs`, which is the
shape the previous round named: a source of truth is what everything else is checked
*against*, so nothing is pointed *at* it.

`aforge lift` was the consequence. It shipped with a CLI test, a README row and a
docs entry, and appeared in none of the nineteen specs — and the CLI spec's own
subcommand requirement enumerated five commands for a tool that ships eight. The spec
that says which commands exist did not know about one of them.

Both directions are checked, as for the README and the docs pages before it: a command
the specs name must exist, and a command that exists must be named. The second is the
one that catches a shipped-but-unspecified feature, which is the failure mode of a
process that folds deltas in by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
import pytest
import typer

from alleleforge.cli.main import ExitCode, app

_ROOT = Path(__file__).resolve().parents[1]
_SPECS = _ROOT / "openspec" / "specs"


def _spec_text() -> str:
    return "".join(p.read_text() for p in sorted(_SPECS.rglob("spec.md")))


def _shipped_commands() -> list[str]:
    cli = typer.main.get_command(app)
    return sorted(cli.list_commands(click.Context(cli)))


def test_there_are_specs_to_check() -> None:
    """Guard the guard: an empty read would pass every case below."""
    specs = sorted(_SPECS.rglob("spec.md"))
    assert len(specs) >= 15, [p.name for p in specs]
    assert len(_spec_text()) > 10_000


@pytest.mark.parametrize("command", _shipped_commands())
def test_every_shipped_command_is_specified(command: str) -> None:
    """A command with no requirement behind it shipped without one being written."""
    assert re.search(rf"`{re.escape(command)}`", _spec_text()), (
        f"`aforge {command}` ships and appears in none of the capability specs. "
        "Fold its requirement into openspec/specs/, as the change process says."
    )


def test_the_subcommand_requirement_names_them_all() -> None:
    """Mentioned anywhere is not enough: the requirement that enumerates must be whole.

    The CLI spec has a requirement whose job is to say which subcommands exist. It
    listed five of eight, so a reader trusting the enumeration got a smaller tool than
    the one installed.
    """
    spec = (_SPECS / "cli" / "spec.md").read_text()
    match = re.search(r"The CLI SHALL expose (.+?)\.", spec, re.S)
    assert match is not None, "the cli spec no longer enumerates its subcommands"
    enumerated = set(re.findall(r"`([a-z]+)`", match.group(1)))
    missing = sorted(set(_shipped_commands()) - enumerated)
    assert not missing, f"the subcommand requirement omits: {missing}"


def test_every_command_the_specs_name_exists() -> None:
    """The other direction: a requirement must not describe a command that is gone."""
    spec = (_SPECS / "cli" / "spec.md").read_text()
    match = re.search(r"The CLI SHALL expose (.+?)\.", spec, re.S)
    assert match is not None
    enumerated = set(re.findall(r"`([a-z]+)`", match.group(1)))
    unknown = sorted(enumerated - set(_shipped_commands()))
    assert not unknown, f"the specs require commands the CLI does not have: {unknown}"


def test_the_specified_exit_codes_are_the_real_ones() -> None:
    """The requirement names four codes by number; they are a real enum."""
    spec = (_SPECS / "cli" / "spec.md").read_text()
    named = {int(n) for n in re.findall(r"`(\d)` (?:success|usage|missing data|unavailable)", spec)}
    assert named == {int(code) for code in ExitCode}, (
        f"the cli spec names exit codes {sorted(named)}; ExitCode has "
        f"{sorted(int(c) for c in ExitCode)}"
    )
