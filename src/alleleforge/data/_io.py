"""Small shared I/O helpers for the data-layer parsers.

The Phase 3 parsers all read plain-text (optionally gzipped) fixtures line by
line. :func:`open_text` centralizes the gzip-vs-plain decision so each parser
stays focused on its format.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from pathlib import Path

_ACGTN = frozenset("ACGTN")


def is_sequence_allele(*alleles: str) -> bool:
    """Return whether every allele is a plain ``ACGTN`` string (case-insensitive).

    VCF ALT columns carry symbolic (`<DEL>`, `<INS>`) and spanning-deletion (`*`)
    alleles that are not literal sequence. The ``Variant`` allele validator rejects
    them, so a parser that lets one reach construction aborts the whole file — one
    such row in a real ClinVar release loses every record after it. Parsers use this
    to *skip* such rows and keep going. An empty string (an indel anchor side) is a
    valid sequence allele and passes.
    """
    return all(not (set(a.upper()) - _ACGTN) for a in alleles)


def open_text(path: str | Path) -> Iterator[str]:
    """Yield decoded text lines from a plain or gzip-compressed file.

    Compression is detected from the **gzip magic bytes**, not the extension. That was
    `p.suffix == ".gz"`, and it could not open the files two of this project's own
    datasets are published as: gnomAD releases
    ``gnomad.genomes.v4.1.sites.chr22.vcf.bgz`` (bgzip — gzip-compatible, different
    suffix), and a caller's extract may carry no suffix at all. The failure was not a
    clear refusal either; the gzip bytes reached the UTF-8 decoder and surfaced as
    ``UnicodeDecodeError: invalid start byte``, which reads as a corrupt file rather than
    an unrecognised name.

    bgzf is a series of concatenated gzip members, which :mod:`gzip` reads as one stream,
    so no special handling is needed beyond recognising it.

    Decoded as UTF-8 with ``utf-8-sig`` so a leading byte-order mark — the default
    when a VCF/TSV is exported from Excel or edited in Windows Notepad — is
    stripped rather than riding on the first field (which would break header
    detection, e.g. ``'﻿#...'.startswith('#')`` is ``False``). The encoding
    is pinned so a reader does not depend on the platform locale.
    """
    p = Path(path)
    if _is_gzipped(p):
        with gzip.open(p, "rt", encoding="utf-8-sig") as fh:
            yield from fh
    else:
        with p.open("rt", encoding="utf-8-sig") as fh:
            yield from fh


def _is_gzipped(path: Path) -> bool:
    """Whether ``path`` begins with the gzip magic bytes.

    An unreadable or empty file reads as "not gzipped" so the caller's own open raises
    the error it would have raised anyway — this helper exists to choose a decoder, not
    to validate a path.
    """
    try:
        with path.open("rb") as fh:
            return fh.read(2) == b"\x1f\x8b"
    except OSError:
        return False
