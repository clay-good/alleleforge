"""A command named inside a message the tool prints must be a command the tool has.

Three populations of command references, and two were guarded. `--help` text is checked
by `test_help_text_names_real_flags`; the documentation by
`test_a_documented_command_survives_a_shell` and its siblings. The third is the one a user
meets at the worst moment: the *remedy inside a refusal*.

    source assembly 'hg19' disagrees with requested build 'hg38'; lift the coordinates …
    — `aforge lift <locus> --chain <file> --from hg19 --to hg38` on the command line

Nothing checked that. The flags in that sentence are `--chain`, `--from`, `--to`, and a
rename of any of them leaves the one instruction a stuck user is given pointing at
something that does not exist — on the refusal whose whole purpose is stopping a design at
the wrong place in the genome.

This was written after a round in which a *different* remedy — the outcome table's "the
full spectrum is on the ranked menu, `aforge design --json` writes it" — turned out to name
a command that ran and silently produced the wrong document. A name check would not have
caught that one; nothing static would. It catches the cheaper half: the name being wrong at
all.

The population is string literals in `src/`, which is where a printed message comes from,
and it deliberately includes docstrings — a docstring naming a dead flag misleads the next
maintainer rather than a user, which is a smaller harm and the same defect.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import click
import pytest
from typer.main import get_command

from alleleforge.cli.main import app

_SRC = Path(__file__).resolve().parents[1] / "src" / "alleleforge"

#: Words that follow `aforge` in a message without being a subcommand — the flag's own
#: prose, or a placeholder standing in for one.
_NOT_A_SUBCOMMAND = frozenset({"command", "<command>"})


def _commands() -> dict[str, click.Command]:
    root = get_command(app)
    found: dict[str, click.Command] = {}

    def walk(command: click.Command, prefix: str) -> None:
        for name, child in getattr(command, "commands", {}).items():
            full = f"{prefix}{name}"
            found[full] = child
            walk(child, f"{full} ")

    walk(root, "")
    assert len(found) >= 8, sorted(found)
    return found


def _mentions() -> list[tuple[str, str, str]]:
    """Return ``(file, command, rest)`` for every `aforge …` in a source string.

    The longest command path wins: `aforge bench run --out` is `bench run`'s `--out`, not
    the `bench` group's. Reading only the first word made this guard's first run report a
    real flag as missing, which is the failure mode a check like this must not have — a
    guard that cries wolf gets weakened rather than obeyed.
    """
    commands = _commands()
    pattern = re.compile(r"aforge ((?:[a-z][\w-]*)(?: [a-z][\w-]*)?)([^\n`]*)")
    found: list[tuple[str, str, str]] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for match in pattern.finditer(node.value):
                words = match.group(1).split()
                rest = match.group(2)
                if len(words) == 2 and " ".join(words) not in commands:
                    rest = f" {words[1]}{rest}"
                    words = words[:1]
                found.append((path.name, " ".join(words), rest))
    return found


def test_there_are_mentions_to_check() -> None:
    """A reader that found nothing would pass forever."""
    mentions = _mentions()
    assert len(mentions) >= 8, mentions
    assert any(command == "lift" for _, command, _ in mentions), "the lift remedy is gone"


def test_every_command_a_message_names_exists() -> None:
    commands = _commands()
    unknown = sorted(
        {
            f"{path}: aforge {command}"
            for path, command, _ in _mentions()
            if command not in _NOT_A_SUBCOMMAND and command not in commands
        }
    )
    assert not unknown, (
        f"these messages name a command the CLI does not have: {unknown}. A remedy "
        "pointing at a command that does not exist is worse than no remedy."
    )


def test_every_flag_a_message_names_belongs_to_the_command_it_names() -> None:
    """A flag from a sibling command is the same dead end as one that does not exist."""
    commands = _commands()
    offenders: list[str] = []
    for path, command, tail in _mentions():
        target = commands.get(command)
        if target is None:
            continue
        options = {opt for param in target.params for opt in param.opts}
        for flag in re.findall(r"(?<![\w-])--[a-z][\w-]*", tail):
            if flag not in options:
                offenders.append(f"{path}: `aforge {command} … {flag}` — not an option of it")
    assert not offenders, sorted(set(offenders))


@pytest.mark.parametrize("subcommand", ["lift", "design", "verify", "offtarget", "data", "bench"])
def test_the_commands_the_messages_lean_on_are_still_here(subcommand: str) -> None:
    """Named directly: these are the ones remedies point at, so a rename must fail loudly
    here rather than in someone's terminal."""
    assert subcommand in _commands()
