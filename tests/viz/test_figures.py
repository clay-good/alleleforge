"""Tests for the reproducible SVG figures (computed from the weight-free pipeline)."""

from __future__ import annotations

from pathlib import Path

from alleleforge.viz import FIGURES, render_all_figures
from alleleforge.viz.figures import (
    conformal_coverage_figure,
    generalization_gap_figure,
    reference_bias_data,
    reference_bias_figure,
    task_ece_figure,
)


def test_reference_bias_data_matches_acceptance_case() -> None:
    ref_only, pop_aware, cfd, ancestries = reference_bias_data()
    assert ref_only == 0  # a reference-only scan is blind to the off-target
    assert pop_aware == 1  # the population-aware scan nominates it
    assert cfd >= 0.20  # high-CFD off-target
    assert ancestries["afr"] == max(ancestries.values())  # AFR-enriched


def test_every_builder_renders_valid_svg() -> None:
    for builder in (
        reference_bias_figure,
        conformal_coverage_figure,
        task_ece_figure,
        generalization_gap_figure,
    ):
        svg = builder()
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")


def test_figures_are_deterministic() -> None:
    # Same config + seed -> byte-identical SVG (safe to commit and diff).
    for builder in FIGURES.values():
        assert builder() == builder()


def test_conformal_figure_shows_recalibrated_above_raw() -> None:
    svg = conformal_coverage_figure()
    assert "Raw coverage" in svg and "Recalibrated coverage" in svg
    assert "target 80%" in svg  # the nominal-level reference line


def test_render_all_writes_every_figure(tmp_path: Path) -> None:
    written = render_all_figures(tmp_path)
    assert set(written) == set(FIGURES)
    for path in written.values():
        assert path.exists()
        assert path.read_text().startswith("<svg")


def test_render_all_creates_missing_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "figures"
    written = render_all_figures(target)
    assert all(p.parent == target for p in written.values())
