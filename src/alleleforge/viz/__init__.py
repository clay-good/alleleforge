"""Reproducible, dependency-free SVG figures for the docs and methods preprint.

The figures are computed from the weight-free, deterministic pipeline and rendered
without a plotting stack — see :mod:`alleleforge.viz.figures` for the figure set and
:mod:`alleleforge.viz.svg` for the renderer.
"""

from __future__ import annotations

from alleleforge.viz.figures import FIGURES, render_all_figures

__all__ = ["FIGURES", "render_all_figures"]
