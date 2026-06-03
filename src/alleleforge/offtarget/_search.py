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

from dataclasses import dataclass, field

from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import SiteOrigin
from alleleforge.types.sequence import DNASequence, Strand


@dataclass(frozen=True)
class SiteProvenance:
    """Where a hit came from and the population context that produced it.

    Attributes:
        origin: Reference, population, or patient origin.
        causal_allele: The allele that creates/modifies the site, if any.
        populations: Populations carrying the causal allele.
        frequency: Allele frequency of the causal allele (max over populations).
        ancestries: Per-ancestry frequency annotation for this site.
    """

    origin: SiteOrigin
    causal_allele: str | None = None
    populations: tuple[str, ...] = ()
    frequency: float | None = None
    ancestries: dict[str, float] = field(default_factory=dict)


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
    aligned_target)`` for the best alignment within budget, else ``None``. The
    ungapped alignment wins ties; bulged alignments are only tried when allowed.
    """
    n = len(spacer)
    # Ungapped: protospacer is exactly n bases immediately 5' of the PAM.
    start = pam_at - n
    if start >= 0:
        window = seq[start:pam_at]
        mm = _best_ungapped(spacer, window, max_mm)
        if mm is not None:
            return (start, mm, 0, 0, spacer, window)
    # DNA bulge: protospacer is n+1 bases (one extra genomic base); remove it so
    # the aligned target is n bases for scoring.
    if dna_bulges >= 1:
        start = pam_at - (n + 1)
        if start >= 0:
            window = seq[start:pam_at]
            best = _best_with_removed_base(window, spacer, max_mm)
            if best is not None:
                mm, reduced_target = best
                return (start, mm, 1, 0, spacer, reduced_target)
    # RNA bulge: protospacer is n-1 bases (one extra spacer base); remove the
    # extra spacer base so both aligned strings are n-1 bases.
    if rna_bulges >= 1 and n >= 2:
        start = pam_at - (n - 1)
        if start >= 0:
            window = seq[start:pam_at]
            best = _best_with_removed_base(spacer, window, max_mm)
            if best is not None:
                mm, reduced_spacer = best
                return (start, mm, 0, 1, reduced_spacer, window)
    return None


def _scan_one_strand(
    spacer: str,
    seq: str,
    pam: PAM,
    *,
    max_mm: int,
    dna_bulges: int,
    rna_bulges: int,
) -> list[tuple[int, int, str, int, int, int, str, str]]:
    """Scan ``seq`` (read 5'->3') for PAM-anchored hits to ``spacer``.

    Returns tuples ``(proto_start, proto_end, pam_seq, mm, dnab, rnab,
    aligned_spacer, aligned_target)`` in ``seq``-local coordinates.
    """
    pam_len = len(pam.pattern)
    hits: list[tuple[int, int, str, int, int, int, str, str]] = []
    for pam_at in range(len(spacer) - 1, len(seq) - pam_len + 1):
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

    Returns:
        All hits within budget, as plus-strand :class:`Hit` records.
    """
    seq = str(sequence).upper()
    sp = str(spacer).upper()
    n = len(seq)
    hits: list[Hit] = []
    for local in _scan_one_strand(
        sp, seq, pam, max_mm=mismatches, dna_bulges=dna_bulges, rna_bulges=rna_bulges
    ):
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
    for local in _scan_one_strand(
        sp, rc, pam, max_mm=mismatches, dna_bulges=dna_bulges, rna_bulges=rna_bulges
    ):
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
