"""Cross-build liftover and hg38-ambiguous-region flagging.

Two responsibilities:

* :class:`Liftover` projects intervals between assemblies via UCSC chain files
  (wrapping :mod:`pyliftover`). Chain files are supplied explicitly — AlleleForge
  never auto-downloads one.
* :func:`flag_ambiguous_regions` detects segmentally-duplicated, centromeric, or
  otherwise hg38-difficult loci and **recommends T2T-CHM13** for them. The
  recommendation is wired into the Phase 1 result types via
  :meth:`ReferenceRecommendation.apply_to`, which annotates a
  :class:`~alleleforge.types.candidate.DesignCandidate` with the appropriate
  flags so a reference-biased design is never silently trusted.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

#: The reference AlleleForge recommends for hg38-ambiguous loci.
DEFAULT_RECOMMENDED_BUILD = "T2T-CHM13v2"

#: A raw chain-file converter: ``(chrom, pos) -> [(chrom, pos, strand, ...), ...]``.
#: Matches :meth:`pyliftover.LiftOver.convert_coordinate` so it can be injected.
ChainConverter = Callable[[str, int], list[tuple[str, int, str, int]]]


class RegionFlagKind(StrEnum):
    """Why a locus is flagged as hg38-ambiguous."""

    SEGDUP = "segdup"
    CENTROMERIC = "centromeric"
    HG38_DIFFICULT = "hg38-difficult"


class AmbiguousRegion(BaseModel):
    """A reference region known to be unreliable on hg38."""

    model_config = ConfigDict(frozen=True)

    interval: GenomicInterval
    kind: RegionFlagKind
    note: str | None = None


class ReferenceRecommendation(BaseModel):
    """The outcome of flagging an interval against ambiguous-region tables.

    Attributes:
        query: The interval that was checked.
        source_build: The build the query is expressed in.
        recommended_build: The build to switch to, or ``None`` if no flag fired.
        regions: The ambiguous regions the query overlaps.
    """

    model_config = ConfigDict(frozen=True)

    query: GenomicInterval
    source_build: str
    recommended_build: str | None
    regions: tuple[AmbiguousRegion, ...] = ()

    @property
    def recommended(self) -> bool:
        """Return ``True`` if a different reference build is recommended."""
        return self.recommended_build is not None and len(self.regions) > 0

    @property
    def reason(self) -> str:
        """Return a human-readable rationale for the recommendation."""
        if not self.recommended:
            return f"no hg38-ambiguous region overlaps {self.query.chrom}:{self.query.start}"
        kinds = ", ".join(sorted({r.kind.value for r in self.regions}))
        return (
            f"{self.query.chrom}:{self.query.start}-{self.query.end} overlaps {kinds}; "
            f"recommend {self.recommended_build}"
        )

    def candidate_flags(self) -> tuple[str, ...]:
        """Return flag strings suitable for :attr:`DesignCandidate.flags`."""
        flags = [f"ambiguous-region:{r.kind.value}" for r in self.regions]
        if self.recommended:
            flags.append(f"recommend-reference:{self.recommended_build}")
        return tuple(dict.fromkeys(flags))

    def apply_to(self, candidate: DesignCandidate) -> DesignCandidate:
        """Return ``candidate`` with this recommendation's flags merged in.

        This is the wiring point into the Phase 1 result types: ambiguous-region
        and reference-recommendation flags ride along on the design candidate so
        they surface in the ranked menu and the report.
        """
        merged = tuple(dict.fromkeys((*candidate.flags, *self.candidate_flags())))
        return candidate.model_copy(update={"flags": merged})


def _region(chrom: str, start: int, end: int, kind: RegionFlagKind, note: str) -> AmbiguousRegion:
    """Build an :class:`AmbiguousRegion` on the plus strand (0-based half-open)."""
    return AmbiguousRegion(
        interval=GenomicInterval(chrom=chrom, start=start, end=end, strand=Strand.PLUS),
        kind=kind,
        note=note,
    )


#: A small curated table of well-known hg38-difficult loci. Not exhaustive; the
#: Phase 3 data registry can supply a fuller segdup/centromere track that callers
#: pass via the ``regions`` argument of :func:`flag_ambiguous_regions`.
HG38_DIFFICULT_REGIONS: tuple[AmbiguousRegion, ...] = (
    _region("chr1", 121_700_000, 125_100_000, RegionFlagKind.CENTROMERIC, "chr1 centromere"),
    _region("chr16", 34_600_000, 46_500_000, RegionFlagKind.CENTROMERIC, "chr16 pericentromere"),
    _region("chr1", 144_000_000, 149_900_000, RegionFlagKind.SEGDUP, "1q21 segdup cluster"),
    _region(
        "chr22", 10_700_000, 12_000_000, RegionFlagKind.HG38_DIFFICULT, "chr22 acrocentric p-arm"
    ),
)


def flag_ambiguous_regions(
    interval: GenomicInterval,
    *,
    source_build: str = "hg38",
    regions: tuple[AmbiguousRegion, ...] | None = None,
    recommended_build: str = DEFAULT_RECOMMENDED_BUILD,
) -> ReferenceRecommendation:
    """Flag ``interval`` against ambiguous-region tables and recommend T2T.

    Args:
        interval: The locus to check (0-based half-open).
        source_build: The build ``interval`` is expressed in. Recommendation
            fires only for ``"hg38"`` (the default reference).
        regions: An explicit region table; defaults to
            :data:`HG38_DIFFICULT_REGIONS` when ``source_build`` is hg38.
        recommended_build: The build to recommend when a flag fires.

    Returns:
        A :class:`ReferenceRecommendation`; ``recommended`` is ``True`` only when
        the query overlaps a flagged region on hg38.

    Raises:
        ValueError: If ``interval`` is not 0-based half-open.
    """
    if interval.coordinate_system is not CoordinateSystem.ZERO_BASED_HALF_OPEN:
        raise ValueError("flag_ambiguous_regions requires a 0-based half-open interval")
    table = (
        regions
        if regions is not None
        else (HG38_DIFFICULT_REGIONS if source_build == "hg38" else ())
    )
    hits = tuple(r for r in table if r.interval.overlaps(interval))
    rec_build = recommended_build if hits and source_build == "hg38" else None
    return ReferenceRecommendation(
        query=interval,
        source_build=source_build,
        recommended_build=rec_build,
        regions=hits,
    )


class Liftover:
    """Project intervals between assemblies via a UCSC chain converter."""

    def __init__(
        self,
        convert: ChainConverter,
        *,
        source_build: str,
        target_build: str,
    ) -> None:
        """Wrap a raw chain converter.

        Args:
            convert: ``(chrom, pos) -> list`` per
                :meth:`pyliftover.LiftOver.convert_coordinate`.
            source_build: The build the input coordinates are in.
            target_build: The build the output coordinates are in.
        """
        self._convert = convert
        self.source_build = source_build
        self.target_build = target_build

    @classmethod
    def from_chain_file(cls, path: str | Path, *, source_build: str, target_build: str) -> Liftover:
        """Build a liftover from a local UCSC chain file (never downloaded)."""
        from pyliftover import LiftOver

        lo = LiftOver(str(path))
        return cls(lo.convert_coordinate, source_build=source_build, target_build=target_build)

    def convert_position(self, chrom: str, pos: int) -> tuple[str, int, Strand] | None:
        """Lift a single 0-based position, or ``None`` if it does not map."""
        result = self._convert(chrom, pos)
        if not result:
            return None
        new_chrom, new_pos, strand, *_ = result[0]
        return new_chrom, new_pos, Strand.PLUS if strand == "+" else Strand.MINUS

    def lift_interval(self, interval: GenomicInterval) -> GenomicInterval | None:
        """Lift a 0-based half-open interval to the target build.

        Lifts the first and last bases independently and rebuilds the span.
        Returns ``None`` if either endpoint fails to map or the endpoints land
        on different contigs (a broken/split region).

        Raises:
            ValueError: If ``interval`` is empty or not 0-based half-open.
        """
        if interval.coordinate_system is not CoordinateSystem.ZERO_BASED_HALF_OPEN:
            raise ValueError("lift_interval requires a 0-based half-open interval")
        if interval.length == 0:
            raise ValueError("cannot lift an empty interval")
        start = self.convert_position(interval.chrom, interval.start)
        last = self.convert_position(interval.chrom, interval.end - 1)
        if start is None or last is None or start[0] != last[0]:
            return None
        lo_pos, hi_pos = sorted((start[1], last[1]))
        strand = interval.strand if start[2] is Strand.PLUS else interval.strand.opposite()
        return GenomicInterval(
            chrom=start[0],
            start=lo_pos,
            end=hi_pos + 1,
            strand=strand,
            coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
        )
