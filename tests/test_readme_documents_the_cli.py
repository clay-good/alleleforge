"""The prose must not make claims the repository cannot back.

Documentation drift is invisible to a test suite by construction — the code keeps
working while the sentences about it rot — so the mechanically checkable claims get
their own pass here: every CLI command is named somewhere, every local link resolves
to a file that exists, and every module path the prose cites is importable.

Two real defects motivated it. `aforge verify` — provenance completeness plus artifact
re-hashing, the mechanism that turns provenance from a record into a checkable contract
— appeared in neither the README nor `docs/`; an undiscoverable feature is, for every
practical purpose, an unshipped one. And the README promised a code of conduct behind a
link that 404s.

These pin only the mechanical half. They cannot tell whether documentation is *good*,
only whether it points at things that exist — which is exactly what was missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.cli.main import app

_ROOT = Path(__file__).resolve().parents[1]


def _command_names() -> list[str]:
    """Return every registered top-level command name."""
    return sorted(
        info.name or (info.callback.__name__ if info.callback else "")
        for info in (*app.registered_commands, *app.registered_groups)
    )


def test_every_cli_command_is_named_in_the_docs() -> None:
    names = _command_names()
    assert names, "no commands discovered — the introspection above is wrong, not the docs"

    prose = (_ROOT / "README.md").read_text()
    for path in (_ROOT / "docs").rglob("*.md"):
        prose += path.read_text()

    missing = [name for name in names if f"aforge {name}" not in prose]
    assert not missing, f"CLI commands documented nowhere: {missing}"


@pytest.mark.parametrize("removed", ["verify", "offtarget"])
def test_the_check_would_notice_a_missing_command(removed: str) -> None:
    """Guard the guard: the assertion above must depend on the prose, not pass blindly."""
    prose = (_ROOT / "README.md").read_text().replace(f"aforge {removed}", "")
    for path in (_ROOT / "docs").rglob("*.md"):
        prose += path.read_text().replace(f"aforge {removed}", "")
    assert f"aforge {removed}" not in prose
    assert removed in _command_names()


# Paths the prose may legitimately reference before they exist in the repository:
# each needs a reason, so this cannot become a place to hide a broken promise.
_ALLOWED_MISSING_LINKS: dict[str, str] = {}


def _prose_files() -> list[Path]:
    return [_ROOT / "README.md", *sorted((_ROOT / "docs").rglob("*.md"))]


def test_every_local_link_in_the_prose_resolves() -> None:
    """A README link that 404s is a claim the repository cannot back.

    Found the code-of-conduct promise: `CONTRIBUTING.md` and the README both told a
    contributor to read a Contributor Covenant that was not in the repository.
    """
    import re

    broken: list[str] = []
    for path in _prose_files():
        text = path.read_text()
        targets = set(re.findall(r"\]\((?!https?:|mailto:|#)([^)#]+)", text))
        targets |= set(
            re.findall(
                r"`((?:src|tests|scripts|docs|examples|openspec|rust)/[A-Za-z0-9_./-]+)`", text
            )
        )
        for target in (t.strip() for t in targets):
            if not target or target in _ALLOWED_MISSING_LINKS:
                continue
            # A docs/ link may be relative to its own page (mkdocs) or to the repo root.
            if (_ROOT / target).exists() or (path.parent / target).exists():
                continue
            broken.append(f"{path.relative_to(_ROOT)} -> {target}")
    assert not broken, f"prose links to files that do not exist: {broken}"


def test_every_module_path_the_prose_cites_is_importable() -> None:
    """`alleleforge.foo.bar` in the prose must still be somewhere in the package."""
    import importlib
    import re

    prose = "\n".join(p.read_text() for p in _prose_files())
    broken: list[str] = []
    for dotted in sorted(set(re.findall(r"`(alleleforge(?:\.[a-z_]+)+)`", prose))):
        try:
            importlib.import_module(dotted)
        except ImportError:
            head, _, tail = dotted.rpartition(".")
            try:
                if not hasattr(importlib.import_module(head), tail):
                    broken.append(dotted)
            except ImportError:
                broken.append(dotted)
    assert not broken, f"prose cites modules that do not exist: {broken}"


def _cli_tree() -> dict[tuple[str, ...], set[str]]:
    """Return ``{subcommand path: accepted --options}`` for the whole CLI.

    Walks by ``hasattr(cmd, "commands")`` rather than ``isinstance(cmd, click.Group)``:
    a ``TyperGroup`` is not an instance of the ``click.Group`` visible here, so an
    isinstance walk silently finds no subcommands and reports the root's five options
    as the entire CLI. That is exactly how an earlier attempt at this check produced a
    page of false positives and was thrown away.
    """
    import typer

    tree: dict[tuple[str, ...], set[str]] = {}

    def walk(cmd: object, path: tuple[str, ...]) -> None:
        opts = {
            o
            for p in getattr(cmd, "params", ())
            for o in (*p.opts, *p.secondary_opts)
            if o.startswith("--")
        }
        tree[path] = opts
        for name, sub in getattr(cmd, "commands", {}).items():
            walk(sub, (*path, name))

    walk(typer.main.get_command(app), ())
    assert len(tree) > 5, "the walk found no subcommands — the introspection is wrong"
    return tree


def _documented_commands() -> list[tuple[Path, str]]:
    """Return every ``aforge …`` command line in a fenced shell block in the prose."""
    import re

    out: list[tuple[Path, str]] = []
    for path in _prose_files():
        for block in re.findall(r"```(?:bash|console|sh)\n(.*?)```", path.read_text(), re.S):
            for line in block.replace("\\\n", " ").splitlines():
                line = line.strip().removeprefix("$ ").strip()
                if line.startswith("aforge "):
                    out.append((path, line))
    return out


def test_every_documented_command_and_flag_exists() -> None:
    """The converse of the check above: prose may not invent a command or a flag.

    One direction was pinned — every command appears somewhere in the docs — and not
    the other. A copy-pasteable command in a quickstart is the first thing a new user
    runs, and a renamed flag turns it into a usage error with no test to notice.
    """
    tree = _cli_tree()
    root_opts = tree[()]
    commands = _documented_commands()
    assert commands, "no aforge commands found in the prose — this check would be vacuous"

    problems: list[str] = []
    for path, line in commands:
        tokens = line.split()
        # Resolve the subcommand path: extend by any token that names a real
        # subcommand, skipping flags, their values, and positional arguments.
        resolved: tuple[str, ...] = ()
        for token in tokens[1:]:
            if not token.startswith("-") and (*resolved, token) in tree:
                resolved = (*resolved, token)
        accepted = tree[resolved] | root_opts
        for token in tokens:
            flag = token.split("=", 1)[0]
            if flag.startswith("--") and flag not in accepted:
                problems.append(
                    f"{path.name}: `aforge {' '.join(resolved)}` does not accept {flag} "
                    f"— in: {line}"
                )
    assert not problems, "documented commands the CLI cannot run:\n" + "\n".join(problems)
