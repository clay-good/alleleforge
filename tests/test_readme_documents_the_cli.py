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

import click
import pytest
from typer.main import get_command

from alleleforge.cli.main import app
from tests.prose import prose_text

_ROOT = Path(__file__).resolve().parents[1]


def _command_names() -> list[str]:
    """Return every runnable command, as the path a user types.

    Top-level names are not the whole CLI. `bench compare` and `bench gap` are
    commands a reader has to be told about exactly as much as `verify` is, and both
    guards below were blind to them while `bench` itself was documented — the same
    mistake as checking the corpus instead of the reference page, one level down.
    """
    root = get_command(app)

    def walk(command: click.Command, path: str) -> list[str]:
        subcommands: dict[str, click.Command] = getattr(command, "commands", {})
        if not subcommands:
            return [path]
        return [
            found
            for name, sub in subcommands.items()
            for found in walk(sub, f"{path} {name}".strip())
        ]

    return sorted(walk(root, ""))


def test_every_cli_command_is_named_in_the_docs() -> None:
    names = _command_names()
    assert names, "no commands discovered — the introspection above is wrong, not the docs"

    prose = prose_text(_ROOT / "README.md")
    for path in (_ROOT / "docs").rglob("*.md"):
        prose += prose_text(path)

    missing = [name for name in names if f"aforge {name}" not in prose]
    assert not missing, f"CLI commands documented nowhere: {missing}"


def test_the_cli_reference_lists_every_command_in_its_own_table() -> None:
    """Corpus-wide coverage is not per-surface coverage.

    The check above concatenates the README and every page under `docs/`, so a command
    named in one file counts as documented everywhere. That is exactly how `aforge
    verify` and `aforge lift` came to be missing from the command table on the page
    titled "The `aforge` CLI" — the reference a reader opens to find out what the tool
    can do — while passing a guard whose whole subject is undocumented commands.

    Asking per surface rather than corpus-wide is the correction this project has had to
    make before, for provenance facts. The table is the surface here.
    """
    table = (_ROOT / "docs" / "api" / "cli.md").read_text()
    heading = table.index("| Command | Purpose |")
    rows = table[heading : table.index("\n\n", heading)]
    missing = [name for name in _command_names() if f"`aforge {name}" not in rows]
    assert not missing, (
        f"the CLI reference's command table omits: {missing}. It is the page a reader "
        "opens to learn what the tool does; a command missing from it is undiscoverable "
        "however many other files mention it."
    )


@pytest.mark.parametrize("removed", ["verify", "offtarget"])
def test_the_check_would_notice_a_missing_command(removed: str) -> None:
    """Guard the guard: the assertion above must depend on the prose, not pass blindly."""
    prose = prose_text(_ROOT / "README.md").replace(f"aforge {removed}", "")
    for path in (_ROOT / "docs").rglob("*.md"):
        prose += prose_text(path).replace(f"aforge {removed}", "")
    assert f"aforge {removed}" not in prose
    assert removed in _command_names()


# Paths the prose may legitimately reference before they exist in the repository:
# each needs a reason, so this cannot become a place to hide a broken promise.
_ALLOWED_MISSING_LINKS: dict[str, str] = {}


def _prose_files() -> list[Path]:
    """Every prose surface a reader can reach, not the two this file started with.

    `README.md` + `docs/` was the population of the round that wrote these checks. The
    question — does a link resolve, is a cited module importable, does a documented
    command exist — has a wider one: `CONTRIBUTING.md`, the two root specs, the seven
    planning documents in `specs/`, and the package README the top-level README links to.
    `openspec/changes/README.md` stays out: it is the audit log, and it quotes historical
    mistakes on purpose.
    """
    files = [
        _ROOT / "README.md",
        _ROOT / "CONTRIBUTING.md",
        _ROOT / "CODE_OF_CONDUCT.md",
        _ROOT / "RELEASE.md",
        _ROOT / "SECURITY.md",
        _ROOT / "SPEC.md",
        _ROOT / "SPEC_V2.md",
        _ROOT / "openspec" / "AGENTS.md",
        _ROOT / "openspec" / "project.md",
        *sorted((_ROOT / "docs").rglob("*.md")),
        *sorted((_ROOT / "specs").glob("*.md")),
        *sorted((_ROOT / "openspec" / "specs").rglob("*.md")),
        *sorted((_ROOT / "src").rglob("README.md")),
        # The example notebooks carry reader-facing markdown cells — the
        # coordinate-convention warning among them — which `read_text()` on a `.ipynb`
        # would have handed these checks as JSON. `prose_text` unwraps them.
        *sorted((_ROOT / "examples").glob("*.ipynb")),
    ]
    # The corpus is the thing every check in this file scans, and a check that scans
    # nothing reports nothing broken. Neutralizing this helper left five of the six
    # tests here green, so the floor belongs at the source rather than in each caller.
    assert len(files) > 5, f"the prose corpus did not resolve: {files}"
    assert all(f.is_file() for f in files), (
        f"missing prose files: {[f for f in files if not f.is_file()]}"
    )
    return files


def test_every_local_link_in_the_prose_resolves() -> None:
    """A README link that 404s is a claim the repository cannot back.

    Found the code-of-conduct promise: `CONTRIBUTING.md` and the README both told a
    contributor to read a Contributor Covenant that was not in the repository.
    """
    import re

    broken: list[str] = []
    checked = 0
    for path in _prose_files():
        text = prose_text(path)
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
            checked += 1
            if (_ROOT / target).exists() or (path.parent / target).exists():
                continue
            broken.append(f"{path.relative_to(_ROOT)} -> {target}")
    assert checked > 20, f"only {checked} local links were examined; the link scan is not working"
    assert not broken, f"prose links to files that do not exist: {broken}"


def test_every_module_path_the_prose_cites_is_importable() -> None:
    """`alleleforge.foo.bar` in the prose must still be somewhere in the package."""
    import importlib
    import re

    prose = "\n".join(prose_text(p) for p in _prose_files())
    cited = sorted(set(re.findall(r"`(alleleforge(?:\.[a-z_]+)+)`", prose)))
    assert len(cited) > 10, f"only {len(cited)} module paths were found; the scan is not working"
    broken: list[str] = []
    for dotted in cited:
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
        for block in re.findall(r"```(?:bash|console|sh)\n(.*?)```", prose_text(path), re.S):
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


#: Config files a documented command names that the repository does not ship, each with
#: the reason. A file the docs tell a reader to *use* must exist; one the docs teach them
#: to *write* must not.
_CALLER_SUPPLIED_CONFIGS: dict[str, str] = {
    "run.toml": "the reproducible-run config a reader writes themselves; the CLI page "
    "shows its contents immediately above the command that consumes it",
}


def _configs_named_in_commands() -> dict[str, list[str]]:
    """Return {path: documents} for every config file named in a documented command."""
    import re

    pattern = re.compile(r"[\w./-]+\.(?:ya?ml|toml|cfg|ini)\b")
    found: dict[str, list[str]] = {}
    for path in [
        _ROOT / "README.md",
        _ROOT / "CONTRIBUTING.md",
        *sorted((_ROOT / "docs").rglob("*.md")),
    ]:
        if not path.is_file():
            continue
        for block in re.findall(
            r"```(?:bash|sh|console)?\n(.*?)```", path.read_text(encoding="utf-8"), re.S
        ):
            for line in block.splitlines():
                if line.strip().startswith("#"):
                    continue
                for name in pattern.findall(line):
                    found.setdefault(name, []).append(path.name)
    assert found, "no config files named in any documented command — check is vacuous"
    return found


def test_every_config_a_documented_command_names_exists() -> None:
    """A setup command that names a file the repository does not have fails immediately.

    CONTRIBUTING said "a conda environment is also provided" and gave `conda env create -f
    environment.yml`. There has never been an `environment.yml`; the repository ships
    `conda/meta.yaml`, a bioconda packaging recipe, which is a different thing for a
    different purpose. It is the second command in the contributor guide, so it failed in
    a new contributor's first five minutes.

    The local-link guard above cannot see this: the name is an argument inside a fenced
    command, not a Markdown link. Same class of claim, different syntax.
    """
    missing = sorted(
        f"{name} (in {sorted(set(where))})"
        for name, where in _configs_named_in_commands().items()
        if not (_ROOT / name).exists() and name not in _CALLER_SUPPLIED_CONFIGS
    )
    assert not missing, (
        f"documented commands name config files this repository does not ship: {missing}. "
        "Add the file, fix the command, or — if the reader is meant to write it — record "
        "it in _CALLER_SUPPLIED_CONFIGS with that reason."
    )


def test_no_caller_supplied_allowance_names_a_file_that_exists() -> None:
    """If the repository ships it, it is not something the reader writes."""
    shipped = sorted(n for n in _CALLER_SUPPLIED_CONFIGS if (_ROOT / n).exists())
    assert not shipped, f"_CALLER_SUPPLIED_CONFIGS excuses files the repo has: {shipped}"
