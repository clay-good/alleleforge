"""Optional cross-check of the native engine against Cas-OFFinder.

When the external `Cas-OFFinder <https://github.com/snugel/cas-offinder>`_ binary
is installed, the native AlleleForge reference search can be cross-checked
against it and **disagreements flagged** — a guard against bugs in either engine.
Cas-OFFinder is reference-only, so the comparison is scoped to reference-origin
sites; AlleleForge's population/haplotype sites have no Cas-OFFinder counterpart
by design.

The binary invocation is never exercised in CI (Cas-OFFinder is not a
dependency); :meth:`CasOffinderAdapter.disagreements` is pure and testable.
"""

from __future__ import annotations

import shutil

from alleleforge.types.offtarget import OffTargetReport, SiteOrigin
from alleleforge.types.sequence import Strand

#: A locus key for set comparison: ``(chrom, start, strand)``.
LocusKey = tuple[str, int, Strand]


class CasOffinderAdapter:
    """Thin adapter that cross-checks reference sites against Cas-OFFinder."""

    def __init__(self, binary: str = "cas-offinder") -> None:
        """Record the Cas-OFFinder binary name (looked up on ``PATH``)."""
        self.binary = binary

    def available(self) -> bool:
        """Return ``True`` if the Cas-OFFinder binary is on ``PATH``."""
        return shutil.which(self.binary) is not None

    @staticmethod
    def reference_loci(report: OffTargetReport) -> set[LocusKey]:
        """Return the reference-origin site loci from ``report``."""
        return {
            (s.locus.chrom, s.locus.start, s.locus.strand)
            for s in report.sites
            if s.origin is SiteOrigin.REFERENCE
        }

    def disagreements(
        self, report: OffTargetReport, external_loci: set[LocusKey]
    ) -> dict[str, set[LocusKey]]:
        """Return loci the two engines disagree on.

        Args:
            report: An AlleleForge off-target report.
            external_loci: Reference-site loci reported by Cas-OFFinder.

        Returns:
            ``{"only_alleleforge": ..., "only_cas_offinder": ...}`` — empty sets
            when the two agree on every reference locus.
        """
        ours = self.reference_loci(report)
        return {
            "only_alleleforge": ours - external_loci,
            "only_cas_offinder": external_loci - ours,
        }

    def run(self, *args: object, **kwargs: object) -> set[LocusKey]:  # pragma: no cover - external
        """Run Cas-OFFinder and return its reference loci (requires the binary).

        Raises:
            RuntimeError: If the binary is not installed.
        """
        if not self.available():
            raise RuntimeError(f"Cas-OFFinder binary {self.binary!r} is not on PATH")
        raise NotImplementedError("Cas-OFFinder invocation is wired up in a later phase")
