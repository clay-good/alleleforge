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


# --- bench leaderboard ------------------------------------------------------


def _write_result(runner: CliRunner, task: str, path: Path) -> Path:
    """Produce one signed result JSON via `bench run --out`."""
    res = runner.invoke(app, ["bench", "run", task, "--out", str(path)])
    assert res.exit_code == 0
    return path


def test_bench_leaderboard_markdown(runner: CliRunner, tmp_path: Path) -> None:
    eff = _write_result(runner, "cas9-efficiency", tmp_path / "eff.json")
    ot = _write_result(runner, "offtarget-classification", tmp_path / "ot.json")
    result = runner.invoke(app, ["bench", "leaderboard", str(eff), str(ot)])
    assert result.exit_code == 0
    assert "# CRISPR-Bench Leaderboard" in result.output
    assert "## cas9-efficiency" in result.output and "## offtarget-classification" in result.output
    assert "crispr-bench-baseline" in result.output and "ECE" in result.output


def test_bench_leaderboard_html_to_file(runner: CliRunner, tmp_path: Path) -> None:
    eff = _write_result(runner, "cas9-efficiency", tmp_path / "eff.json")
    out = tmp_path / "board.html"
    result = runner.invoke(
        app, ["bench", "leaderboard", str(eff), "--format", "html", "--out", str(out)]
    )
    assert result.exit_code == 0
    assert out.read_text().startswith("<!doctype html>")
    assert "CRISPR-Bench Leaderboard" in out.read_text()


def test_bench_leaderboard_missing_file_is_missing_data(runner: CliRunner) -> None:
    result = runner.invoke(app, ["bench", "leaderboard", "/no/such/result.json"])
    assert result.exit_code == ExitCode.MISSING_DATA


def test_bench_leaderboard_rejects_tampered_result(runner: CliRunner, tmp_path: Path) -> None:
    # Editing a result after signing must break the signature gate -> USAGE exit.
    path = _write_result(runner, "cas9-efficiency", tmp_path / "eff.json")
    payload = json.loads(path.read_text())
    payload["primary_value"] = 0.999  # tamper with the score, keep the old signature
    path.write_text(json.dumps(payload))
    result = runner.invoke(app, ["bench", "leaderboard", str(path)])
    assert result.exit_code == ExitCode.USAGE
    assert "signature" in result.output.lower() or "inadmissible" in result.output.lower()


def test_bench_leaderboard_invalid_json_is_usage(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not a result}")
    result = runner.invoke(app, ["bench", "leaderboard", str(bad)])
    assert result.exit_code == ExitCode.USAGE
