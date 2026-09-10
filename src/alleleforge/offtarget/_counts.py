"""How a supplied variant source fared during a scan.

Every optional safety source — a gnomAD sites file, a phased haplotype panel, a patient
VCF — is consumed by an enumerator that skips a record whose asserted REF is not the base
this genome has. Skipping is right: applying an ALT to a base the genome does not have
builds a haplotype nobody carries. Skipping *silently* is what made a whole file for the
wrong assembly indistinguishable from a file that simply had nothing to add, because the
counter the report reads (`sources_considered`) counts records **found in the region**,
which a wrong-build file satisfies completely.

Lives in its own module so the haplotype kernel wrapper and the population enumerator can
both fill one, without either importing the other.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SourceCounts"]


@dataclass
class SourceCounts:
    """What a source's records did, for the report to state.

    In the shape :class:`~alleleforge.variant.vcf.VcfIngestCounts` already uses: filled as
    the stream is consumed, so it is complete by the time the report is built and costs
    nothing when no caller passes one.
    """

    #: Records whose asserted REF does not match this reference at that position.
    build_mismatch: int = 0
