"""Off-target site and report models with ancestry stratification.

The off-target report is AlleleForge's safety surface. Every nominated site
records not just its locus and score but *where it came from*: the reference, a
population variant (which allele, which populations, at what frequency), or a
patient's VCF. Reports are ancestry-stratified by default so a design that is
safe on average but dangerous in one population is never hidden behind a global
number.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from alleleforge.types.sequence import GenomicInterval


class ScoreMethod(StrEnum):
    """The specificity score used to rank an off-target site."""

    CFD = "cfd"
    MIT = "mit"
    CFD_CAS12A = "cfd_cas12a"


class SiteOrigin(StrEnum):
    """Where a candidate off-target site originates."""

    REFERENCE = "reference"
    POPULATION = "population"
    PATIENT = "patient"


class OffTargetSite(BaseModel):
    """A single nominated off-target locus with provenance and scoring.

    Attributes:
        locus: The genomic placement of the off-target protospacer.
        mismatches: Number of base mismatches to the on-target spacer.
        dna_bulges: Number of DNA bulges in the alignment.
        rna_bulges: Number of RNA bulges in the alignment.
        score: The specificity score under ``score_method``.
        score_method: Which score ``score`` reports.
        mit_score: The MIT/Hsu specificity score for this site when defined (an
            ungapped, 20-nt alignment), else ``None``. Recorded alongside
            ``score`` so a site nominated by the engine's MIT reporting threshold
            is auditable even when the primary ``score`` is CFD — the two
            thresholds are an OR, and the MIT score that retained a low-CFD site
            would otherwise be invisible.
        origin: Reference, population, or patient origin.
        causal_allele: For population/patient sites, the allele that creates or
            modifies the site (``chrom:pos:ref>alt`` form), else ``None``.
        populations: Populations carrying the causal allele.
        frequency: Allele frequency of the causal allele (max over populations).
        ancestries: Per-ancestry frequency annotation for this site.
    """

    model_config = ConfigDict(frozen=True)

    locus: GenomicInterval
    mismatches: int
    dna_bulges: int = 0
    rna_bulges: int = 0
    score: float
    score_method: ScoreMethod
    mit_score: float | None = None
    origin: SiteOrigin = SiteOrigin.REFERENCE
    causal_allele: str | None = None
    populations: tuple[str, ...] = ()
    frequency: float | None = None
    ancestries: dict[str, float] = {}

    @model_validator(mode="after")
    def _check(self) -> OffTargetSite:
        """Validate counts, score range, and population-origin consistency."""
        if self.mismatches < 0 or self.dna_bulges < 0 or self.rna_bulges < 0:
            raise ValueError("mismatch/bulge counts must be non-negative")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score {self.score} not in [0, 1]")
        if self.mit_score is not None and not 0.0 <= self.mit_score <= 1.0:
            raise ValueError(f"mit_score {self.mit_score} not in [0, 1]")
        if self.frequency is not None and not 0.0 <= self.frequency <= 1.0:
            raise ValueError(f"frequency {self.frequency} not in [0, 1]")
        if self.origin is not SiteOrigin.REFERENCE and self.causal_allele is None:
            raise ValueError(f"{self.origin.value} site must record a causal_allele")
        return self


class OffTargetReport(BaseModel):
    """An aggregated, ancestry-stratified off-target nomination report.

    Attributes:
        spacer: The on-target spacer the search was run for (5'->3').
        pam: The PAM pattern searched.
        sites: All nominated sites passing the reporting thresholds.
        mismatch_threshold: Max mismatches allowed in the search.
        reference_build: The reference build searched.
    """

    model_config = ConfigDict(frozen=True)

    spacer: str
    pam: str
    sites: tuple[OffTargetSite, ...] = ()
    mismatch_threshold: int = 4
    reference_build: str = "hg38"

    @property
    def n_sites(self) -> int:
        """Return the number of nominated sites."""
        return len(self.sites)

    @property
    def population_sites(self) -> tuple[OffTargetSite, ...]:
        """Return only the sites arising from population or patient variation."""
        return tuple(s for s in self.sites if s.origin is not SiteOrigin.REFERENCE)

    def worst_score(self) -> float:
        """Return the highest off-target score across all sites (0 if none)."""
        return max((s.score for s in self.sites), default=0.0)

    def specificity_score(self) -> float:
        """Return the aggregate genome-wide specificity score in ``(0, 1]``.

        This is the CFD-scale analog of the Hsu 2013 / MIT aggregate guide
        specificity score (``100 / (100 + Σ off-target scores)``): on the
        normalized ``[0, 1]`` per-site scale it is ``1 / (1 + Σ sᵢ)``. It is the
        single-number summary every design tool reports — **1.0** for a guide with
        no nominated off-targets, decreasing monotonically as the total off-target
        burden grows. Unlike :meth:`worst_score` (the single worst site), it
        distinguishes two guides with the same worst-case off-target but a
        different *number* of off-targets — the one with fewer is more specific.
        """
        return 1.0 / (1.0 + sum(s.score for s in self.sites))

    def ancestry_stratification(self) -> dict[str, float]:
        """Return the worst-case off-target score per ancestry.

        For each ancestry mentioned by any site, reports the maximum site score
        among sites carrying a non-zero frequency in that ancestry. Reference
        sites (present in every genome) contribute to every ancestry.
        """
        strata: dict[str, float] = {}
        ancestries: set[str] = set()
        for site in self.sites:
            ancestries.update(site.ancestries)
        for ancestry in ancestries:
            best = 0.0
            for site in self.sites:
                if site.origin is SiteOrigin.REFERENCE:
                    best = max(best, site.score)
                elif site.ancestries.get(ancestry, 0.0) > 0.0:
                    best = max(best, site.score)
            strata[ancestry] = best
        return strata

    def worst_ancestry(self) -> tuple[str, float] | None:
        """Return the ``(ancestry, score)`` with the highest worst-case score.

        Returns ``None`` when no site carries ancestry annotation.
        """
        strata = self.ancestry_stratification()
        if not strata:
            return None
        ancestry = max(strata, key=lambda a: strata[a])
        return ancestry, strata[ancestry]
