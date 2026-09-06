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
        score_matrix: The weight source that actually produced ``score`` for *this*
            site, so a consumer can tell a published-CFD score from a fallback. It
            can differ from the report-level scorer matrix: the published CFD matrix
            is defined only for a 20-nt alignment, so a bulge-collapsed or off-length
            hit is scored by the length-relative approximation and records that here
            rather than being mislabeled as published CFD. ``None`` when unset.
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
    score_matrix: str | None = None
    #: The concrete PAM read at this site. A report can mix a canonical ``NGG`` with a
    #: low-stringency ``NAG`` — very different real risk — and a reader had no way to
    #: tell them apart. It is also what distinguishes two *overlapping* sites: with
    #: bulges allowed the same 20 bp of genome is reachable from two adjacent PAMs, and
    #: without the PAM those two rows look like one locus printed twice.
    pam_sequence: str | None = None

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
        dna_bulge_budget: Max DNA bulges allowed in the search.
        rna_bulge_budget: Max RNA bulges allowed in the search.
        cfd_threshold: The CFD score at or above which a site is *reported*.
        mit_threshold: The MIT score at or above which a site is *reported*.
        reference_build: The reference build searched.
        scorer: Name of the specificity scorer that produced the site scores.
        score_matrix: Identity of the weight source the scorer used, so a consumer
            can tell whether the scores are published-CFD or an approximation.
        subthreshold_score_sum: Sum of the best per-placement scores of in-budget
            off-target sites that were nominated but did **not** clear the reporting
            threshold, so :meth:`specificity_score` can aggregate over the full
            nominated set (including the sub-threshold tail) rather than only over
            reported sites. Defaults to ``0.0`` for a report built without a tail.
    """

    model_config = ConfigDict(frozen=True)

    spacer: str
    pam: str
    sites: tuple[OffTargetSite, ...] = ()
    mismatch_threshold: int = 4
    # The budget and the reporting thresholds decide what this report *contains*:
    # the same guide yields two sites at a 0.20 CFD cut-off and fifteen at 0.05, and
    # a bulge-free search misses a class of site entirely. `mismatch_threshold` was
    # already recorded for exactly this reason; its neighbours were not, leaving a
    # site count that cannot be compared against another report's.
    dna_bulge_budget: int = 1
    rna_bulge_budget: int = 1
    cfd_threshold: float = 0.20
    mit_threshold: float = 0.10
    #: Bases in the searched region(s), and how many of those were unambiguous A/C/G/T.
    #: A window holding an assembly gap or an IUPAC code cannot be scanned, so a search
    #: over a region that is mostly gap examines almost nothing while reporting the same
    #: "0 sites" as one over fully-resolved sequence.
    searched_bases: int = 0
    resolved_bases: int = 0
    #: For each safety source the caller **supplied**, how many of its entries fell in
    #: the searched region(s). An absent key means the source was not supplied at all;
    #: a key mapping to ``0`` means it was supplied and covered nothing here. Those are
    #: different statements and produce identical reports otherwise — an empty ancestry
    #: breakdown reads as "clean" either way.
    #:
    #: A mapping rather than a field per source, because the sources are a growing set
    #: (gnomAD, haplotype panels, patient VCFs, and whatever comes next) and one of them
    #: getting the check while the others did not is how the gap arose in the first
    #: place.
    sources_considered: dict[str, int] = {}
    #: Ancestries the caller asked to stratify by that no supplied source carries data
    #: for. They contribute nothing and are dropped silently, while provenance records
    #: them among the populations considered — so a report can assert an ancestry was
    #: examined when nothing for it exists. Empty when every request is backed, and
    #: empty when no source was supplied at all (a different case, warned elsewhere).
    unbacked_populations: tuple[str, ...] = ()
    reference_build: str = "hg38"
    scorer: str | None = None
    score_matrix: str | None = None
    subthreshold_score_sum: float = 0.0

    def search_description(self) -> str:
        """Return a one-line statement of the budgets and cut-offs used.

        Every number this report carries — the site count, the worst score, the
        specificity — is conditional on these five settings, and a reader comparing
        two reports cannot do so without them. Recording them on the model (so they
        survive serialization) is only half the job; this is the form a render can
        put next to the numbers.
        """
        # Deliberately ASCII: this string reaches the PDF leave-behind, whose WinAnsi
        # font has no glyph for the mathematical <= or >=, and would print "?3
        # mismatches" on the page a collaborator is handed.
        coverage = ""
        if self.searched_bases == 0 and self.sites == ():
            # No sequence at all — a truncated or header-only reference, or a scope that
            # resolved to nothing. Left unsaid this returns "0 sites, specificity 1.000",
            # the most reassuring report the system can produce, from a search that
            # examined nothing.
            coverage = (
                "; NO SEQUENCE WAS SEARCHED — the reference or region scope yielded no "
                "bases, so this is not a clean result, it is an empty one"
            )
        if self.searched_bases > 0:
            fraction = self.resolved_bases / self.searched_bases
            # Only when it materially narrows the search: a genome with a few scattered
            # ambiguity codes is not news, a region that is half gap is.
            if fraction < 0.99:
                coverage = (
                    f"; only {fraction:.0%} of the {self.searched_bases:,} requested bases "
                    "were searchable (the rest are assembly gaps, ambiguity codes, or "
                    "past a contig end)"
                )
        if self.unbacked_populations:
            coverage += (
                "; no supplied source carries data for "
                f"{', '.join(self.unbacked_populations)} — those ancestries were "
                "requested but not examined, and their absence from the breakdown "
                "means 'no data', not 'no risk'"
            )
        inert = sorted(name for name, n in self.sources_considered.items() if n == 0)
        if inert:
            coverage += (
                f"; supplied but contributing nothing in this region: {', '.join(inert)} "
                "— the scan is that much closer to reference-only here, and an empty "
                "ancestry breakdown means 'not measured', not 'clean'"
            )
        return (
            f"up to {self.mismatch_threshold} mismatches, "
            f"{self.dna_bulge_budget} DNA / {self.rna_bulge_budget} RNA bulges; "
            f"sites reported at CFD >= {self.cfd_threshold:g} "
            f"or MIT >= {self.mit_threshold:g}{coverage}"
        )

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

    def effective_matrix(self) -> str | None:
        """Return the weight source the *reported* sites were actually scored by.

        The report-level :attr:`score_matrix` records the scorer's nominal matrix
        (how it was configured). But a fixed published matrix falls back to the
        length-relative approximation per hit — a bulge-collapsed or off-length
        alignment cannot be scored off-register — and that effective identity is
        recorded on each :class:`OffTargetSite`. When every reported site fell back,
        the nominal label alone would claim published CFD for an all-approximation
        table. This reconciles the per-site truth: the shared matrix when the
        reported sites agree, both joined with ``" + "`` when they are mixed, and
        the nominal :attr:`score_matrix` when there are no sites to speak for it.
        """
        used = sorted({s.score_matrix for s in self.sites if s.score_matrix is not None})
        if not used:
            return self.score_matrix
        return " + ".join(used)

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

        The sum covers the **full nominated in-budget set**: the reported sites plus
        :attr:`subthreshold_score_sum`, the sub-threshold tail the reporting filter
        excludes from :attr:`sites`. Two guides with identical above-threshold hits
        but different sub-threshold tails therefore report different specificity,
        matching the CRISPOR/Hsu aggregate that sums over all candidate sites — not
        just the reporting-threshold survivors.
        """
        return 1.0 / (1.0 + sum(s.score for s in self.sites) + self.subthreshold_score_sum)

    def expected_burden(self) -> float:
        """Return the frequency-weighted expected off-target burden.

        Each site's score is weighted by the probability a genome actually carries
        it: a reference site is present in every genome (weight 1.0), a patient
        site is certain in that individual's genome (weight 1.0), and a population
        site is weighted by its carrying-population frequency. This separates a
        rare-variant off-target (down-weighted toward the MAF floor) from a
        universal one, which the frequency-blind :meth:`worst_score` and
        :meth:`specificity_score` cannot — a 0.1%-MAF hit and a reference hit of the
        same raw score contribute a thousandfold-different burden here.
        """
        total = 0.0
        for site in self.sites:
            if site.origin is SiteOrigin.REFERENCE or site.frequency is None:
                total += site.score
            else:
                total += site.score * site.frequency
        return total

    def ancestry_stratification(self) -> dict[str, float]:
        """Return the worst-case off-target score per ancestry.

        For each ancestry mentioned by any site, reports the maximum site score
        among sites that affect it. A site whose attribution to a specific ancestry
        is **not** available contributes to *every* ancestry, exactly as
        :meth:`expected_burden` still counts it: a reference site (present in every
        genome), a patient site (carried by this individual, so no ancestry
        frequency; ``frequency is None``), **and** a population/haplotype site with a
        known frequency but an empty per-ancestry breakdown (``ancestries`` empty —
        we know it is carried but not in which stratum, so worst-case it is all of
        them). A population site *with* a breakdown contributes only to the
        ancestries it carries a non-zero frequency in. Were an unattributed site
        instead dropped from every stratum, a dangerous off-target would be invisible
        to :meth:`worst_ancestry` and so to the ranking safety axis, letting a benign
        ancestry-tagged site mask it — understating the genome-wide worst case.
        Ancestries are emitted in sorted order so the returned mapping — and
        anything that serializes it — is byte-stable across runs (a bare ``set``
        iteration would vary with the process hash seed).
        """
        strata: dict[str, float] = {}
        ancestries: set[str] = set()
        for site in self.sites:
            ancestries.update(site.ancestries)
        for ancestry in sorted(ancestries):
            best = 0.0
            for site in self.sites:
                unattributed = (
                    site.origin is SiteOrigin.REFERENCE
                    or site.frequency is None
                    or not site.ancestries
                )
                if unattributed:
                    best = max(best, site.score)
                elif site.ancestries.get(ancestry, 0.0) > 0.0:
                    best = max(best, site.score)
            strata[ancestry] = best
        return strata

    def worst_ancestry(self) -> tuple[str, float] | None:
        """Return the ``(ancestry, score)`` with the highest worst-case score.

        Returns ``None`` when no site carries ancestry annotation. A tie on the
        worst-case score resolves to the alphabetically-first ancestry, so the
        result is deterministic (and the safety penalty it drives is byte-stable)
        rather than depending on hash-seed-varying iteration order.
        """
        strata = self.ancestry_stratification()
        if not strata:
            return None
        ancestry = max(sorted(strata), key=lambda a: strata[a])
        return ancestry, strata[ancestry]
