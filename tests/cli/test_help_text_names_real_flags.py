"""A flag named inside CLI help must be a flag that exists.

`--region`'s help, on `design`, `batch` and `offtarget`, warned that the locus is
0-based "unlike `--variant` and `--pop-freqs`, which take 1-based VCF positions".
Neither flag exists. The variant is a positional argument, and the population
allele-frequency file is `--gnomad`.

The warning is not decoration: mixing the two conventions moves a locus by one base,
which is how a scan silently covers the wrong window. Pointing the reader at a flag
they cannot find makes the one piece of guidance that would have saved them
unfollowable, and `--help` is where a CLI user looks first.

This pins the mechanical property rather than the specific sentence: every long
option a command's help text mentions must be an option that command actually has.
A cross-reference to a *sibling* command's flag is still caught here, deliberately —
help is read one command at a time, and `aforge design --help` naming a flag only
`offtarget` accepts is the same dead end.
"""

from __future__ import annotations

import re

import click
import pytest
import typer

from alleleforge.cli.main import app

#: A long option as it appears in prose, e.g. `--regions-bed`, optionally qualified by
#: the command it belongs to, e.g. `design --region`. The lookbehind keeps the tail of a
#: hyphenated word from reading as the start of a flag.
_FLAG = re.compile(r"(?<![\w-])(?:(?P<cmd>[a-z][a-z-]*) )?`?(?P<flag>--[a-z][a-z0-9-]+)")


def _commands() -> list[tuple[str, click.Command]]:
    """Return every ``(path, command)`` in the CLI, groups included."""
    cli = typer.main.get_command(app)
    found: list[tuple[str, click.Command]] = []

    def walk(cmd: click.Command, ctx: click.Context, path: str) -> None:
        found.append((path, cmd))
        # Duck-typed, not `isinstance(cmd, click.Group)`: Typer builds a `TyperGroup`
        # that is not a click.Group subclass, and the isinstance form silently walks
        # nothing -- one passing test over the root command and no coverage at all.
        lister = getattr(cmd, "list_commands", None)
        if lister is None:
            return
        for name in lister(ctx):
            sub = cmd.get_command(ctx, name)
            assert sub is not None
            walk(sub, click.Context(sub, parent=ctx), f"{path} {name}".strip())

    walk(cli, click.Context(cli), "aforge")
    return found


def _texts(cmd: click.Command) -> list[str]:
    return [p.help or "" for p in cmd.params] + [cmd.help or ""]


def _options(cmd: click.Command) -> set[str]:
    own = {o for p in cmd.params for o in p.opts + p.secondary_opts if o.startswith("--")}
    own.add("--help")
    return own


#: Every command by its full path, so a qualified mention resolves to the right one.
_BY_PATH = dict(_commands())
#: The last word of each path, which is how help text refers to a sibling command.
_BY_NAME = {path.split()[-1]: cmd for path, cmd in _BY_PATH.items()}


@pytest.mark.parametrize("path, cmd", _commands(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_flag_mentioned_in_help_exists(path: str, cmd: click.Command) -> None:
    missing: list[str] = []
    for text in _texts(cmd):
        for m in _FLAG.finditer(text):
            flag, qualifier = m.group("flag"), m.group("cmd")
            # An unqualified flag must exist here; `design --region` is resolved against
            # `design`, so a cross-reference stays legal as long as it says whose flag it
            # is. A qualifier that is not a command name is just an ordinary word before
            # the flag, so fall back to this command.
            target = _BY_NAME.get(qualifier or "", cmd)
            if flag not in _options(target):
                missing.append(f"{qualifier + ' ' if target is not cmd else ''}{flag}")
    missing = sorted(set(missing))
    assert not missing, (
        f"`{path} --help` names option(s) that do not exist on it: {missing}. "
        "Use the real flag, or name the command the flag belongs to as well."
    )


def test_the_scan_reaches_every_subcommand() -> None:
    """Guard the guard: a walk that descends into nothing would pass vacuously."""
    paths = {path for path, _ in _commands()}
    assert {"aforge design", "aforge offtarget", "aforge bench run"} <= paths, paths


def test_the_scan_would_notice_a_broken_reference() -> None:
    """Guard the guard: the regex must actually find a flag written in prose."""
    found = [(m.group("cmd"), m.group("flag")) for m in _FLAG.finditer("see --xx, design --yy")]
    assert found == [("see", "--xx"), ("design", "--yy")]
    assert not _FLAG.findall("a well-formed sentence")

    # And the check itself, over a command whose help names a flag it does not have.
    broken = click.Command("broken", params=[click.Option(["--real"], help="see --fake")])
    with pytest.raises(AssertionError, match=r"--fake"):
        test_every_flag_mentioned_in_help_exists("aforge broken", broken)

    # A reference qualified by a real command is accepted; one qualified by a
    # non-command is not, because that word is prose and the flag is being claimed here.
    ok = click.Command("ok", params=[click.Option(["--real"], help="see design --region")])
    test_every_flag_mentioned_in_help_exists("aforge ok", ok)
    prose = click.Command("p", params=[click.Option(["--real"], help="pass --region")])
    with pytest.raises(AssertionError, match=r"--region"):
        test_every_flag_mentioned_in_help_exists("aforge p", prose)
