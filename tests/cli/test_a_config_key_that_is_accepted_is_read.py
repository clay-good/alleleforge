"""A whitelisted config key must be read by the command that accepts it.

Round 573's lesson was that a knob whose over-large value produces no error and no
missing output produces the one artifact nobody checks: a smaller answer. `--config` is
the same shape one level up. `_load_config` warns about a key it does not recognise, so
silence means "accepted" — and its whitelist was one shared set holding every knob
*either* command has:

    $ aforge batch cohort.txt --config c.toml ...   # c.toml: vector_scheme = "aav"
    cohort: 1 requested - 1 designed (1 ok, 0 failed)
    $ echo $?
    0

No scheme was used, and no such scheme exists — `aforge design` refuses that same file
as a usage error. `trained_prime = true` was the higher-stakes half: the cohort was
designed by the heuristic baseline (`pridict2-baseline`) while the user believed they had
opted into the trained model, with the opt-in silently dropped on the one command whose
runs are large enough that nobody re-reads a single item's provenance.

The guard below derives what each command reads from the command's own source, so the
declaration cannot drift from the code again in either direction — a key declared and
never read, or read and never declared.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli import main as cli_main
from alleleforge.cli.main import _RUN_PARAM_KEYS, ExitCode, app


def _module_tree() -> ast.Module:
    return ast.parse(inspect.getsource(cli_main))


def _reads_by_function() -> dict[str, set[str]]:
    """Every ``cfg.get("k")`` / ``cfg["k"]`` / ``"k" in cfg`` literal, per function."""
    reads: dict[str, set[str]] = {}
    for node in ast.walk(_module_tree()):
        if not isinstance(node, ast.FunctionDef):
            continue
        keys: set[str] = set()
        for sub in ast.walk(node):
            match sub:
                case ast.Call(
                    func=ast.Attribute(value=ast.Name(id="cfg"), attr="get"),
                    args=[ast.Constant(value=str() as key), *_],
                ):
                    keys.add(key)
                case ast.Subscript(
                    value=ast.Name(id="cfg"), slice=ast.Constant(value=str() as key)
                ):
                    keys.add(key)
                case ast.Compare(
                    left=ast.Constant(value=str() as key),
                    ops=[ast.In()],
                    comparators=[ast.Name(id="cfg")],
                ):
                    keys.add(key)
        reads[node.name] = keys
    return reads


def _calls(function: str) -> set[str]:
    """The names this function calls, so a helper it hands ``cfg`` to counts as a read."""
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            return {
                sub.func.id
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
            }
    raise AssertionError(f"no function named {function} in the CLI module")


def _keys_read(command: str) -> set[str]:
    reads = _reads_by_function()
    keys = set(reads.get(command, set()))
    for called in _calls(command):
        keys |= reads.get(called, set())
    return keys


def test_the_derivation_finds_something() -> None:
    """A derivation returning nothing would make both directions below vacuous."""
    assert "intent" in _keys_read("design")
    assert "run_offtarget" in _keys_read("design")  # read inside a helper, not the body


@pytest.mark.parametrize("command", sorted(_RUN_PARAM_KEYS))
def test_every_accepted_key_is_actually_read(command: str) -> None:
    """The direction that was broken: accepted in silence, read by nothing."""
    unread = _RUN_PARAM_KEYS[command] - _keys_read(command)
    assert not unread, (
        f"`aforge {command}` accepts {sorted(unread)} from a config file without warning "
        "and reads none of them: the run silently ignores what the user asked for"
    )


@pytest.mark.parametrize("command", sorted(_RUN_PARAM_KEYS))
def test_every_key_read_is_declared(command: str) -> None:
    """And the other direction, which would warn about a key that does work."""
    from alleleforge.config import Settings

    undeclared = _keys_read(command) - _RUN_PARAM_KEYS[command] - set(Settings.model_fields)
    assert not undeclared, (
        f"`aforge {command}` reads {sorted(undeclared)} from a config file but warns that "
        "the key is unknown, so a config that works is reported as a typo"
    )


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    path.write_text(">chr2\n" + "AT" * 200 + "\n")
    return path


def _models(directory: Path) -> set[str]:
    menu = json.loads(next(iter(sorted(directory.glob("*.json")))).read_text())
    return {m["name"] for m in menu["provenance"]["models"]}


def test_a_trained_model_opt_in_reaches_a_cohort_through_the_config(
    runner: CliRunner, genome: Path, tmp_path: Path
) -> None:
    """The measurement: the flag and the config file must select the same model.

    Asserted on the *provenance* rather than on the flag's plumbing, because the flag's
    plumbing was fine — it was the config path that dropped it, and provenance is what
    a reader of the run has to go on.
    """
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    config = tmp_path / "c.toml"
    config.write_text("trained_prime = true\n")
    base = ["batch", str(cohort), "--reference-fasta", str(genome), "--no-offtarget"]

    by_config = tmp_path / "by-config"
    by_flag = tmp_path / "by-flag"
    plain = tmp_path / "plain"
    assert runner.invoke(app, [*base, "--config", str(config), "--output-dir", str(by_config)])
    assert runner.invoke(app, [*base, "--trained-prime", "--output-dir", str(by_flag)])
    assert runner.invoke(app, [*base, "--output-dir", str(plain)])

    assert _models(by_config) == _models(by_flag)
    # And the opt-in is not a no-op either way round, which is what makes the line above
    # an assertion about the config rather than about two identical default runs.
    assert _models(by_config) != _models(plain)


def test_a_key_the_command_cannot_use_is_named_against_the_one_that_can(
    runner: CliRunner, genome: Path, tmp_path: Path
) -> None:
    """Not "unknown key": the file is fine, it is being given to the wrong command."""
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    config = tmp_path / "c.toml"
    config.write_text('vector_scheme = "px330-bbsi"\n')
    result = runner.invoke(
        app,
        [
            "batch",
            str(cohort),
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--config",
            str(config),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    assert "vector_scheme" in result.stderr
    assert "`aforge design`" in result.stderr
    assert "not by `aforge batch`" in result.stderr
    assert "unknown config key" not in result.stderr  # it is known; it is misdirected

    # The same file is a working config for the command that reads it.
    ok = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--config",
            str(config),
        ],
    )
    assert ok.exit_code == ExitCode.OK, ok.stderr
    assert "warning: config key" not in ok.stderr


def test_a_real_typo_still_reads_as_a_typo(runner: CliRunner, genome: Path, tmp_path: Path) -> None:
    """The half the new branch could have swallowed: a key no command reads."""
    config = tmp_path / "c.toml"
    config.write_text('vector_schema = "px330-bbsi"\n')
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--config",
            str(config),
        ],
    )
    assert "unknown config key 'vector_schema'" in result.stderr
    assert "known keys:" in result.stderr
