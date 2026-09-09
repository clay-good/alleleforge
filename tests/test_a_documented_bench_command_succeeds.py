"""The docs told a reader to run a command that refuses.

`docs/api/benchmark.md` documented `aforge bench gap cas9-efficiency` as the way to ask
"does the score survive a held-out cell type?". Once an undefined metric stopped being
reported as `0.0`, that command exits `2`: the reference baseline predicts one constant,
its rank correlation is undefined on both folds, and there is no gap to subtract. Correct
behaviour, wrong example — and the existing docs guards could not see it, because they
check that a documented command *exists* and that its flags exist, not that running it
works.

That gap is the general shape here. A command's name surviving a rename is the cheap half;
what the reader actually finds out is whether it runs. These are small, fixture-backed
commands over bundled synthetic splits, so running them is affordable — which is the only
reason "does it exist" was ever an acceptable substitute.

A documented command that is *meant* to fail is allowed, and has to say so in the prose
next to it: the entry records the expected exit code and the file must explain the refusal
within a few lines, so "this command refuses" stays a documented behaviour rather than a
silent breakage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

_DOCS = Path(__file__).resolve().parents[1] / "docs"
_README = Path(__file__).resolve().parents[1] / "README.md"

#: Documented `aforge bench …` invocations that are expected to refuse, with the exit code
#: and the phrase the surrounding prose must carry to explain it. An entry here is a claim
#: that the refusal is deliberate *and* explained where the reader is looking. Empty today:
#: `bench gap cas9-efficiency` was moved out of the fenced examples and into prose that
#: explains the refusal, which is the better answer when a command genuinely cannot work.
_EXPECTED_REFUSALS: dict[str, tuple[int, str]] = {}


def _documented_bench_commands() -> dict[Path, list[list[str]]]:
    """Return each file's `aforge bench …` invocations, in the order it shows them.

    Grouped by file and run in order in one directory, because that is how a reader
    follows a code block: the leaderboard line consumes the result files the `run` lines
    above it wrote, and checking it in isolation would only ever prove that a missing
    input is an error.
    """
    found: dict[Path, list[list[str]]] = {}
    for path in [*sorted(_DOCS.rglob("*.md")), _README]:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.split("#")[0].strip()
            if not stripped.startswith("aforge bench "):
                continue
            argv = stripped.split()[1:]
            # `*.json` is a shell glob the reader expands, not an argument this can pass.
            if any("*" in token for token in argv):
                continue
            found.setdefault(path, []).append(argv)
    assert sum(len(v) for v in found.values()) >= 4, f"parsed {found} — this would be vacuous"
    return found


@pytest.mark.parametrize("path", sorted(_documented_bench_commands()), ids=lambda p: p.name)
def test_the_documented_bench_commands_run(
    path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for argv in _documented_bench_commands()[path]:
        result = runner.invoke(app, argv)
        key = " ".join(argv[:3])
        expected = _EXPECTED_REFUSALS.get(key)
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
            f"copying it learns only that the tool is broken."
        )


def test_the_recorded_refusals_are_still_documented() -> None:
    """An allowance must not outlive the line that needed it."""
    documented = {
        " ".join(argv[:3]) for argvs in _documented_bench_commands().values() for argv in argvs
    }
    stale = sorted(set(_EXPECTED_REFUSALS) - documented)
    assert not stale, f"refusals recorded for commands the docs no longer show: {stale}"
