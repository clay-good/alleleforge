"""The ``cyvcf2`` fast path: stream a VCF into the cohort designer (R4).

:func:`design_many <alleleforge.design.cohort.design_many>` already consumes any
iterable lazily, and its docstring promises "a ``cyvcf2`` stream" as a first-class
input. :func:`iter_vcf` is the adapter that *produces* that stream: it reads a VCF
with ``cyvcf2`` (the fastest available parser — a thin wrapper over htslib) and
yields one :class:`~alleleforge.variant.resolver.VcfRecord` per **concrete ALT
allele**, so the whole genome flows through the designer without ever holding more
than the current record in memory.

Three decisions keep this honest and CI-testable:

* **Multi-allelic split.** A VCF row with ``ALT=G,T`` is two distinct biological
  variants; each becomes its own :class:`VcfRecord`. Symbolic (``<DEL>``), spanning
  -deletion (``*``), and non-ACGTN alleles are skipped — the design chemistries
  operate on concrete substitutions and indels, not structural placeholders.
* **PASS-by-default.** Only records the caller (or the upstream filtering pipeline)
  marked ``PASS``/``.`` are yielded unless ``pass_only=False`` — a cohort run
  should not silently design against soft-filtered noise.
* **Injectable reader.** ``cyvcf2`` is an optional, htslib-backed dependency absent
  from the CI default install. :func:`iter_vcf` therefore accepts either a path
  (opened with ``cyvcf2`` lazily, raising a clear :class:`RuntimeError` if it is
  not installed) **or** any already-iterable of records duck-typed to the cyvcf2
  ``Variant`` shape — so the splitting/filtering logic is fully covered by tests
  with a fake reader and no native dependency.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from alleleforge.variant.resolver import VcfRecord

#: Alleles that are not a concrete ACGTN sequence and so cannot be designed against.
_NON_CONCRETE = frozenset({"", "*", "."})


@runtime_checkable
class VcfVariantLike(Protocol):
    """The minimal slice of a ``cyvcf2.Variant`` :func:`iter_vcf` reads.

    ``cyvcf2`` exposes exactly these attributes (1-based ``POS``; ``FILTER`` is
    ``None`` when the column is ``PASS`` or ``.``; ``ALT`` is the list of alternate
    alleles; ``ID`` is the rsID or ``None``). Any object with this shape works,
    which is what makes the path testable without the native library.
    """

    CHROM: str
    POS: int
    REF: str
    ALT: list[str]
    ID: str | None
    FILTER: str | None


def _is_concrete(allele: str) -> bool:
    """Return whether ``allele`` is a designable ACGTN sequence (not symbolic)."""
    a = allele.upper()
    return a not in _NON_CONCRETE and not a.startswith("<") and set(a) <= set("ACGTN")


def _split_record(record: VcfVariantLike, *, pass_only: bool) -> Iterator[VcfRecord]:
    """Yield one :class:`VcfRecord` per concrete ALT of one VCF row."""
    if pass_only and record.FILTER is not None:
        return
    ref = record.REF
    if not _is_concrete(ref):
        return
    rsid = record.ID if (record.ID and record.ID != ".") else None
    for alt in record.ALT:
        if not _is_concrete(alt):
            continue
        yield VcfRecord(chrom=record.CHROM, pos=record.POS, ref=ref, alt=alt, rsid=rsid)


def _open_cyvcf2(source: str) -> Iterable[VcfVariantLike]:
    """Open ``source`` with ``cyvcf2`` (lazily imported).

    Raises:
        RuntimeError: If ``cyvcf2`` is not installed (it is an optional, htslib
            -backed dependency; install the ``genome`` extra).
    """
    try:
        from cyvcf2 import VCF
    except ImportError as exc:  # pragma: no cover - exercised only without cyvcf2
        raise RuntimeError(
            "iter_vcf needs cyvcf2 to read a VCF path; install the 'genome' extra "
            "(pip install 'alleleforge[genome]') or pass an iterable of records."
        ) from exc
    return VCF(source)  # type: ignore[no-any-return]


def iter_vcf(
    source: str | Path | Iterable[VcfVariantLike],
    *,
    pass_only: bool = True,
    opener: Callable[[str], Iterable[VcfVariantLike]] | None = None,
) -> Iterator[VcfRecord]:
    """Stream a VCF as :class:`VcfRecord`s, one per concrete ALT allele.

    The result is a lazy iterator suitable to hand straight to
    :func:`~alleleforge.design.cohort.design_many` — the whole cohort flows through
    the designer with bounded memory.

    Args:
        source: A path to a (optionally ``.gz``/``.bgz``) VCF opened with
            ``cyvcf2``, **or** any already-iterable of records duck-typed to the
            cyvcf2 ``Variant`` shape (e.g. a region query ``VCF(path)("chr1:1-1e6")``
            or a hand-built list in a test).
        pass_only: Skip records whose ``FILTER`` is not ``PASS``/``.`` (the
            default — a cohort run should not design against soft-filtered calls).
        opener: Override the path opener (defaults to ``cyvcf2.VCF``); used to test
            the path branch without the native library.

    Yields:
        One :class:`VcfRecord` per concrete ALT allele, multi-allelic rows split.

    Raises:
        RuntimeError: If a path is given but ``cyvcf2`` is not installed and no
            ``opener`` was supplied.
    """
    if isinstance(source, (str, Path)):
        open_fn = opener or _open_cyvcf2
        records: Iterable[VcfVariantLike] = open_fn(str(source))
    else:
        records = source
    for record in records:
        yield from _split_record(record, pass_only=pass_only)
