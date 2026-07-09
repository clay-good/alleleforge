"""Tests for the shared data-layer I/O helper."""

from __future__ import annotations

import gzip
from pathlib import Path

from alleleforge.data._io import open_text


def test_open_text_strips_utf8_bom(tmp_path: Path) -> None:
    # A VCF/TSV exported from Excel or edited in Windows Notepad carries a UTF-8
    # BOM. Without stripping it, the first line reads '﻿#...', so header
    # detection (`line.startswith('#')`) fails and the header is parsed as data.
    p = tmp_path / "clinvar.tsv"
    p.write_bytes("﻿#fileformat=VCFv4.2\nchr1\t100\n".encode())
    first = next(iter(open_text(p)))
    assert not first.startswith("﻿")
    assert first.startswith("#")  # header detection works again


def test_open_text_strips_bom_in_gzip(tmp_path: Path) -> None:
    p = tmp_path / "clinvar.tsv.gz"
    with gzip.open(p, "wb") as fh:
        fh.write("﻿#header\ndata\n".encode())
    assert next(iter(open_text(p))).startswith("#")


def test_open_text_reads_utf8_content(tmp_path: Path) -> None:
    # The reader is pinned to UTF-8, not the platform locale, so non-ASCII data
    # (a gene name like "β-globin") round-trips regardless of LANG/LC_ALL.
    p = tmp_path / "genes.tsv"
    p.write_bytes("β-globin\tHBB\n".encode())
    assert next(iter(open_text(p))).startswith("β-globin")
