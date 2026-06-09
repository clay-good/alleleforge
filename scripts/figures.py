#!/usr/bin/env python
"""Regenerate the committed docs/preprint figures (dependency-free SVG).

Every figure is computed from the weight-free, deterministic pipeline and rendered
without a plotting stack, so it regenerates byte-for-byte from config plus seed.

Usage:
    python scripts/figures.py                       # write to docs/assets/figures
    python scripts/figures.py --out-dir docs/assets/figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

from alleleforge.viz import render_all_figures

#: Where the committed figures live (served by mkdocs, embedded in README/preprint).
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs" / "assets" / "figures"


def main(argv: list[str] | None = None) -> int:
    """Render every figure to the output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args(argv)

    written = render_all_figures(args.out_dir)
    for stem, path in written.items():
        print(f"wrote {stem:22s} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
