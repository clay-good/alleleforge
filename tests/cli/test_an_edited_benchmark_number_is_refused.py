"""A published benchmark number cannot be silently edited — through the command.

The README's design-decisions table says results are content-addressed so "a published
benchmark number cannot be silently edited (each result carries a `signature`)". The
machinery is well tested: `verify_signature` hashes the whole model, and a test asserts the
reproducibility digest changes when `dataset_is_synthetic` flips.

What was not tested is the sentence a reader believes, which is about the *command*: open
the JSON, change a number, run `aforge bench leaderboard`. That is what an editing attack
looks like, and it is one line away from the digest test in mechanism and a long way from it
in evidence.

Two edits, because they are different claims. Changing a metric is the obvious one.
Flipping `dataset_is_synthetic` from `True` to `False` is the one this project's honesty
rests on: every bundled corpus is a synthetic stand-in, every result over one says so, and a
forged flag turns a number from a toy into an apparent measurement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def signed(tmp_path: Path) -> Path:
    out = tmp_path / "result.json"
    written = CliRunner().invoke(app, ["bench", "run", "cas9-efficiency", "--out", str(out)])
    assert written.exit_code == ExitCode.OK, written.stderr
    payload = json.loads(out.read_text())
    assert payload["signature"], "the result carries no signature to forge"
    assert payload["dataset_is_synthetic"] is True, "the bundled corpus is a stand-in"
    return out


def _board(path: Path) -> object:
    return CliRunner().invoke(app, ["bench", "leaderboard", str(path)])


def test_the_honest_result_is_admitted(signed: Path) -> None:
    """Without this, a board that refused everything would pass the checks below."""
    assert _board(signed).exit_code == ExitCode.OK, _board(signed).stderr  # type: ignore[attr-defined]


def test_an_edited_metric_is_refused(signed: Path, tmp_path: Path) -> None:
    payload = json.loads(signed.read_text())
    payload["metrics"]["ece"] = 0.01  # a better number than the run produced
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(payload, indent=2))

    result = _board(edited)
    assert result.exit_code == ExitCode.USAGE, result.stdout  # type: ignore[attr-defined]
    assert "edited after signing" in result.stderr  # type: ignore[attr-defined]


def test_a_forged_synthetic_flag_is_refused(signed: Path, tmp_path: Path) -> None:
    """The edit this project's honesty rests on.

    Every bundled corpus is a synthetic stand-in and every result over one says so. A
    flipped flag turns a number from a toy into an apparent measurement, without touching
    the number at all.
    """
    payload = json.loads(signed.read_text())
    payload["dataset_is_synthetic"] = False
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps(payload, indent=2))

    result = _board(forged)
    assert result.exit_code == ExitCode.USAGE, result.stdout  # type: ignore[attr-defined]
    assert "signature" in result.stderr  # type: ignore[attr-defined]


def test_the_refusal_names_the_task_it_rejected(signed: Path, tmp_path: Path) -> None:
    """A board aggregates many results; "one of these is forged" is not actionable."""
    payload = json.loads(signed.read_text())
    payload["primary_value"] = 0.99
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(payload, indent=2))
    assert "cas9-efficiency" in _board(edited).stderr  # type: ignore[attr-defined]
