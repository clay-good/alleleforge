"""PAM-anchored, mismatch- and bulge-tolerant protospacer search.

The primitive every off-target pass shares: scan a sequence (both strands) for
PAM-anchored windows within a mismatch/bulge budget of a spacer. The genome-scale
path is the Rust FM-index seed-and-extend kernel (``bwt.rs``); until that crate
is built this module provides a *correct* linear-scan fallback, mirroring how
:mod:`alleleforge.genome.index` degrades. CI never blocks on the native build.

Coordinates returned are 0-based half-open on the **plus** strand; ``strand``
records which strand the protospacer (and so the spacer) reads on.

Bulges follow the CRISPRitz/Cas-OFFinder model: a **DNA bulge** is an extra base
in the genomic target (protospacer one nt longer than the spacer), an **RNA
bulge** an extra base in the spacer (protospacer one nt shorter). Up to one of
each is evaluated independently; a single site is not given both at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from alleleforge.offtarget._kmer import covered_prefix, seed_length, seed_positions
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import IUPAC_EXPAND, DNASequence, Strand

if TYPE_CHECKING:
    from alleleforge.genome.index import FMIndex


class SearchBudget(TypedDict):
    """The mismatch/bulge budget shared by the off-target search call sites."""

    mismatches: int
    dna_bulges: int
    rna_bulges: int


@dataclass(frozen=True)
class SiteProvenance:
    """Where a hit came from and the population context that produced it.

    Attributes:
        origin: Reference, population, or patient origin.
        causal_allele: The allele that creates/modifies the site, if any.
        populations: Populations carrying the causal allele.
        frequency: Allele frequency of the causal allele (max over populations).
        ancestries: Per-ancestry frequency annotation for this site.
        skipped_variants: Variants that were present on the source haplotype but
            not applied (their asserted reference base clashed with the build),
            recorded for audit so a partially-applied haplotype is transparent.
    """

    origin: SiteOrigin
    causal_allele: str | None = None
    populations: tuple[str, ...] = ()
    frequency: float | None = None
    ancestries: dict[str, float] = field(default_factory=dict)
    skipped_variants: tuple[str, ...] = ()


@dataclass(frozen=True)
class Hit:
    """One PAM-anchored off-target alignment.

    Attributes:
        chrom: Contig the hit lies on.
        start: 0-based start of the protospacer on the plus strand.
        end: 0-based half-open end of the protospacer on the plus strand.
        strand: Strand the protospacer/spacer reads on.
        pam_sequence: Concrete PAM bases (5'->3' on ``strand``).
        aligned_spacer: The spacer after any RNA-bulge removal (for scoring).
        aligned_target: The protospacer after any DNA-bulge removal (for scoring).
        mismatches: Base mismatches in the aligned pair.
        dna_bulges: DNA bulges (0 or 1).
        rna_bulges: RNA bulges (0 or 1).
    """

    chrom: str
    start: int
    end: int
    strand: Strand
    pam_sequence: str
    aligned_spacer: str
    aligned_target: str
    mismatches: int
    dna_bulges: int
    rna_bulges: int

    @property
    def edits(self) -> int:
        """Return the total edit count (mismatches + bulges)."""
        return self.mismatches + self.dna_bulges + self.rna_bulges


#: One applied edit relative to a window: ``(rel_start, ref_len, alt_len)``.
AppliedEdit = tuple[int, int, int]


def _alt_coordinate_lift(
    ref_len: int, window_start: int, applied: list[AppliedEdit]
) -> tuple[dict[int, int], dict[int, int]]:
    """Map alt-local boundaries back to genomic coordinates through indels.

    Given the reference-window length, its genomic start, and the length-changing
    edits applied to it (``(rel, ref_len, alt_len)`` in ascending, non-overlapping
    order), return ``(lo, hi)`` dicts from an alt-local boundary index to its
    genomic coordinate — ``lo`` for a span start, ``hi`` for a span end. In a
    1:1 region (before/after/between edits, and across equal-length
    substitutions) both agree and reduce to ``window_start + index``, so an
    all-substitution (SNV) window is placed exactly as an unshifted scan would.
    Inside a length-changing edit a start boundary anchors to the edit's genomic
    start and an end boundary to its genomic end, so a protospacer straddling the
    indel is reported over the whole affected genomic footprint.
    """
    lo: dict[int, int] = {}
    hi: dict[int, int] = {}
    a = 0  # alt-local index
    r = 0  # ref-local index

    def _copy(length: int) -> None:
        nonlocal a, r
        for k in range(length + 1):
            g = window_start + r + k
            lo[a + k] = g
            hi[a + k] = g
        a += length
        r += length

    for rel, rlen, alen in applied:
        _copy(rel - r)  # 1:1 stretch up to this edit
        if rlen == alen:
            _copy(alen)  # substitution: coordinates are unshifted
        else:
            glo = window_start + r
            ghi = window_start + r + rlen
            for k in range(alen + 1):
                lo[a + k] = glo if k < alen else ghi
                hi[a + k] = glo if k == 0 else ghi
            a += alen
            r += rlen
    _copy(ref_len - r)  # trailing 1:1 stretch
    return lo, hi


def _reindex_alt_hits(
    hits: list[Hit], ref_len: int, window_start: int, applied: list[AppliedEdit]
) -> list[Hit]:
    """Reindex hits found on a length-changed alt window to genomic coordinates.

    ``hits`` must carry alt-local coordinates (scanned with ``offset=0``). Each
    hit's ``start``/``end`` is lifted through :func:`_alt_coordinate_lift`.
    """
    if not applied:
        return [replace(h, start=window_start + h.start, end=window_start + h.end) for h in hits]
    lo, hi = _alt_coordinate_lift(ref_len, window_start, applied)
    return [replace(h, start=lo[h.start], end=hi[h.end]) for h in hits]


def _best_ungapped(spacer: str, window: str, max_mm: int) -> int | None:
    """Return the mismatch count of an equal-length alignment, or ``None``."""
    mm = sum(a != b for a, b in zip(spacer, window, strict=True))
    return mm if mm <= max_mm else None


def _best_with_removed_base(longer: str, shorter: str, max_mm: int) -> tuple[int, str] | None:
    """Best ``(mismatches, reduced_longer)`` over removing one base from ``longer``.

    ``longer`` is one base longer than ``shorter``; each base is removed in turn
    and the equal-length comparison with the fewest mismatches (within budget) is
    returned, along with the reduced ``longer`` string, or ``None`` if always
    over budget.
    """
    best: tuple[int, str] | None = None
    for r in range(len(longer)):
        reduced = longer[:r] + longer[r + 1 :]
        mm = sum(a != b for a, b in zip(reduced, shorter, strict=True))
        if mm <= max_mm and (best is None or mm < best[0]):
            best = (mm, reduced)
    return best


def _evaluate(
    spacer: str,
    seq: str,
    pam_at: int,
    pam_len: int,
    *,
    max_mm: int,
    dna_bulges: int,
    rna_bulges: int,
) -> tuple[int, int, int, int, str, str] | None:
    """Evaluate the protospacer 5' of a PAM at ``pam_at`` in ``seq``.

    Returns ``(proto_start, mismatches, dna_bulge, rna_bulge, aligned_spacer,
    aligned_target)`` for the **edit-minimal** alignment within budget, else
    ``None``. Every in-budget alignment (ungapped, single DNA bulge, single RNA
    bulge) is considered and the one with the fewest total edits is returned — a
    bulged near-perfect match therefore wins over a many-mismatch ungapped one, so
    a site's risk is never under-stated. Ties break deterministically: fewer
    bulges first (ungapped over bulged), then a DNA bulge before an RNA bulge. A
    site is never given both bulge types at once.
    """
    n = len(spacer)
    candidates: list[tuple[int, int, int, int, str, str]] = []
    # Ungapped: protospacer is exactly n bases immediately 5' of the PAM.
    start = pam_at - n
    if start >= 0:
        window = seq[start:pam_at]
        mm = _best_ungapped(spacer, window, max_mm)
        if mm is not None:
            candidates.append((start, mm, 0, 0, spacer, window))
    # DNA bulge: protospacer is n+1 bases (one extra genomic base); remove it so
    # the aligned target is n bases for scoring.
    if dna_bulges >= 1:
        start = pam_at - (n + 1)
        if start >= 0:
            window = seq[start:pam_at]
            best = _best_with_removed_base(window, spacer, max_mm)
            if best is not None:
                mm, reduced_target = best
                candidates.append((start, mm, 1, 0, spacer, reduced_target))
    # RNA bulge: protospacer is n-1 bases (one extra spacer base); remove the
    # extra spacer base so both aligned strings are n-1 bases.
    if rna_bulges >= 1 and n >= 2:
        start = pam_at - (n - 1)
        if start >= 0:
            window = seq[start:pam_at]
            best = _best_with_removed_base(spacer, window, max_mm)
            if best is not None:
                mm, reduced_spacer = best
                candidates.append((start, mm, 0, 1, reduced_spacer, window))
    if not candidates:
        return None

    # Edit-minimal: fewest total edits, then fewest bulges (ungapped wins), then
    # DNA bulge before RNA bulge — a total, deterministic order.
    def _rank(c: tuple[int, int, int, int, str, str]) -> tuple[int, int, int]:
        _start, mm, dnab, rnab, _asp, _atg = c
        return (mm + dnab + rnab, dnab + rnab, rnab)

    return min(candidates, key=_rank)


#: Minimum seed length for the prefilter to be worth it. Below this the seed is
#: too short to be selective (a 4-symbol alphabet saturates short k-mers, so
#: almost every window contains one) and seeding only adds overhead; the scan
#: then falls back to the full brute force. Calibrated from the R2 micro-benchmark
#: (``scripts/native_speedup.py``): k>=5 gives a ~2-4x speedup, k<=4 does not.
MIN_SELECTIVE_K = 5


def _seed_filter(
    spacer: str, seq: str, *, max_mm: int, dna_bulges: int, rna_bulges: int
) -> list[int] | None:
    """Return a covered-index prefix sum for the seed prefilter, or ``None``.

    ``None`` means "do not seed — scan every anchor", which is always correct (a
    full scan is a superset of any prefilter). Seeding is skipped when the seed
    would not be guaranteed (``E + 1 > n``) **or** would not be selective
    (``k < MIN_SELECTIVE_K``); otherwise the returned prefix sum lets the scan
    skip anchors whose protospacer window provably contains no exact seed and
    therefore no in-budget hit.
    """
    k = seed_length(len(spacer), max_mm + dna_bulges + rna_bulges)
    if k < MIN_SELECTIVE_K:
        return None
    positions = seed_positions(seq, spacer, k)
    return covered_prefix(len(seq), positions, k)


def _scan_one_strand(
    spacer: str,
    seq: str,
    pam: PAM,
    *,
    max_mm: int,
    dna_bulges: int,
    rna_bulges: int,
    seed: bool = True,
) -> list[tuple[int, int, str, int, int, int, str, str]]:
    """Scan ``seq`` (read 5'->3') for PAM-anchored hits to ``spacer``.

    With ``seed`` (the default), a k-mer seed prefilter skips anchors whose
    protospacer window cannot contain an in-budget hit; the result is identical to
    the unseeded brute-force scan (the prefilter is a proven superset). Returns
    tuples ``(proto_start, proto_end, pam_seq, mm, dnab, rnab, aligned_spacer,
    aligned_target)`` in ``seq``-local coordinates.
    """
    pam_len = len(pam.pattern)
    n = len(spacer)
    covered = (
        _seed_filter(spacer, seq, max_mm=max_mm, dna_bulges=dna_bulges, rna_bulges=rna_bulges)
        if seed
        else None
    )
    hits: list[tuple[int, int, str, int, int, int, str, str]] = []
    for pam_at in range(len(spacer) - 1, len(seq) - pam_len + 1):
        if covered is not None:
            # Skip before the PAM check: no exact seed in the widest protospacer
            # window (ungapped/DNA-bulge/RNA-bulge) -> provably no in-budget hit.
            lo = max(0, pam_at - (n + 1))
            if covered[pam_at] - covered[lo] == 0:
                continue
        pam_seq = seq[pam_at : pam_at + pam_len]
        if "N" in pam_seq or not pam.matches(pam_seq):
            continue
        result = _evaluate(
            spacer,
            seq,
            pam_at,
            pam_len,
            max_mm=max_mm,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
        )
        if result is None:
            continue
        start, mm, dnab, rnab, a_spacer, a_target = result
        if "N" in seq[start:pam_at]:
            continue  # never nominate a site over a padded / unknown region
        hits.append((start, pam_at, pam_seq, mm, dnab, rnab, a_spacer, a_target))
    return hits


#: The alphabet both the linear scan and the FM-index/native path accept.
_INDEX_ALPHABET = frozenset("ACGTN")


def _sanitize(seq: str) -> str:
    """Map any base outside ``ACGTN`` to ``N`` so both search paths agree.

    The FM-index/native path can only be built over ``ACGTN`` (it raises on any
    other base), while the linear scan would otherwise tolerate dirty bases and
    silently score against them. Folding non-``ACGTN`` to ``N`` up front makes the
    two paths identical — a window containing an unexpected base is skipped by
    both (a site is never nominated over an ``N``), rather than crashing one path
    and silently mis-scoring the other.
    """
    if all(b in _INDEX_ALPHABET for b in seq):
        return seq
    return "".join(b if b in _INDEX_ALPHABET else "N" for b in seq)


def _expand_pam(pam: PAM) -> list[str]:
    """Expand an IUPAC PAM pattern into its concrete ACGT instantiations."""
    choices = [sorted(IUPAC_EXPAND[code]) for code in pam.pattern]
    return ["".join(combo) for combo in product(*choices)]


def _scan_one_strand_fm(
    spacer: str,
    seq: str,
    pam: PAM,
    fm: FMIndex,
    *,
    max_mm: int,
    dna_bulges: int,
    rna_bulges: int,
) -> list[tuple[int, int, str, int, int, int, str, str]]:
    """FM-index seed-and-extend equivalent of :func:`_scan_one_strand`.

    The PAM is the *seed*: instead of testing ``pam.matches`` at every anchor,
    each concrete PAM instantiation is **located** in ``fm`` (an FM-index built
    over ``seq``), giving exactly the PAM-positive anchors directly. Each anchor
    is then **extended** by the same :func:`_evaluate` alignment as the
    brute-force scan, so the result is byte-identical to ``_scan_one_strand``
    (pinned by a parity test) — only the anchor enumeration changes from an
    ``O(n)`` linear pass to an indexed lookup over the genome-scale path.
    """
    pam_len = len(pam.pattern)
    n = len(spacer)
    lo_bound = n - 1  # the brute-force loop's first anchor (room for an RNA bulge)
    hi_bound = len(seq) - pam_len  # last anchor with room for a full PAM
    anchors: set[int] = set()
    for concrete in _expand_pam(pam):
        for pam_at in fm.locate(concrete):
            if lo_bound <= pam_at <= hi_bound:
                anchors.add(pam_at)
    hits: list[tuple[int, int, str, int, int, int, str, str]] = []
    for pam_at in sorted(anchors):
        pam_seq = seq[pam_at : pam_at + pam_len]
        result = _evaluate(
            spacer,
            seq,
            pam_at,
            pam_len,
            max_mm=max_mm,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
        )
        if result is None:
            continue
        start, mm, dnab, rnab, a_spacer, a_target = result
        if "N" in seq[start:pam_at]:
            continue  # never nominate a site over a padded / unknown region
        hits.append((start, pam_at, pam_seq, mm, dnab, rnab, a_spacer, a_target))
    return hits


def scan_sequence(
    chrom: str,
    sequence: str | DNASequence,
    spacer: str | DNASequence,
    pam: PAM,
    *,
    mismatches: int = 4,
    dna_bulges: int = 1,
    rna_bulges: int = 1,
    offset: int = 0,
    seed: bool = True,
    use_fm_index: bool = False,
    fm_cache_dir: str | Path | None = None,
    fm_plus: FMIndex | None = None,
    fm_minus: FMIndex | None = None,
) -> list[Hit]:
    """Scan both strands of ``sequence`` for PAM-anchored hits to ``spacer``.

    Args:
        chrom: Contig name used in the returned plus-strand coordinates.
        sequence: The plus-strand sequence to scan.
        spacer: The guide spacer, 5'->3'.
        pam: The PAM pattern to anchor on (e.g. ``NRG`` to include ``NAG``).
        mismatches: Maximum base mismatches.
        dna_bulges: Maximum DNA bulges (0 or 1).
        rna_bulges: Maximum RNA bulges (0 or 1).
        offset: Added to every coordinate so a scanned sub-window maps back to
            genome coordinates.
        seed: Use the k-mer seed prefilter (default); the result is identical to
            the unseeded scan but skips windows that provably contain no hit. Set
            ``False`` to force the exhaustive brute-force scan.
        use_fm_index: Anchor PAMs through a (content-addressed, cached) FM-index
            seed-and-extend instead of the linear scan. Identical hits (a parity
            test pins this); this is the genome-scale reference path. Ignores
            ``seed`` (the PAM is the index seed).
        fm_cache_dir: Override for the FM-index cache root (used only when
            ``use_fm_index``); defaults to the shared content-addressed cache.
        fm_plus: A prebuilt plus-strand FM-index over ``sequence`` (e.g. a
            persistent, memory-mapped contig index from a :class:`GenomeIndex`);
            engages the FM path and skips rebuilding.
        fm_minus: A prebuilt FM-index over the reverse complement of ``sequence``.

    Returns:
        All hits within budget, as plus-strand :class:`Hit` records.
    """
    seq = _sanitize(str(sequence).upper())
    sp = str(spacer).upper()
    n = len(seq)
    hits: list[Hit] = []

    use_fm = use_fm_index or (fm_plus is not None and fm_minus is not None)
    if use_fm and seq:
        from alleleforge.genome.index import FMIndex

        if fm_plus is None:
            fm_plus = FMIndex.build(seq, cache_dir=fm_cache_dir, in_memory=True)
        if fm_minus is None:
            rc_seq = str(DNASequence(seq).reverse_complement())
            fm_minus = FMIndex.build(rc_seq, cache_dir=fm_cache_dir, in_memory=True)
    else:
        fm_plus = fm_minus = None

    def _plus() -> list[tuple[int, int, str, int, int, int, str, str]]:
        if fm_plus is not None:
            return _scan_one_strand_fm(
                sp,
                seq,
                pam,
                fm_plus,
                max_mm=mismatches,
                dna_bulges=dna_bulges,
                rna_bulges=rna_bulges,
            )
        return _scan_one_strand(
            sp, seq, pam, max_mm=mismatches, dna_bulges=dna_bulges, rna_bulges=rna_bulges, seed=seed
        )

    for local in _plus():
        start, pam_at, pam_seq, mm, dnab, rnab, a_sp, a_tg = local
        hits.append(
            Hit(
                chrom=chrom,
                start=offset + start,
                end=offset + pam_at,
                strand=Strand.PLUS,
                pam_sequence=pam_seq,
                aligned_spacer=a_sp,
                aligned_target=a_tg,
                mismatches=mm,
                dna_bulges=dnab,
                rna_bulges=rnab,
            )
        )
    rc = str(DNASequence(seq).reverse_complement())

    def _minus() -> list[tuple[int, int, str, int, int, int, str, str]]:
        if fm_minus is not None:
            return _scan_one_strand_fm(
                sp,
                rc,
                pam,
                fm_minus,
                max_mm=mismatches,
                dna_bulges=dna_bulges,
                rna_bulges=rna_bulges,
            )
        return _scan_one_strand(
            sp, rc, pam, max_mm=mismatches, dna_bulges=dna_bulges, rna_bulges=rna_bulges, seed=seed
        )

    for local in _minus():
        start, pam_at, pam_seq, mm, dnab, rnab, a_sp, a_tg = local
        # Map the rc-local protospacer span [start, pam_at) back to plus coords.
        plus_start = n - pam_at
        plus_end = n - start
        hits.append(
            Hit(
                chrom=chrom,
                start=offset + plus_start,
                end=offset + plus_end,
                strand=Strand.MINUS,
                pam_sequence=pam_seq,
                aligned_spacer=a_sp,
                aligned_target=a_tg,
                mismatches=mm,
                dna_bulges=dnab,
                rna_bulges=rnab,
            )
        )
    return hits
