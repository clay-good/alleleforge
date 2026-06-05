"""The calibration-study script regenerates the CRISPR-Bench calibration report."""

from __future__ import annotations

from pathlib import Path

from scripts import calibration_study


def test_task_table_reports_ece_for_every_task() -> None:
    rows = calibration_study.task_calibration_table()
    assert {r["task"] for r in rows} == set(calibration_study.TASKS)
    # ECE (the honesty metric) is present and in range for every task.
    for r in rows:
        assert 0.0 <= r["ece"] <= 1.0
        assert r["kind"] in {"regression", "distribution", "classification"}


def test_generalization_table_covers_cell_type_tasks() -> None:
    rows = calibration_study.generalization_table()
    tasks = {r["task"] for r in rows}
    # The four cell-type-stratified chemistry tasks are reported; off-target
    # (sequence-pair stratified, no cell type) is excluded.
    assert "offtarget-classification" not in tasks
    assert {"cas9-efficiency", "pe-efficiency", "cas9-outcome", "be-outcome"} <= tasks
    for r in rows:
        assert r["held_out_context"]  # the held-out context is labeled
        assert isinstance(r["gap"], float)


def test_conformal_demo_restores_coverage() -> None:
    rows = calibration_study.conformal_demo()
    assert {r["level"] for r in rows} == set(calibration_study.LEVELS)
    for r in rows:
        assert r["raw_coverage"] < 0.4  # the synthetic set is badly under-covering
        assert r["recalibrated_coverage"] >= r["level"] - 0.03  # restored to nominal


def test_main_writes_and_prints_report(tmp_path: Path, capsys: object) -> None:
    out = tmp_path / "calibration_report.md"
    assert calibration_study.main(["--out", str(out)]) == 0
    report = out.read_text()
    assert "# CRISPR-Bench calibration report" in report
    assert "Cross-cell-type generalization gap" in report
    assert "Conformal interval recalibration" in report
    for task in calibration_study.TASKS:
        assert task in report
