"""A documented command that resolves is not a documented command that works.

This repo has four guards over its own docs — every command the prose invokes exists,
every flag it names exists, every local link resolves, every module path is importable —
and all four check that a *name* resolves. `docs/api/benchmark.md` documented

    aforge bench gap cas9-efficiency        # does the score survive a held-out cell type?

which exits `2`: the reference baseline predicts one constant, so its rank correlation is
undefined on both folds and a gap is a subtraction. Every name in that line was real.

So the documented invocations are run. Not all of them can be: most of this tool's
examples name a reference genome, a cohort VCF or a gnomAD release that the reader
supplies, and a test cannot invent an hg38. The rule is mechanical — an argument that
looks like a path and that no earlier command *in the same file* wrote is the reader's to
provide — and it is checked in both directions, so it cannot quietly grow to cover
everything.

Commands are run **in file order in one directory**, because that is how a reader follows
a code block: `bench leaderboard outcome.json offtarget.json` consumes the files the two
`bench run` lines above it wrote, and running it alone would only prove that a missing
input is an error.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

_ROOT = Path(__file__).resolve().parents[1]

#: Suffixes that make an argument a path rather than a value.
_PATHLIKE = (
    ".fa",
    ".fasta",
    ".vcf",
    ".gz",
    ".bcf",
    ".json",
    ".jsonl",
    ".toml",
    ".tsv",
    ".parquet",
    ".html",
    ".pdf",
    ".txt",
    ".bed",
)

#: Options whose value is a path this command *writes*, so a later command in the same
#: block may consume it.
_WRITE_FLAGS = frozenset(
    {"--out", "--summary-tsv", "--summary-parquet", "--manifest", "--output-dir"}
)

#: Documented invocations expected to refuse, as `command` → (exit code, the phrase the
#: file must carry to explain it). An entry is a claim that the refusal is deliberate
#: *and* explained where the reader is looking. Empty today: the one command that could
#: not work moved out of the fenced examples and into prose that explains why.
_EXPECTED_REFUSALS: dict[str, tuple[int, str]] = {}


def _files() -> list[Path]:
    return [*sorted((_ROOT / "docs").rglob("*.md")), _ROOT / "README.md", _ROOT / "CONTRIBUTING.md"]


def _invocations(path: Path) -> list[str]:
    """Return the `aforge …` command lines in ``path``, backslash-continuations joined."""
    commands: list[str] = []
    buffer = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not buffer and not line.startswith("aforge "):
            continue
        if line.endswith("\\"):
            buffer += line[:-1] + " "
            continue
        commands.append((buffer + line).split(" #")[0].strip())
        buffer = ""
    return commands


def _plan(path: Path) -> tuple[list[list[str]], list[list[str]]]:
    """Return ``(runnable, needs_a_file_the_reader_supplies)`` for one document."""
    runnable: list[list[str]] = []
    skipped: list[list[str]] = []
    written: set[str] = set()
    for command in _invocations(path):
        try:
            argv = shlex.split(command)[1:]
        except ValueError:  # pragma: no cover - a malformed quote is a docs bug elsewhere
            continue
        for index, token in enumerate(argv):
            if token in _WRITE_FLAGS and index + 1 < len(argv):
                written.add(argv[index + 1])
        external = [
            token
            for token in argv
            if not token.startswith("-") and token.endswith(_PATHLIKE) and token not in written
        ]
        (skipped if external else runnable).append(argv)
    return runnable, skipped


@pytest.mark.parametrize("path", _files(), ids=lambda p: p.name)
def test_the_documented_commands_run(
    path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runnable, _ = _plan(path)
    if not runnable:
        pytest.skip(f"{path.name} documents no self-contained invocation")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for argv in runnable:
        key = " ".join(argv[:3])
        expected = _EXPECTED_REFUSALS.get(key)
        result = runner.invoke(app, argv)
        if expected is None:
            assert result.exit_code == ExitCode.OK, (
                f"{path.name} documents `aforge {' '.join(argv)}`, which exited "
                f"{result.exit_code}:\n{result.output}{result.stderr}"
            )
            continue
        code, phrase = expected
        assert result.exit_code == code, (
            f"{path.name} documents `aforge {' '.join(argv)}` as refusing with {code}; "
            f"it exited {result.exit_code}"
        )
        assert phrase in path.read_text(encoding="utf-8"), (
            f"{path.name} documents a command that refuses and never says so; a reader "
            "copying it learns only that the tool is broken."
        )


def test_the_plan_covers_the_commands_it_should() -> None:
    """The floor, both ways: the skip rule must neither swallow nor cover everything."""
    plans = {path: _plan(path) for path in _files()}
    ran = [argv for runnable, _ in plans.values() for argv in runnable]
    skipped = [argv for _, skipped in plans.values() for argv in skipped]

    assert len(ran) >= 10, f"only {len(ran)} documented commands are exercised: {ran}"
    assert skipped, "nothing was skipped; the path rule is no longer doing anything"
    # Every skip must name the file it wants, so the rule cannot become a bucket.
    for argv in skipped:
        assert any(token.endswith(_PATHLIKE) for token in argv), argv
    # And every command that reaches a genome must be among the skips: a test cannot
    # invent an hg38, and a guard that pretended otherwise would be checking a stub.
    assert all("--reference-fasta" not in argv for argv in ran), ran


def test_the_recorded_refusals_are_still_documented() -> None:
    """An allowance must not outlive the line that needed it."""
    documented = {
        " ".join(argv[:3]) for path in _files() for argv in _plan(path)[0] + _plan(path)[1]
    }
    stale = sorted(set(_EXPECTED_REFUSALS) - documented)
    assert not stale, f"refusals recorded for commands the docs no longer show: {stale}"
