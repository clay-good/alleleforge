"""The ``aforge bench`` CLI lists tasks and runs the baseline (Phase 14)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from alleleforge.cli.main import ExitCode, app  # noqa: E402


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_bench_list_human(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "list"])
    assert result.exit_code == 0
    assert "cas9-efficiency" in result.output
    assert "offtarget-classification" in result.output


def test_bench_list_json(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["tasks"]) == 5
    assert all("ece" in t["metrics"] for t in payload["tasks"])


def test_bench_run_human(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "run", "cas9-efficiency"])
    assert result.exit_code == 0
    assert "cas9-efficiency @ v1" in result.output
    assert "ece=" in result.output


def test_bench_run_json(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "run", "offtarget-classification", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task"] == "offtarget-classification"
    assert payload["signature"]


def test_bench_run_writes_file(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    result = runner.invoke(app, ["bench", "run", "pe-efficiency", "--out", str(out)])
    assert result.exit_code == 0
    assert out.is_file()
    payload = json.loads(out.read_text())
    assert payload["task"] == "pe-efficiency"


def test_bench_run_unknown_task(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "run", "nope"])
    assert result.exit_code == ExitCode.USAGE


def test_bench_run_unknown_split(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "run", "cas9-efficiency", "--split-version", "v999"])
    assert result.exit_code == ExitCode.MISSING_DATA


def test_bench_run_split_integrity_failure(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A tampered/drifted split surfaces as a MISSING_DATA exit, not a traceback.
    from alleleforge.benchmark import splits as splits_mod

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise splits_mod.SplitIntegrityError("membership hash mismatch")

    monkeypatch.setattr(splits_mod, "load_split", _raise)
    result = runner.invoke(app, ["bench", "run", "cas9-efficiency"])
    assert result.exit_code == ExitCode.MISSING_DATA
    assert "integrity" in result.output.lower()
