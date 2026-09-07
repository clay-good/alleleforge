"""Reading a BED file of intervals, with the conventions a reader has to get right.

This was written inline in ``cli/main.py``, which made it the only way to scope a search
to a gene panel and left a Python caller to re-derive the parts that are easy to get
wrong: which lines are headers, that a BED start is 0-based and its end exclusive, and
that an interval naming no bases is not a restriction but an erasure.

That last one had already diverged. ``GenomicInterval.parse`` rejects an empty interval —
its docstring says it is "shared by every surface that accepts a locus from a user, so the
CLI and the web API cannot drift into accepting different spellings" — while the inline
BED reader constructed intervals directly and so accepted one. The same interval was a
usage error spelled ``--region chr1:100-100`` and silently accepted spelled as a BED row,
in the same command, and a scope of zero bases reports every guide as clean.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from alleleforge.types.sequence import GenomicInterval, Strand

__all__ = ["BED_HEADER_PREFIXES", "read_bed_intervals"]

#: Line prefixes a BED file uses for anything that is not a feature. `track` and
#: `browser` are UCSC display directives; `#` is a comment.
BED_HEADER_PREFIXES: tuple[str, ...] = ("#", "track", "browser")


def read_bed_intervals(path: str | Path) -> list[GenomicInterval]:
    """Return the intervals a BED file names, in file order.

    Only the first three columns are read — ``chrom``, ``start``, ``end`` — and they are
    taken at BED's own convention, which is this project's throughout: 0-based start,
    exclusive end. Header and comment lines are skipped; blank lines are ignored.

    Args:
        path: The BED file to read.

    Returns:
        One :class:`GenomicInterval` per feature line, plus-strand.

    Raises:
        ValueError: On a line with fewer than three columns, a non-integer coordinate,
            or an interval naming no bases. The message names the line number, because a
            panel file is long and "invalid literal for int()" is not a location.
        OSError: If the file cannot be read.
    """
    intervals: list[GenomicInterval] = []
    for number, line in enumerate(Path(path).read_text().splitlines(), start=1):
        if not line.strip() or line.startswith(BED_HEADER_PREFIXES):
            continue
        columns = line.split()
        if len(columns) < 3:
            raise ValueError(
                f"line {number}: a BED feature needs chrom, start and end; got {line.strip()!r}"
            )
        try:
            start, end = int(columns[1]), int(columns[2])
        except ValueError as exc:
            raise ValueError(
                f"line {number}: start and end must be integers; got "
                f"{columns[1]!r} and {columns[2]!r}"
            ) from exc
        if end <= start:
            # The same refusal `GenomicInterval.parse` makes for `chrom:start-end`. A
            # region list of empty intervals restricts a search to nothing and reports
            # every guide as perfectly specific, which is the failure this whole file
            # exists to keep out of a panel.
            raise ValueError(
                f"line {number}: interval names no bases ({end} <= {start}); a BED end is "
                "exclusive, so a feature at position N spans N to N+1"
            )
        intervals.append(
            GenomicInterval(chrom=columns[0], start=start, end=end, strand=Strand.PLUS)
        )
    return intervals


def merge_region_arguments(
    loci: Iterable[str] | None, bed: str | Path | None
) -> list[GenomicInterval] | None:
    """Merge locus strings and a BED file into one restriction list, or ``None``.

    ``None`` means "search everything", which is what the engine defaults to — so an
    empty result stays ``None`` rather than becoming an empty list, which would restrict
    the search to nothing and report a spotless guide.

    Both inputs go through the same validation: a locus string via
    :meth:`GenomicInterval.parse`, a BED row via :func:`read_bed_intervals`.

    Args:
        loci: ``chrom:start-end`` strings, if any.
        bed: A BED file, if one was given.

    Returns:
        The intervals to restrict to, or ``None`` for no restriction.

    Raises:
        ValueError: On a malformed locus or BED line.
        OSError: If the BED file cannot be read.
    """
    out = [GenomicInterval.parse(text) for text in loci or ()]
    if bed is not None:
        out.extend(read_bed_intervals(bed))
    return out or None
