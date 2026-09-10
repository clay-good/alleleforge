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

from alleleforge.types.guide import GUIDE_SPACER_RANGE
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


#: Decimal places a *frequency* is published to — an allele frequency of 0.0001 is a real
#: carrier rate and four places would round it away.
FREQUENCY_PRECISION = 6

#: Decimal places every surface reports an aggregate score to. The scores are ratios in
#: `[0, 1]` computed from sums of per-site scores, so their last digits are float noise —
#: the reproducibility audit rounds for the same reason ("a last-ULP difference across
#: platforms is not a spurious failure"). It lives here, once, because the CLI rounded and
#: the web did not: the same guide reported `specificity 0.21` from one shell and
#: `0.21004997798215197` from the other, and a pipeline thresholding at 0.21 got two
#: answers to one question.
AGGREGATE_PRECISION = 4

#: Ancestry burdens carry allele frequencies, which are small: 4 places would round a
#: 0.0001 carrier frequency to nothing.
ANCESTRY_BURDEN_PRECISION = 6


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
    #: The PAM pattern the scan actually anchored on. `search()` broadens SpCas9's
    #: `NGG` to `NRG` so a low-stringency `NAG` off-target — which SpCas9 does cut, at
    #: reduced efficiency — is found rather than missed. That is deliberate and
    #: specified, and nothing said it: a report headed `PAM NGG` listed sites reading
    #: `pam=CAG`, with no surface reconciling the two. `None` when the scan used the
    #: requested pattern unchanged, so the note marks a real difference.
    scanned_pam: str | None = None
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
    #: Records from a supplied source that assert a reference base this genome does not
    #: have, per source. The enumerator has always skipped them — `return []  # the
    #: variant's ref does not match this build; skip safely` — which is right, and was
    #: silent. A whole gnomAD file for the wrong build is *records in the region* as far
    #: as `sources_considered` can tell, so the "supplied but contributing nothing" note
    #: could not fire, and the run read exactly like one whose file was fine and had
    #: nothing to add. The patient-VCF path refuses the same mistake loudly at load; this
    #: is the same statement for a source that is skipped per record instead.
    source_build_mismatch: dict[str, int] = {}
    #: Ancestries the caller asked to stratify by that no supplied source carries data
    #: for. They contribute nothing and are dropped silently, while provenance records
    #: them among the populations considered — so a report can assert an ancestry was
    #: examined when nothing for it exists. Empty when every request is backed. Covers
    #: the no-source case too: the CLI warns about that one, but only to the terminal,
    #: so the durable artifact said nothing and a library caller was told nothing.
    unbacked_populations: tuple[str, ...] = ()
    #: Every ancestry label the supplied sources actually carry. Telling a caller their
    #: request went unexamined without naming the alternatives is an unactionable
    #: warning: the three documented vocabularies (gnomAD `afr`, 1000 Genomes `AFR`,
    #: HGDP `africa`) look interchangeable on the page and are not, and the report has
    #: this set in hand because it computed it to decide `unbacked_populations`. Empty
    #: when no ancestry source was supplied at all, which is a different statement and
    #: gets a different sentence.
    available_populations: tuple[str, ...] = ()
    #: Minimum population allele frequency a variant had to reach to be considered,
    #: or ``None`` when no ancestry source was supplied and the cut-off never applied.
    #: It decides which population alleles enter the scan at all, so it moves the site
    #: count and the specificity exactly the way the reporting cut-offs do -- a 2%
    #: PAM-creating variant is a site at ``maf=0.001`` and nothing at ``maf=0.05``,
    #: turning specificity 0.500 into a clean 1.000. The description said neither the
    #: number nor that a cut-off was responsible.
    maf_threshold: float | None = None
    #: 1-based spacer positions holding a non-ACGT base. Such a position cannot be
    #: scored — the CFD matrix has no entry for it — so the aligner counts it as a
    #: mismatch and the site's score falls toward 0, the *optimistic* direction on a
    #: safety axis, since the real base is unknown and may match perfectly.
    ambiguous_spacer_positions: tuple[int, ...] = ()
    reference_build: str = "hg38"
    scorer: str | None = None
    score_matrix: str | None = None
    subthreshold_score_sum: float = 0.0
    #: How many nominated placements that tail covers. The mass alone cannot be read:
    #: `0.19` is one near-miss or twenty faint ones, and those are different guides.
    subthreshold_placements: int = 0

    #: How many nominated placements the on-target exclusion removed. Every other route
    #: to "0 sites, specificity 1.000" on this report explains itself — an unsearchable
    #: scope, a sub-threshold tail, a source contributing nothing — and this one did not.
    #: An `--on-target` interval wider than the protospacer (a gene span, an over-generous
    #: liftover) excludes more than the guide's own site, and the result is indistinguishable
    #: from a guide that has no off-targets at all.
    on_target_excluded_placements: int = 0

    def search_description(self) -> str:
        """Return a one-line statement of the extent searched, the budgets and cut-offs.

        Every number this report carries — the site count, the worst score, the
        specificity — is conditional on these settings, and a reader comparing
        two reports cannot do so without them. Recording them on the model (so they
        survive serialization) is only half the job; this is the form a render can
        put next to the numbers.

        ``searched_bases`` leads, unconditionally. Scoping to a gene panel is the
        ordinary way a run is made practical — the ``--region`` help says so — and the
        scope is the setting that moves the numbers most: over a two-contig reference,
        restricting to one gave 1 site at specificity 0.468 where the whole reference
        gave 2 at 0.305. Both descriptions were identical, because the extent was
        mentioned only when the *resolved* fraction was degraded, and both were fully
        resolved. A reader comparing a panel scan against a genome-wide one saw two
        different specificities under the same provenance string, with the smaller
        search — the one that finds fewer off-targets — reading as the safer guide.
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
        low, high = GUIDE_SPACER_RANGE
        if self.spacer and not low <= len(self.spacer) <= high:
            coverage += (
                f"; the query is {len(self.spacer)} nt, outside the {low}-{high} nt range "
                "a guide has, so this is a sequence search and not a guide's off-target "
                "profile — a short query matches almost everywhere and its specificity is "
                "arithmetic, not biology"
            )
        if self.ambiguous_spacer_positions:
            listed = ", ".join(str(p) for p in self.ambiguous_spacer_positions)
            coverage += (
                f"; the spacer is ambiguous at position(s) {listed}, which cannot be "
                "scored — those positions count as mismatches, pushing scores DOWN, so "
                "a low score here is not evidence of safety"
            )
        if self.on_target_excluded_placements:
            coverage += (
                f"; {self.on_target_excluded_placements} nominated placement(s) were "
                "excluded as the guide's own locus, so the count and specificity above "
                "are over what remained — an on-target interval wider than the "
                "protospacer excludes more than the intended site"
            )
        if self.subthreshold_score_sum > 0.0:
            # `specificity_score` aggregates over every nominated site, not only the
            # reported ones, so a guide does not become clean because the caller asked
            # to see fewer of its off-targets. Correct, and unreadable without this:
            # summing the printed rows gives a different number, and with the cut-offs
            # raised past every hit the report reads "0 site(s), worst score 0.000,
            # specificity 0.130" with nothing on the page explaining the third figure.
            coverage += (
                f"; a sub-threshold tail of {self.subthreshold_placements} further "
                "in-budget placement(s) scored below the reporting cut-off and is "
                "therefore not among the nominated sites, contributing "
                f"{self.subthreshold_score_sum:.3f} to the specificity denominator - so "
                "the specificity is over every nominated site, not only the reported "
                "ones, and raising the cut-off cannot improve it"
            )
        if self.scanned_pam and self.scanned_pam != self.pam:
            coverage += (
                f"; the PAM was broadened from {self.pam} to {self.scanned_pam} for the "
                "scan, so low-stringency sites (e.g. NAG for SpCas9) are nominated too: "
                "they are cut less efficiently, and each site records the PAM it was "
                "actually found with"
            )
        if self.unbacked_populations:
            coverage += (
                "; no supplied source carries data for "
                f"{', '.join(self.unbacked_populations)} — those ancestries were "
                "requested but not examined, and their absence from the breakdown "
                "means 'no data', not 'no risk'"
            )
            # What to do about it. The labels are the source's own and are NOT
            # case-folded onto the request: gnomAD's `afr` and 1000 Genomes' `AFR`
            # are different groupings, so answering a question about one with data
            # about the other would be a silent substitution. Naming them lets the
            # caller choose; matching them would hide the choice.
            if self.available_populations:
                coverage += (
                    f"; the supplied source(s) carry: {', '.join(self.available_populations)}"
                )
            else:
                coverage += (
                    "; no ancestry source was supplied at all, so there is no label "
                    "that would have worked — supply a population allele-frequency "
                    "source or a haplotype panel"
                )
        # A build mismatch first: it is a *different statement* from "nothing here", and
        # the actionable one. An empty ancestry breakdown from a wrong-build file means
        # the file was never read, not that the ancestries are clean.
        mismatched = sorted((name, n) for name, n in self.source_build_mismatch.items() if n > 0)
        for name, count in mismatched:
            total = self.sources_considered.get(name, count)
            # "every one of the 2" reads very differently from "1 of the 2": the first is
            # a file for the wrong build, the second is one stale record in a good file.
            how_many = f"every one of the {total}" if count >= total else f"{count} of the {total}"
            coverage += (
                f"; {how_many} {name} record(s) in this region assert a reference base "
                "this genome does not have — that is a build mismatch, not an absence of "
                "population risk, and those records were skipped"
            )
        inert = sorted(name for name, n in self.sources_considered.items() if n == 0)
        if inert:
            # "in this region" alone attributed an empty contribution to the locus. The
            # MAF cut-off is the other reason a supplied source comes back with nothing,
            # and it is the one the caller chose.
            at_maf = f" at MAF >= {self.maf_threshold:g}" if self.maf_threshold is not None else ""
            coverage += (
                f"; supplied but contributing nothing in this region{at_maf}: "
                f"{', '.join(inert)} — the scan is that much closer to reference-only "
                "here, and an empty ancestry breakdown means 'not measured', not 'clean'"
            )
        # The population cut-off, whenever one applied. It gates which alleles enter the
        # scan, so it moves the numbers the same way the reporting cut-offs do.
        population_cutoff = (
            f"; population alleles at MAF >= {self.maf_threshold:g}"
            if self.maf_threshold is not None
            else ""
        )
        # The extent, unconditionally -- except that "over 0 bases" beside a table of
        # nominated sites is not a scope, it is a contradiction. `searched_bases` has a
        # default, so a report deserialized from before the field existed arrives at 0
        # with sites attached; saying the extent is unrecorded is the honest form, and
        # keeps the reader from comparing two numbers that are not comparable.
        if self.searched_bases > 0:
            extent = f"over {self.searched_bases:,} bases; "
        elif self.sites:
            extent = "over an unrecorded extent (not comparable with another report); "
        else:
            extent = ""  # the empty-search clause below already says what happened
        return (
            f"{extent}"
            f"up to {self.mismatch_threshold} mismatches, "
            f"{self.dna_bulge_budget} DNA / {self.rna_bulge_budget} RNA bulges; "
            f"sites reported at CFD >= {self.cfd_threshold:g} "
            f"or MIT >= {self.mit_threshold:g}{population_cutoff}{coverage}"
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

    def is_frequency_weighted(self) -> bool:
        """Return ``True`` if any site's presence in a genome is probabilistic.

        A reference site is in every genome and a patient site is certain in this one,
        so with only those, :meth:`expected_burden` is just the unweighted score sum and
        says nothing :meth:`specificity_score` does not. It becomes a distinct number
        exactly when a population or haplotype site carries a frequency — which is when
        a rare-variant off-target and a universal one stop being interchangeable. Every
        surface asks this before reporting the burden, so they agree on when it is worth
        a reader's attention.
        """
        return any(
            site.origin is not SiteOrigin.REFERENCE and site.frequency is not None
            for site in self.sites
        )

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

    def ancestry_expected_burden(self) -> dict[str, float]:
        """Return the frequency-weighted expected off-target burden per ancestry.

        :meth:`ancestry_stratification` reports the worst *score* per ancestry, and a
        score does not depend on ancestry — only on the sequence. So on the finding this
        engine exists to reproduce (a minor allele creating a de-novo PAM, enriched in
        one population) the stratification reads::

            worst off-target score by ancestry: afr 1.000, amr 1.000, nfe 1.000

        Three identical numbers over frequencies of 0.105, 0.012 and 0.001. A reader
        takes that as risk spread evenly across ancestries, which is the opposite of the
        published finding, and the opposite of what the site line beneath it says.

        The blindness is already named in this class: :meth:`expected_burden`'s docstring
        says it "separates a rare-variant off-target from a universal one, which the
        frequency-blind :meth:`worst_score` and :meth:`specificity_score` cannot" — and
        the ancestry axis, the one thing the population-aware search is for, was reported
        with the frequency-blind statistic.

        Weighted per ancestry, so the same site contributes what a genome from *that*
        population is actually likely to carry. Unattributed sites (a reference site, a
        patient site, or a population site with no per-ancestry breakdown) count at full
        weight for every ancestry, exactly as they do in :meth:`ancestry_stratification`
        and :meth:`expected_burden`: not knowing which stratum carries a site is not a
        reason to discount it.

        This does **not** replace the worst-case score, and does not touch the ranking
        safety axis, which :meth:`worst_ancestry` still drives. "Is there a dangerous
        site at all" and "how often is it actually there" are two questions, and the
        second was the one with no answer.
        """
        ancestries: set[str] = set()
        for site in self.sites:
            ancestries.update(site.ancestries)
        burden: dict[str, float] = {}
        for ancestry in sorted(ancestries):
            total = 0.0
            for site in self.sites:
                unattributed = (
                    site.origin is SiteOrigin.REFERENCE
                    or site.frequency is None
                    or not site.ancestries
                )
                if unattributed:
                    total += site.score
                else:
                    total += site.score * site.ancestries.get(ancestry, 0.0)
            burden[ancestry] = total
        return burden

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


def headline_notes(report: OffTargetReport) -> tuple[str, ...]:
    """Return the short forms of everything in this report a caller can act on.

    :meth:`OffTargetReport.search_description` is one sentence carrying a dozen clauses.
    Most describe what the scan *did* — the mismatch budget, the reporting cut-offs, the
    sub-threshold tail, the PAM broadening — and are exactly where they belong, because a
    reader consults them to interpret a number. A few say **the caller supplied something
    that will not do what they think**, and those were in the same neutral paragraph, in
    the sixth clause of a sentence a reader skims.

    Built from the model's fields, never by parsing the description, so the two cannot
    disagree — and the description is not modified: it is what travels inside a written
    artifact, while these are for a terminal and a screen. Each is held short for the
    same reason a headline that repeats the paragraph is a headline nobody reads.

    Deliberately excluded: an *inert* source (supplied, in scope, contributed nothing).
    That is the ordinary outcome of a region with no common variants — nothing to act on
    — while the mismatch below is the same shape with a cause the caller can fix. The
    difference is worth the exclusion note: it is the one judgement call in this list.
    """
    notes: list[str] = []
    if report.searched_bases == 0 and report.sites == ():
        notes.append("NO SEQUENCE WAS SEARCHED — this is an empty result, not a clean one")
    low, high = GUIDE_SPACER_RANGE
    if report.spacer and not low <= len(report.spacer) <= high:
        notes.append(
            f"the query is {len(report.spacer)} nt, not a guide length — this is a "
            "sequence search, not an off-target profile"
        )
    if report.ambiguous_spacer_positions:
        listed = ", ".join(str(p) for p in report.ambiguous_spacer_positions)
        notes.append(f"the spacer is ambiguous at position(s) {listed}, which pushes scores DOWN")
    # A cut-off outside the score range. Both criteria above 1 is how a caller turns
    # nomination off, which is legitimate and produces `0 site(s)` — the most reassuring
    # output this system can make. Below 0 is the mirror: every placement nominated. The
    # aggregate stays honest either way (the sub-threshold tail is in the denominator),
    # and the site *count* does not, so the count says which question it answered.
    unreachable = [
        f"{name} {value:g}"
        for name, value in (("CFD", report.cfd_threshold), ("MIT", report.mit_threshold))
        if value > 1.0
    ]
    if len(unreachable) == 2:
        notes.append(
            f"no site can clear either cut-off ({', '.join(unreachable)}) — the site "
            "count is 0 because nothing was nominatable, not because nothing was found"
        )
    if report.maf_threshold is not None and report.maf_threshold > 1.0:
        notes.append(
            f"no allele can reach MAF {report.maf_threshold:g} — the population pass was "
            "turned off by the cut-off, so this scan is reference-only"
        )
    mismatch = build_mismatch_note(report)
    if mismatch is not None:
        notes.append(mismatch)
    if report.unbacked_populations:
        notes.append(
            f"not examined for {', '.join(report.unbacked_populations)} — no supplied "
            "source carries them"
        )
    return tuple(notes)


def build_mismatch_note(report: OffTargetReport) -> str | None:
    """Return a short note for a source whose records are for another assembly.

    The full sentence is already in :meth:`OffTargetReport.search_description`, at the end
    of a paragraph that also carries the mismatch budget, the reporting cut-offs, the
    sub-threshold tail and the PAM broadening. Every one of those describes *what the scan
    did*; this one says **the caller supplied the wrong file**, and it is the only clause
    with a remedy. `aforge offtarget` already elevates the other such clause — the
    on-target locus — out of the paragraph and onto the headline in brackets, which is the
    precedent this follows.

    Returns:
        A bracket-ready note, or ``None`` when every supplied record agreed with the
        reference. Short on purpose: the paragraph keeps the full explanation, and a
        headline that repeats it is a headline nobody reads.
    """
    parts = [
        f"{name}: {count} of {report.sources_considered.get(name, count)} record(s) "
        "are for another build"
        for name, count in sorted(report.source_build_mismatch.items())
        if count
    ]
    return "; ".join(parts) if parts else None


def published(report: OffTargetReport) -> OffTargetReport:
    """Return ``report`` with every number rounded to the precision surfaces publish.

    A rendering rule, owned by the library because two surfaces were applying two of
    them: `aforge offtarget --json` (and the TSV export, and the report) round a site
    score to four places, and the HTTP response serialized the model as-is — so one guide
    came back `0.8824` from one shell and `0.882353` from the other, with the same
    difference on the aggregate specificity. A client filtering at a threshold got two
    answers to one question, and neither surface was wrong on its own.

    The stored model keeps full precision: this is what a *reader* is given, not what the
    engine computed with.
    """
    sites = tuple(
        site.model_copy(
            update={
                "score": round(site.score, AGGREGATE_PRECISION),
                "mit_score": (
                    None if site.mit_score is None else round(site.mit_score, AGGREGATE_PRECISION)
                ),
                "frequency": (
                    None if site.frequency is None else round(site.frequency, FREQUENCY_PRECISION)
                ),
                "ancestries": {
                    ancestry: round(value, FREQUENCY_PRECISION)
                    for ancestry, value in site.ancestries.items()
                },
            }
        )
        for site in report.sites
    )
    return report.model_copy(
        update={
            "sites": sites,
            "subthreshold_score_sum": round(report.subthreshold_score_sum, AGGREGATE_PRECISION),
        }
    )
