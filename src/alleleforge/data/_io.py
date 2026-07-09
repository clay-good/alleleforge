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
    """Yield decoded text lines from a plain or ``.gz`` file.

    Decoded as UTF-8 with ``utf-8-sig`` so a leading byte-order mark — the default
    when a VCF/TSV is exported from Excel or edited in Windows Notepad — is
    stripped rather than riding on the first field (which would break header
    detection, e.g. ``'﻿#...'.startswith('#')`` is ``False``). The encoding
    is pinned so a reader does not depend on the platform locale.
    """
    p = Path(path)
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8-sig") as fh:
            yield from fh
    else:
        with p.open("rt", encoding="utf-8-sig") as fh:
            yield from fh
