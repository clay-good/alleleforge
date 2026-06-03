"""Small shared I/O helpers for the data-layer parsers.

The Phase 3 parsers all read plain-text (optionally gzipped) fixtures line by
line. :func:`open_text` centralizes the gzip-vs-plain decision so each parser
stays focused on its format.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from pathlib import Path


def open_text(path: str | Path) -> Iterator[str]:
    """Yield decoded text lines from a plain or ``.gz`` file."""
    p = Path(path)
    if p.suffix == ".gz":
        with gzip.open(p, "rt") as fh:
            yield from fh
    else:
        with p.open("rt") as fh:
            yield from fh
