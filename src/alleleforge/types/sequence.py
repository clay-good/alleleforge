"""Strandedness, coordinate systems, and ambiguity-aware DNA sequences.

These are the lowest-level value objects in AlleleForge. Getting strandedness,
the 0-based half-open coordinate convention, and IUPAC ambiguity handling right
*here, once* keeps every higher layer honest.

All internal coordinates are **0-based, half-open** ("BED-style"). Convert to
1-based only at I/O boundaries via :meth:`GenomicInterval.to_one_based`, and
never internally.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

#: IUPAC nucleotide alphabet: the four bases plus ambiguity and gap codes.
IUPAC_ALPHABET = frozenset("ACGTRYSWKMBDHVN")

#: Ambiguity-aware complement map. Reverse-complement must respect IUPAC codes
#: (R<->Y, W<->W, N<->N) so degenerate PAMs and primers round-trip correctly.
_COMPLEMENT = {
    "A": "T",
    "T": "A",
    "C": "G",
    "G": "C",
    "R": "Y",
    "Y": "R",
    "S": "S",
    "W": "W",
    "K": "M",
    "M": "K",
    "B": "V",
    "V": "B",
    "D": "H",
    "H": "D",
    "N": "N",
}

#: For each IUPAC code, the concrete bases it can match. Drives PAM matching.
IUPAC_EXPAND = {
    "A": frozenset("A"),
    "C": frozenset("C"),
    "G": frozenset("G"),
    "T": frozenset("T"),
    "R": frozenset("AG"),
    "Y": frozenset("CT"),
    "S": frozenset("GC"),
    "W": frozenset("AT"),
    "K": frozenset("GT"),
    "M": frozenset("AC"),
    "B": frozenset("CGT"),
    "D": frozenset("AGT"),
    "H": frozenset("ACT"),
    "V": frozenset("ACG"),
    "N": frozenset("ACGT"),
}


class Strand(StrEnum):
    """Genomic strand. Always explicit; AlleleForge has no "default strand"."""

    PLUS = "+"
    MINUS = "-"

    def opposite(self) -> Strand:
        """Return the other strand."""
        return Strand.MINUS if self is Strand.PLUS else Strand.PLUS


class CoordinateSystem(StrEnum):
    """Coordinate convention. Internal everything is 0-based half-open."""

    ZERO_BASED_HALF_OPEN = "0-based-half-open"
    ONE_BASED = "1-based-inclusive"


class DNASequence(BaseModel):
    """An IUPAC-validated DNA sequence with ambiguity-aware operations.

    Accepts a positional string (``DNASequence("ACGT")``) or the keyword form
    used by deserialization (``DNASequence(sequence="ACGT")``). The sequence is
    upper-cased and validated against the IUPAC alphabet on construction.
    """

    model_config = ConfigDict(frozen=True)

    sequence: str

    def __init__(self, sequence: str | None = None, **data: Any) -> None:
        """Allow a positional sequence string in addition to the keyword form."""
        if sequence is not None:
            data["sequence"] = sequence
        super().__init__(**data)

    @field_validator("sequence")
    @classmethod
    def _validate_alphabet(cls, value: str) -> str:
        """Upper-case and reject any non-IUPAC character."""
        upper = value.upper()
        bad = set(upper) - IUPAC_ALPHABET
        if bad:
            raise ValueError(f"non-IUPAC characters in sequence: {sorted(bad)}")
        return upper

    def __len__(self) -> int:
        """Return the number of bases."""
        return len(self.sequence)

    def __str__(self) -> str:
        """Return the bare base string (so ``print`` shows the sequence)."""
        return self.sequence

    def __getitem__(self, key: int | slice) -> DNASequence:
        """Slice or index, returning a new :class:`DNASequence`.

        Integer indexing returns a single-base sequence rather than a raw
        character, keeping the type uniform across the codebase.
        """
        if isinstance(key, slice):
            return DNASequence(self.sequence[key])
        return DNASequence(self.sequence[key])

    @property
    def is_ambiguous(self) -> bool:
        """Return ``True`` if any base is an IUPAC ambiguity code."""
        return any(base not in "ACGT" for base in self.sequence)

    def complement(self) -> DNASequence:
        """Return the ambiguity-aware base complement (same 5'->3' order)."""
        return DNASequence("".join(_COMPLEMENT[base] for base in self.sequence))

    def reverse_complement(self) -> DNASequence:
        """Return the ambiguity-aware reverse complement.

        This is an involution: ``s.reverse_complement().reverse_complement()``
        equals ``s`` for any valid sequence.
        """
        return DNASequence("".join(_COMPLEMENT[base] for base in reversed(self.sequence)))

    def gc_content(self) -> float:
        """Return the fraction of unambiguous G/C bases, ``0.0`` for empty."""
        if not self.sequence:
            return 0.0
        gc = sum(base in "GCS" for base in self.sequence)
        return gc / len(self.sequence)


def canonical_contig(chrom: str) -> str:
    """Return a naming-style-independent key for a contig name.

    Strips a UCSC ``chr`` prefix and unifies the mitochondrion's two spellings
    (``chrM``/``M`` and Ensembl ``MT``), so ``chr17`` and ``17`` — or ``chrM`` and
    ``MT`` — compare equal. Any other name is returned upper-cased and unprefixed.
    """
    base = chrom[3:] if chrom.lower().startswith("chr") else chrom
    return "MT" if base.upper() in {"M", "MT"} else base.upper()


class GenomicInterval(BaseModel):
    """A strand-aware genomic interval, 0-based half-open by default.

    Attributes:
        chrom: Contig / chromosome name (e.g. ``"chr2"``).
        start: Inclusive start coordinate.
        end: Exclusive end coordinate (``start <= end``).
        strand: The strand the interval is reported on.
        coordinate_system: The coordinate convention of ``start``/``end``.
    """

    model_config = ConfigDict(frozen=True)

    chrom: str
    start: int
    end: int
    strand: Strand
    coordinate_system: CoordinateSystem = CoordinateSystem.ZERO_BASED_HALF_OPEN

    @model_validator(mode="after")
    def _check_bounds(self) -> GenomicInterval:
        """Validate non-negative, ordered coordinates."""
        if self.start < 0:
            raise ValueError(f"start {self.start} is negative")
        if self.end < self.start:
            raise ValueError(f"end {self.end} precedes start {self.start}")
        return self

    def __len__(self) -> int:
        """Return the interval length in bases (coordinate-system aware)."""
        return self.length

    def __str__(self) -> str:
        """Return a compact ``chrom:start-end(strand)`` representation."""
        return f"{self.chrom}:{self.start}-{self.end}({self.strand.value})"

    @property
    def length(self) -> int:
        """Return the interval length in bases.

        Half-open ``[start, end)`` spans ``end - start`` bases; 1-based
        inclusive ``[start, end]`` spans one more.
        """
        if self.coordinate_system is CoordinateSystem.ONE_BASED:
            return self.end - self.start + 1
        return self.end - self.start

    def to_one_based(self) -> GenomicInterval:
        """Return an equivalent 1-based inclusive interval (I/O boundary only).

        0-based half-open ``[start, end)`` maps to 1-based inclusive
        ``[start + 1, end]``. Never use the result for internal arithmetic.

        Raises:
            ValueError: If the interval is already 1-based.
        """
        if self.coordinate_system is CoordinateSystem.ONE_BASED:
            raise ValueError("interval is already 1-based")
        return GenomicInterval(
            chrom=self.chrom,
            start=self.start + 1,
            end=self.end,
            strand=self.strand,
            coordinate_system=CoordinateSystem.ONE_BASED,
        )

    def overlaps(self, other: GenomicInterval) -> bool:
        """Return ``True`` if the two intervals share any base on the same contig.

        Contigs are compared by :func:`canonical_contig`, so a ``chr1`` interval
        and a ``1`` interval on the same chromosome are recognized as the same
        contig rather than silently treated as disjoint. Both intervals must use
        the same coordinate system for the result to be meaningful.
        """
        if canonical_contig(self.chrom) != canonical_contig(other.chrom):
            return False
        return self.start < other.end and other.start < self.end
