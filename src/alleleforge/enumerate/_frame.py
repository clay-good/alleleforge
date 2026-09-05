"""Coordinate mapping from an edited enumeration frame back onto the reference.

Every enumerator works on the sequence the **target genome actually carries** —
the reference window with the carried allele substituted in — so that a PAM the
allele destroys is not emitted and one it creates is found. When the carried
allele is not the same length as the reference span it replaces, that window's
coordinates drift from the reference downstream of the edit, and every emitted
placement has to be mapped back or it names a locus the reagent does not occupy.

:class:`EditFrame` owns that mapping. It reports the **reference footprint** a
span's bases derive from: exact for a span that does not cross the edit (the
common case — a 20 nt protospacer beside a small edit), wider for one spanning a
deletion, narrower for one spanning an insertion. A span lying wholly inside
carried bases the reference does not contain has no footprint at all, and the
frame says so rather than inventing one.
"""

from __future__ import annotations

from dataclasses import dataclass

from alleleforge.types.sequence import GenomicInterval, Strand


@dataclass(frozen=True)
class EditFrame:
    """Maps enumeration-frame coordinates onto reference loci.

    Attributes:
        chrom: Contig of the fetched window.
        offset: Genomic start of the fetched reference window.
        edit_plus: Plus-frame index where the edit span begins.
        start_len: Length of the carried (start) allele.
        ref_len: Length of the reference span that allele replaces.
        span: Length of the start-genome string this frame indexes.
        reverse: ``True`` when the frame is the reverse complement of the plus frame.
    """

    chrom: str
    offset: int
    edit_plus: int
    start_len: int
    ref_len: int
    span: int
    reverse: bool = False

    @classmethod
    def identity(cls, *, chrom: str, offset: int, span: int) -> EditFrame:
        """Return a frame for a window carrying no length-changing edit."""
        return cls(chrom=chrom, offset=offset, edit_plus=0, start_len=0, ref_len=0, span=span)

    def _reference_start(self, index: int) -> int:
        """Return the reference coordinate a span *starting* at ``index`` begins on.

        A span boundary at the edit is ambiguous, and the two directions want
        opposite answers. When the carried allele is empty — the target genome has
        a pure deletion — index ``edit_plus`` is simultaneously "just before the
        removed reference bases" and "just after" them. A span **starting** there
        begins *after* them, so the downstream branch is tested first; a span
        **ending** there stops *before* them (see :meth:`_reference_end`). Resolving
        both with one map made a span starting at that point claim the removed
        bases as part of its footprint. The off-target module's
        ``_alt_coordinate_lift`` splits its lift into ``lo``/``hi`` maps for exactly
        this reason.
        """
        if index >= self.edit_plus + self.start_len:
            return self.offset + index - self.start_len + self.ref_len
        if index <= self.edit_plus:
            return self.offset + index
        # Inside the carried allele: walk the reference span it replaces, then
        # stay pinned at its 3' boundary once the allele outruns it.
        return self.offset + self.edit_plus + min(index - self.edit_plus, self.ref_len)

    def _reference_end(self, index: int) -> int:
        """Return the reference coordinate a span *ending* at ``index`` stops on."""
        if index <= self.edit_plus:
            return self.offset + index
        if index >= self.edit_plus + self.start_len:
            return self.offset + index - self.start_len + self.ref_len
        return self.offset + self.edit_plus + min(index - self.edit_plus, self.ref_len)

    def interval(self, lo: int, hi: int, strand: Strand) -> GenomicInterval | None:
        """Return the reference footprint of frame span ``[lo, hi)``.

        Returns ``None`` when the footprint is zero-width — the span lies wholly
        inside carried bases the reference does not contain, so it has no
        reference locus to report (an unplaced reagent, not an invalid one).
        """
        lo_plus, hi_plus = (self.span - hi, self.span - lo) if self.reverse else (lo, hi)
        start, end = self._reference_start(lo_plus), self._reference_end(hi_plus)
        if end <= start:
            return None
        out_strand = strand.opposite() if self.reverse else strand
        return GenomicInterval(chrom=self.chrom, start=start, end=end, strand=out_strand)

    def coord(self, index: int) -> int:
        """Return the reference coordinate of the base at frame position ``index``.

        A position names a base, not a boundary, so it uses the span-start map.
        """
        return self._reference_start(self.span - 1 - index if self.reverse else index)
