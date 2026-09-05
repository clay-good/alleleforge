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


def test_the_report_says_its_numbers_are_synthetic() -> None:
    """This report is treated as the project's calibration evidence.

    Every number in it comes from the bundled synthetic stand-ins at sample sizes in
    the single digits, and the report said neither — so `spearman 0.0, ECE 0.2` read
    as a measurement of a model rather than a demonstration that the measurement
    machinery works. The preprint says so in prose; the generated artifact did not,
    and the artifact is what gets read and quoted.
    """
    tasks = calibration_study.task_calibration_table()
    report = calibration_study.render_markdown(
        tasks,
        calibration_study.generalization_table(),
        calibration_study.conformal_demo(),
    )

    assert "SYNTHETIC" in report
    assert "not measurements of any model" in report
    # Sample size per row, because a Spearman over ten rows is not a result.
    assert "| n |" in report or "| n | Data |" in report
    for row in tasks:
        assert row["n_test"] > 0
        assert row["synthetic"] is True  # the shipped fixtures really are stand-ins
    # ...and the per-row label, so a future real corpus is visibly different.
    assert "| synthetic |" in report
