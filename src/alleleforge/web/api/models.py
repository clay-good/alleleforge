"""Request and response models for the AlleleForge web API.

Requests are small typed envelopes; responses reuse the Phase 1 domain schemas
(``RankedMenu``, ``OffTargetReport``, ``DatasetDescriptor``) and the Phase 11
report model, so the same pydantic contracts validate the HTTP boundary that
validate the library. FastAPI generates the OpenAPI spec from these.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from alleleforge.design.ranking import OBJECTIVES
from alleleforge.report.builder import COORDINATE_SYSTEM, RESEARCH_USE_OFFTARGET
from alleleforge.types.offtarget import (
    AGGREGATE_PRECISION,
    ANCESTRY_BURDEN_PRECISION,
    OffTargetReport,
    published,
)
from alleleforge.types.sequence import GenomicInterval, Strand

#: Maximum number of variants a single batch request may carry. Bounds the work a
#: caller can queue in one request, so a shared (non-loopback) deployment cannot be
#: flooded with an unbounded cohort. Callers with more variants page across requests.
MAX_BATCH_VARIANTS = 1000

#: Per-field size caps. The batch *count* cap alone left individual field sizes
#: unbounded, so a within-count request could still carry multi-megabyte strings or
#: lists that reach genome-scale work — the request-size cap the web-API hardening
#: promised. These bounds are generous — far above any legitimate input (a real
#: spacer is <=~30 nt, an HGVS/coords string is short, gnomAD/1000G/HGDP expose
#: ~30 ancestry labels) — so no genuine request is rejected while pathological
#: inputs are refused at the boundary before any scan.
MAX_VARIANT_LEN = 8192  # HGVS delins can inline an inserted sequence; still generous
MAX_BUILD_LEN = 128
MAX_SPACER_LEN = 512
MAX_PAM_LEN = 64
#: Longest accepted cell-line / cell-type label.
MAX_CELL_CONTEXT_LEN = 128
#: Longest accepted contig name.
MAX_CHROM_LEN = 128
#: Most intervals a single request may restrict a scan to.
MAX_REGIONS = 1000
MAX_POPULATIONS = 64
MAX_CHEMISTRIES = 16


def _not_blank(value: str) -> str:
    """Refuse a field that was sent with an empty or whitespace-only value.

    The CLI refuses `--cell-context ""` because `value or default` cannot tell an empty
    string from an omitted flag, and an unset shell variable is how that empty string
    usually arrives. The web models had the same hole with the same consequence and no
    check: `{"cell_context": ""}` answered 200 with a design whose out-of-distribution
    flag could never be raised, and `{"populations": [""]}` answered 200 with no
    population analysis — a client that JSON-encodes an empty form field is the
    browser's version of the unset variable. The library is the source of truth and the
    two shells must not disagree about what they accept.
    """
    if not value.strip():
        raise ValueError(
            "this field was sent empty. Omit it to use the default; an empty string is "
            "usually an unfilled form field or an unset variable, and it is not the "
            "same request as not asking."
        )
    return value


#: A string that, if present at all, must say something.
NonBlank = AfterValidator(_not_blank)


def _drop_blanks(values: list[str]) -> list[str]:
    """Drop blank entries from a list field, refusing one that is blank all through.

    A *list* is not a scalar, and the two mistakes are different. `afr,,eas` — a stray
    comma, the commonest typo in a comma-separated list — has an unambiguous intent, and
    `aforge design --populations afr,,eas` has always dropped the empty element and run.
    Applying the scalar rule element-wise made the served page refuse it, because the
    page's own parser trims each entry and keeps the empty one: `["afr", "", "eas"]`.
    Two shells, two answers, from a check meant to stop exactly that.

    A list with nothing in it *is* the scalar mistake — the field was filled in with
    commas and no labels — so that is still refused, matching `--populations ""`.
    """
    kept = [value for value in values if value.strip()]
    if values and not kept:
        raise ValueError(
            "this field names nothing. Omit it to use the default; a list of empty "
            "entries is usually an unfilled form field or an unset variable."
        )
    return kept


#: A list field whose blank entries are the user's stray comma, not their request.
DropBlanks = AfterValidator(_drop_blanks)

#: A variant input string bounded to :data:`MAX_VARIANT_LEN`, usable as a list item.
VariantStr = Annotated[str, Field(max_length=MAX_VARIANT_LEN)]
#: An ancestry/population label bounded so a huge list element can't slip the count cap.
PopulationStr = Annotated[str, Field(max_length=MAX_BUILD_LEN)]
#: A chemistry name bounded likewise.
ChemistryStr = Annotated[str, Field(max_length=MAX_BUILD_LEN)]

#: An edit intent is one of four short words, and an unrecognized one is echoed back in
#: the 422 (`unknown intent '...'`, so a caller can see their typo). Unbounded, that echo
#: reflects whatever was sent: a 100 KB intent produced a 100 KB error response. Every
#: other string on these models was already bounded; this was the one that was not.
IntentStr = Annotated[str, Field(max_length=MAX_BUILD_LEN), NonBlank]

#: A specificity-scorer name, bounded for the same reason as the intent above; the
#: set of valid names lives in `scorer_for`, which raises with the list on a miss.
ScorerStr = Annotated[str, Field(max_length=MAX_BUILD_LEN), NonBlank]


class ResolveRequest(BaseModel):
    """A request to normalize any variant input form."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant: str = Field(
        max_length=MAX_VARIANT_LEN,
        description=(
            "Coordinates (chrom:pos:ref>alt, 1-based as in a VCF) or a VCF record. A "
            "ClinVar accession, a dbSNP rsID or a coding/protein HGVS string needs a "
            "lookup database this deployment has no way to supply — the 422 says so "
            "and names the coordinate form."
        ),
    )
    build: str | None = Field(
        default=None,
        max_length=MAX_BUILD_LEN,
        description=(
            "Reference build the input coordinates are expressed in. Defaults to "
            "whatever assembly this deployment serves, reported as `reference_build` by "
            "`GET /api/health`; stating a different one is a 422, because the same "
            "coordinate is a different base in two assemblies."
        ),
    )
    annotate_consequence: bool = Field(
        default=False,
        description=(
            "Annotate the variant's predicted molecular consequence via Ensembl VEP. "
            "Off by default and available only where the operator has enabled it "
            "(`ALLELEFORGE_VEP`), because it sends this variant — chromosome, position "
            "and both alleles — to a third-party public server. `GET /api/health` says "
            "whether this deployment offers it; a request for it where it is not "
            "configured is a 422, not a silent omission."
        ),
    )


class ResolveResponse(BaseModel):
    """The normalized variant and its analysis context."""

    model_config = ConfigDict(frozen=True)

    variant: str
    variant_class: str
    changes_the_sequence: bool = True
    """Whether the normalized variant differs from the reference at all.

    `variant_class` is computed from the allele *lengths*, so a one-base ref and a
    one-base alt is an `snv` whether or not they differ. A variant whose alleles are
    equal changes nothing and no reagent can be designed for it — reported rather
    than refused, because a reference call is a legitimate VCF row.
    """
    build: str
    source: str
    working_interval: str
    #: The convention every locus in this response is in — the working interval, and the
    #: position inside `variant`. A genome browser reads the same digits as 1-based
    #: inclusive. Every other locus-bearing surface states it; this one did not.
    coordinate_system: str = COORDINATE_SYSTEM
    #: Whether a reference genome was available to check this normalization. Without one,
    #: the REF allele is not verified and the variant is not left-aligned — and the
    #: response was otherwise byte-identical to a verified one.
    reference_checked: bool = False
    #: The genome that checked it, when one did. `build` is only a label: two FASTAs both
    #: called hg38 are not the same genome.
    reference: dict[str, Any] | None = None
    reference_recommendation: str | None = None
    #: Why a different build is recommended — the ambiguous regions the locus overlaps.
    #: The build name on its own does not say that alignment here is ambiguous, which is
    #: the part that matters: an off-target search at such a locus under-reports.
    reference_recommendation_reason: str | None = None
    #: Whether the consequence was asked for at all. Stated for the same reason as
    #: `reference_checked`: a null `consequence` without it means nobody asked, not that
    #: VEP looked and found the variant unremarkable.
    consequence_checked: bool = False
    consequence: str | None = None
    impact: str | None = None
    gene: str | None = None
    #: What a clinical database asserts about the variant, when resolution came from one.
    #: Over HTTP no client can supply a lookup, so this is `None` for every request today
    #: — carried because the field is the CLI's and the two `resolve` surfaces answering
    #: the same question differently is how one of them quietly stops being checked.
    clinical_significance: str | None = None
    #: The class alone is not the claim: the same class "reviewed by expert panel" and
    #: "no assertion criteria provided" is very different evidence.
    clinical_review_status: str | None = None


class VectorSchemeName(StrEnum):
    """The cloning vectors a request may name.

    Spelled out rather than generated from :data:`VECTOR_SCHEMES` so mypy and the
    OpenAPI schema can both see the members; a test pins the two lists equal, since a
    scheme that exists and cannot be requested is the gap this enum was added to close.
    """

    LENTIGUIDE_BSMBI = "lentiguide-bsmbi"
    PEGRNA_GG_BSAI = "pegrna-gg-bsai"
    PX330_BBSI = "px330-bbsi"


class DesignRequest(BaseModel):
    """A request to design a ranked, multi-chemistry editing menu."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant: str = Field(
        max_length=MAX_VARIANT_LEN,
        description=(
            "Coordinates (chrom:pos:ref>alt, 1-based as in a VCF) or a VCF record. A "
            "ClinVar accession, a dbSNP rsID or a coding/protein HGVS string needs a "
            "lookup database this deployment has no way to supply — the 422 says so "
            "and names the coordinate form."
        ),
    )
    build: str | None = Field(
        default=None,
        max_length=MAX_BUILD_LEN,
        description=(
            "Reference build the input coordinates are expressed in. Defaults to "
            "whatever assembly this deployment serves, reported as `reference_build` by "
            "`GET /api/health`; stating a different one is a 422, because the same "
            "coordinate is a different base in two assemblies."
        ),
    )
    intent: IntentStr = Field(
        default="correct", description="correct | knock_out | install | revert."
    )
    chemistries: Annotated[list[ChemistryStr], DropBlanks] | None = Field(
        default=None,
        max_length=MAX_CHEMISTRIES,
        description="Restrict to these chemistries (default: all eligible).",
    )
    populations: Annotated[list[PopulationStr], DropBlanks] | None = Field(
        default=None,
        max_length=MAX_POPULATIONS,
        description="Ancestry labels to query and stratify off-target by.",
    )
    offtarget_regions: list[Region] | None = Field(
        default=None,
        max_length=MAX_REGIONS,
        description=(
            "Restrict the off-target search to these intervals (default: every contig). "
            "Scoping to a gene panel is usually what makes a scan over a real reference "
            "practical. Sent as objects, the same shape a reported site's `locus` has."
        ),
    )
    cell_context: Annotated[str, NonBlank] | None = Field(
        default=None,
        max_length=MAX_CELL_CONTEXT_LEN,
        description=(
            "The target cell line or type (e.g. HEK293T, K562, HepG2). Consumed by "
            "prime editing, where a context outside the scorer's training distribution "
            "flags the efficiency prediction out-of-distribution instead of reporting "
            "it as if it were in-domain. SpCas9 nuclease and base editing do not take "
            "it, and the rationale says so when a context is supplied and they run. "
            "Omitted, no OOD claim is made either way."
        ),
    )
    render_candidates: int | None = Field(
        default=None,
        ge=0,
        le=10_000,
        description=(
            "How many candidates the html/pdf render draws (default 50; 0 for all). "
            "Every Pareto-front candidate is drawn whatever the cap, and the page states "
            "what it withheld. The json export is never capped."
        ),
    )
    weights: list[float] | None = Field(
        default=None,
        description=f"Ranking weights [{', '.join(OBJECTIVES)}], in that order.",
        min_length=len(OBJECTIVES),
        max_length=len(OBJECTIVES),
    )
    chromatin_track: str | None = Field(
        default=None,
        description=(
            "Which of the deployment's accessibility tracks to read for the "
            "ePRIDICT-style open-chromatin efficiency adjustment (prime editing). The "
            "names are listed by `GET /api/health`; the tracks file itself is configured "
            "by the operator."
        ),
    )
    annotate_consequence: bool = Field(
        default=False,
        description=(
            "Annotate the variant's predicted molecular consequence via Ensembl VEP. "
            "Off by default and available only where the operator has enabled it "
            "(`ALLELEFORGE_VEP`), because it sends this variant — chromosome, position "
            "and both alleles — to a third-party public server. `GET /api/health` says "
            "whether this deployment offers it; a request for it where it is not "
            "configured is a 422, not a silent omission."
        ),
    )
    trained_efficiency: bool = Field(
        default=False,
        description=(
            "Score SpCas9 efficiency with the trained Rule Set 3 model instead of the "
            "weight-free baseline. Off by default and available only where the operator "
            "has enabled it (`ALLELEFORGE_TRAINED_MODELS`), because the weights are a "
            "consent-gated download onto the server's disk. `GET /api/health` lists the "
            "trained models this deployment offers; asking for one it does not is a 422, "
            "not a silent fall back to the baseline."
        ),
    )
    trained_outcome: bool = Field(
        default=False,
        description=(
            "Predict the SpCas9 indel spectrum with the trained Lindel model instead of "
            "the microhomology baseline. Operator-gated; see `trained_efficiency`."
        ),
    )
    trained_base_outcome: bool = Field(
        default=False,
        description=(
            "Predict the base-edit window outcome with the trained BE-DICT model "
            "instead of the weight-free baseline. Operator-gated; see "
            "`trained_efficiency`."
        ),
    )
    trained_prime: bool = Field(
        default=False,
        description=(
            "Score prime-editing efficiency with the trained DeepPrime model instead of "
            "the transparent PRIDICT2-style baseline. Operator-gated; see "
            "`trained_efficiency`."
        ),
    )
    max_per_chemistry: int | None = Field(
        default=None, ge=1, description="Cap candidates kept per chemistry."
    )
    run_offtarget: bool = Field(default=True, description="Run the off-target engine.")
    allow_ng: bool = Field(
        default=False,
        description=(
            "Offer SpCas9-NG (NG PAM) guides when no NGG guide is actionable. Off by "
            "default: an NG guide is a different reagent with different specificity. "
            "Consumed by SpCas9 nuclease design alone — prime and base editing take no "
            "PAM-flexible fallback, and the rationale says so when one is enabled and "
            "the nuclease vertical did not run."
        ),
    )
    allow_spry: bool = Field(
        default=False,
        description="Offer SpRY (NRN/NYN PAM) guides when neither NGG nor NG yields one.",
    )
    vector_scheme: VectorSchemeName | None = Field(
        default=None,
        description=(
            "The cloning vector the guide oligos are ordered for (default "
            "lentiguide-bsmbi). This picks the Type IIS enzyme the inserts are "
            "screened against for a cloning-lethal internal recognition site, so "
            "naming the wrong vector reports an insert clean that your own enzyme "
            "cuts. A pegRNA candidate keeps the pegRNA acceptor when an sgRNA-only "
            "vector is named, and every candidate names the vector it used."
        ),
    )


class BatchRequest(BaseModel):
    """A request to design a cohort of variants in one streaming run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variants: list[VariantStr] = Field(
        min_length=1,
        max_length=MAX_BATCH_VARIANTS,
        description="Variant input forms (ClinVar / rsID / HGVS / coords).",
    )
    build: str | None = Field(
        default=None,
        max_length=MAX_BUILD_LEN,
        description=(
            "Reference build the input coordinates are expressed in. Defaults to "
            "whatever assembly this deployment serves, reported as `reference_build` by "
            "`GET /api/health`; stating a different one is a 422, because the same "
            "coordinate is a different base in two assemblies."
        ),
    )
    intent: IntentStr = Field(
        default="correct", description="correct | knock_out | install | revert."
    )
    chemistries: Annotated[list[ChemistryStr], DropBlanks] | None = Field(
        default=None,
        max_length=MAX_CHEMISTRIES,
        description="Restrict to these chemistries (default: all eligible).",
    )
    populations: Annotated[list[PopulationStr], DropBlanks] | None = Field(
        default=None,
        max_length=MAX_POPULATIONS,
        description="Ancestry labels to query and stratify off-target by.",
    )
    weights: list[float] | None = Field(
        default=None,
        description=f"Ranking weights [{', '.join(OBJECTIVES)}], in that order.",
        min_length=len(OBJECTIVES),
        max_length=len(OBJECTIVES),
    )
    chromatin_track: str | None = Field(
        default=None,
        description=(
            "Which of the deployment's accessibility tracks to read for the "
            "open-chromatin efficiency adjustment; names are listed by `GET /api/health`."
        ),
    )
    annotate_consequence: bool = Field(
        default=False,
        description=(
            "Annotate each item's predicted molecular consequence via Ensembl VEP. "
            "Off by default and available only where the operator has enabled it "
            "(`ALLELEFORGE_VEP`), because it sends every variant in the cohort to a "
            "third-party public server. `GET /api/health` says whether this deployment "
            "offers it."
        ),
    )
    trained_efficiency: bool = Field(
        default=False,
        description=(
            "Score SpCas9 efficiency with the trained Rule Set 3 model instead of the "
            "weight-free baseline. Off by default and available only where the operator "
            "has enabled it (`ALLELEFORGE_TRAINED_MODELS`), because the weights are a "
            "consent-gated download onto the server's disk. `GET /api/health` lists the "
            "trained models this deployment offers; asking for one it does not is a 422, "
            "not a silent fall back to the baseline."
        ),
    )
    trained_outcome: bool = Field(
        default=False,
        description=(
            "Predict the SpCas9 indel spectrum with the trained Lindel model instead of "
            "the microhomology baseline. Operator-gated; see `trained_efficiency`."
        ),
    )
    trained_base_outcome: bool = Field(
        default=False,
        description=(
            "Predict the base-edit window outcome with the trained BE-DICT model "
            "instead of the weight-free baseline. Operator-gated; see "
            "`trained_efficiency`."
        ),
    )
    trained_prime: bool = Field(
        default=False,
        description=(
            "Score prime-editing efficiency with the trained DeepPrime model instead of "
            "the transparent PRIDICT2-style baseline. Operator-gated; see "
            "`trained_efficiency`."
        ),
    )
    max_per_chemistry: int | None = Field(
        default=None, ge=1, description="Cap candidates kept per chemistry."
    )
    run_offtarget: bool = Field(default=True, description="Run the off-target engine.")
    # These four reached `design()` from `DesignRequest` and from `aforge batch`, and
    # from here they did not -- so the most expensive path was the one that could not be
    # scoped, and a cohort item with no NGG guide came back empty with no way to offer
    # the fallback that exists for exactly that case.
    offtarget_regions: list[Region] | None = Field(
        default=None,
        max_length=MAX_REGIONS,
        description=(
            "Restrict the off-target search to these intervals (default: every contig). "
            "Scoping to a gene panel is usually what makes a scan over a real reference "
            "practical, and a cohort run is the most expensive path there is."
        ),
    )
    cell_context: Annotated[str, NonBlank] | None = Field(
        default=None,
        max_length=MAX_CELL_CONTEXT_LEN,
        description=(
            "The target cell line or type (e.g. HEK293T, K562, HepG2). Consumed by "
            "prime editing, where a context outside the scorer's training distribution "
            "flags the efficiency prediction out-of-distribution instead of reporting "
            "it as if it were in-domain. SpCas9 nuclease and base editing do not take "
            "it, and the rationale says so when a context is supplied and they run. "
            "Omitted, no OOD claim is made either way."
        ),
    )
    allow_ng: bool = Field(
        default=False,
        description=(
            "Offer SpCas9-NG (NG PAM) guides when no NGG guide is actionable. Off by "
            "default: an NG guide is a different reagent with different specificity. "
            "Consumed by SpCas9 nuclease design alone — prime and base editing take no "
            "PAM-flexible fallback, and the rationale says so when one is enabled and "
            "the nuclease vertical did not run."
        ),
    )
    allow_spry: bool = Field(
        default=False,
        description="Offer SpRY (NRN/NYN PAM) guides when neither NGG nor NG yields one.",
    )


class BatchItemResult(BaseModel):
    """The compact outcome of one cohort item (never the full menu)."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    status: str = Field(description="'ok' or 'error'.")
    summary: dict[str, object] | None = Field(
        default=None, description="Compact design summary (counts, best chemistry, off-target)."
    )
    error: str | None = Field(default=None, description="The error string when status == 'error'.")


class BatchResponse(BaseModel):
    """The aggregate outcome of a cohort design run."""

    model_config = ConfigDict(frozen=True)

    total: int
    succeeded: int
    failed: int
    items: tuple[BatchItemResult, ...]
    provenance: dict[str, object]
    #: The convention every locus in this response is in — including the `variant` each
    #: row carries, which is the *resolved* one and therefore 0-based. `ResolveResponse`,
    #: the design report and `OffTargetResponse` all state it, and `aforge batch --json`
    #: carries the same sentence; the cohort response over HTTP was the one document
    #: whose reader had to assume. A cohort is also the artifact most likely to be
    #: forwarded to someone who did not make the request.
    coordinate_system: str = COORDINATE_SYSTEM
    disclaimer: str


class Region(BaseModel):
    """A search-restriction interval: a locus without a strand.

    A restriction covers both strands by construction, so requiring one would be
    noise — but a client's most natural source for an interval is a `locus` copied
    out of a previous response, which *does* carry `strand` and
    `coordinate_system`. This accepts either: the extra keys are ignored and the
    strand is not read.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    chrom: str = Field(max_length=MAX_CHROM_LEN)
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    def to_interval(self) -> GenomicInterval:
        """Return the plus-strand :class:`GenomicInterval` this region names.

        Raises:
            ValueError: If the interval is empty — a zero-width restriction would
                silently scope the scan to nothing and report every guide spotless.
        """
        if self.end <= self.start:
            raise ValueError(f"region {self.chrom}:{self.start}-{self.end} is empty")
        return GenomicInterval(chrom=self.chrom, start=self.start, end=self.end, strand=Strand.PLUS)


class OffTargetRequest(BaseModel):
    """A request for a standalone population-aware off-target search."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    spacer: str = Field(max_length=MAX_SPACER_LEN, description="The on-target spacer (5'->3').")
    pam: str = Field(default="NGG", max_length=MAX_PAM_LEN, description="PAM pattern (IUPAC).")
    mismatches: int = Field(default=4, ge=0, le=8, description="Max mismatches.")
    dna_bulges: int = Field(default=1, ge=0, le=4, description="Max DNA bulges.")
    rna_bulges: int = Field(default=1, ge=0, le=4, description="Max RNA bulges.")
    cfd_threshold: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Report a site at or above this CFD score."
    )
    mit_threshold: float = Field(
        default=0.10, ge=0.0, le=1.0, description="...or at or above this MIT score."
    )
    maf: float = Field(
        default=0.001,
        ge=0.0,
        le=1.0,
        description="Min population allele frequency to consider carrying.",
    )
    populations: Annotated[list[PopulationStr], DropBlanks] | None = Field(
        default=None, max_length=MAX_POPULATIONS, description="Ancestry labels to stratify by."
    )
    offtarget_regions: list[Region] | None = Field(
        default=None,
        max_length=MAX_REGIONS,
        description=(
            "Restrict the off-target search to these intervals (default: every contig). "
            "Scoping to a gene panel is usually what makes a scan over a real reference "
            "practical. Sent as objects, the same shape a reported site's `locus` has."
        ),
    )
    scorer: ScorerStr | None = Field(
        default=None,
        description=(
            "Specificity scorer: 'cfd' (default, the published Doench 2016 matrix), "
            "'mit' (Hsu 2013 position weights), or 'cfd-cas12a' (the Cas12a analog, "
            '5\' seed and TTTV PAM — pair it with `pam: "TTTV"`). The choice travels '
            "into `effective_matrix`, so a Cas12a run is labelled as the unvalidated "
            "approximation it is rather than as the published matrix."
        ),
    )
    on_target: GenomicInterval | None = Field(
        default=None,
        description=(
            "The spacer's own locus, so it is not counted against itself. This is the "
            "same shape a reported site's `locus` has, so a client can copy one "
            "straight back. Omit it and the guide's own perfect match is reported like "
            "any other site, which caps the specificity — see `on_target_excluded`."
        ),
    )


class OffTargetResponse(BaseModel):
    """A standalone off-target search result with its aggregate summary.

    The single-number aggregates a client wants to triage on — site count,
    worst-case score, and the genome-wide specificity score — are *methods* on
    :class:`OffTargetReport`, so they are absent from its serialized fields. This
    envelope projects them alongside the full report, giving an API client the
    same summary the ``aforge offtarget`` CLI surfaces — including
    ``on_target_excluded``, without which ``specificity`` is not the same quantity
    a design report prints under that name.

    Every *numeric* method was projected and the one *prose* method was not, which
    made the envelope's own purpose false in the case that matters most: the CLI
    prints the aggregates and then ``search: …`` under them, and that line is what
    says a search covered 1% of what was asked for, or nothing at all. Without it a
    client reads ``n_sites: 0, specificity: 1.0`` as a spotless guide.
    """

    model_config = ConfigDict(frozen=True)

    report: OffTargetReport
    n_sites: int = Field(description="Number of nominated off-target sites.")
    worst_score: float = Field(description="Highest single-site off-target score (0 if none).")
    specificity: float = Field(
        description="Aggregate genome-wide specificity 1/(1+Σ scores) in (0, 1]."
    )
    expected_burden: float | None = Field(
        default=None,
        description=(
            "Frequency-weighted expected off-target burden, present only when some "
            "site's presence in a genome is probabilistic. `worst_score` and "
            "`specificity` are frequency-blind, so a 0.1%-MAF hit and a universal "
            "reference hit of the same raw score are indistinguishable in them."
        ),
    )
    on_target_excluded: bool = Field(
        description=(
            "Whether the spacer's own locus was excluded. When false, the guide's own "
            "perfect match is counted among the sites and the specificity is capped "
            "accordingly; supply `on_target` to drop it."
        )
    )
    search_description: str = Field(
        description=(
            "What the search actually covered, and what it could not: the budgets and "
            "cut-offs every number here is conditional on, the fraction of requested "
            "bases that held searchable sequence, any supplied source that was inert, "
            "and an explicit statement when NO sequence was searched. The CLI prints "
            "this under the aggregates; the numbers above are not readable without it."
        )
    )
    ancestry_stratification: dict[str, float] = Field(
        description="Worst-case off-target score per annotated ancestry."
    )
    ancestry_expected_burden: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Frequency-weighted expected off-target burden per annotated ancestry. A "
            "score does not depend on ancestry, so `ancestry_stratification` reads the "
            "same for every stratum even where the carrying frequency differs "
            "hundredfold — which is precisely the case the population-aware search "
            "exists to surface. This is the half that differs."
        ),
    )
    effective_matrix: str | None = Field(
        default=None,
        description=(
            "The weight matrix the *reported* sites were actually scored by. The embedded "
            "report's nominal `score_matrix` records how the scorer was configured, but a "
            "published matrix falls back to the length-relative approximation per off-register "
            "hit; this reconciles the per-site truth so a client is not misled into reading an "
            "all-approximation table as published CFD."
        ),
    )

    reference: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The genome that was searched: build label, contig and base counts, and a "
            "hash of the canonicalized `name:length` list. Every number here is "
            "conditional on it, and a build label alone is a name the deployment chose "
            "— two FASTAs both called hg38 give different specificities. `pins` states "
            "what the digest covers (contig names and lengths, not the bases)."
        ),
    )
    coordinate_system: str = Field(
        default=COORDINATE_SYSTEM,
        description=(
            "The convention every `locus` in the embedded report is in. A genome "
            "browser reads the same digits as 1-based inclusive."
        ),
    )
    disclaimer: str = Field(
        default=RESEARCH_USE_OFFTARGET,
        description=(
            "The research-use disclaimer. The off-target wording: this response nominates "
            "sites and ranks no candidates, so the sentence about ranked candidates would "
            "describe a menu that is not here."
        ),
    )

    @classmethod
    def from_report(
        cls,
        report: OffTargetReport,
        *,
        on_target_excluded: bool = False,
        reference: dict[str, Any] | None = None,
    ) -> OffTargetResponse:
        """Build the envelope from a report, computing its aggregate summary."""
        # Rounded to the same places `aforge offtarget --json` reports, from the constant
        # both read: the same guide came back `specificity 0.21` from one shell and
        # `0.21004997798215197` from the other, which is one question with two answers for
        # anything thresholding on it.
        burden = report.expected_burden() if report.is_frequency_weighted() else None
        return cls(
            # The same rounding every other surface publishes: a site score is `0.8824`
            # here as it is in `aforge offtarget --json` and in the TSV export.
            report=published(report),
            n_sites=report.n_sites,
            worst_score=round(report.worst_score(), AGGREGATE_PRECISION),
            specificity=round(report.specificity_score(), AGGREGATE_PRECISION),
            expected_burden=None if burden is None else round(burden, AGGREGATE_PRECISION),
            on_target_excluded=on_target_excluded,
            search_description=report.search_description(),
            ancestry_stratification={
                ancestry: round(value, AGGREGATE_PRECISION)
                for ancestry, value in report.ancestry_stratification().items()
            },
            ancestry_expected_burden={
                ancestry: round(value, ANCESTRY_BURDEN_PRECISION)
                for ancestry, value in report.ancestry_expected_burden().items()
            },
            effective_matrix=report.effective_matrix(),
            reference=reference,
        )


class JobState(StrEnum):
    """Lifecycle state of an async design job."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobStatusResponse(BaseModel):
    """An async job's state, coarse progress, and result when it is finished.

    The status endpoint returned a bare `dict`, so `progress` reached a client with no
    description at all — and it is **not** a continuous fraction. It takes exactly three
    values: `0.0` queued, `0.1` running, `1.0` finished. A client rendering it as a
    percentage shows 10% for the entire duration of a cohort run and then jumps to
    100%, which is a worse lie than showing nothing. Typed and documented so the shape
    is visible in the OpenAPI schema rather than inferred from two observations.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str
    #: Typed as the enum, not as `str`, so the four values reach the OpenAPI schema and
    #: a generated client can switch on them. As prose it said "queued | running | done |
    #: error" — and nothing ever emits `queued`; a job starts `pending`. A client polling
    #: for the documented first state waits forever, and the schema said only
    #: `type: string`, so there was nothing to check the prose against. The neighbouring
    #: `progress` field was typed and documented for exactly this reason one line below.
    state: JobState
    progress: float = Field(
        description=(
            "Coarse, three-valued: 0.0 queued, 0.1 running, 1.0 finished — finished "
            "meaning terminal, so a failed or timed-out job reports 1.0 too and `state` "
            "says which kind. NOT a completion fraction: a running job reports 0.1 "
            "whether it is 1% or 99% through. Render it as a state, not as a percentage."
        )
    )
    error: str | None = Field(default=None, description="The failure message, if the job failed.")
    result: dict[str, object] | None = Field(
        default=None, description="The design report, present only once the job is done."
    )


class HealthResponse(BaseModel):
    """Liveness and capability report."""

    model_config = ConfigDict(frozen=True)

    status: str
    version: str
    reference_loaded: bool
    #: The assembly this deployment serves, when a reference is loaded. A client sends
    #: coordinates, and a coordinate without an assembly is not a locus — the same
    #: `chr7:5,530,601` is a different base in hg38 and in T2T-CHM13. Nothing said which
    #: one the operator mounted, and the label the results carried was the constant
    #: "hg38" whatever the FASTA was.
    reference_build: str | None = None
    #: Whether a population allele-frequency source is configured. Without one every scan
    #: this deployment runs is reference-only, whatever ancestry labels a request asks
    #: for — a client cannot supply the source and had no way to find that out.
    gnomad_loaded: bool = False
    #: Whether a phased-haplotype panel is configured. Without one the haplotype-aware
    #: pass never runs, so a site that exists only on a co-inherited combination of
    #: alleles is not nominated — and, like the population source, a client cannot supply
    #: one.
    haplotypes_loaded: bool = False
    #: The accessibility tracks this deployment can read, by name. A client chooses one
    #: per request via `chromatin_track` and has no other way to learn what the
    #: operator's bedGraph contains.
    chromatin_tracks: tuple[str, ...] = ()
    #: Whether this deployment will annotate a variant's predicted consequence when a
    #: request asks. It is off unless the operator enabled it, because the annotation
    #: sends the client's variant to a third-party public server — a disclosure only
    #: the operator can consent to on behalf of the deployment.
    vep_enabled: bool = False
    #: The trained models this deployment will run when a request asks for one, by the
    #: request field that asks ("trained_efficiency", ...). Empty unless the operator
    #: enabled them: each is a consent-gated download or an external checkout on the
    #: operator's disk, so a client can choose per request but cannot turn one on. A
    #: client has no other way to learn whether the numbers it gets back came from a
    #: trained model or the transparent baseline it can always reach.
    trained_models: tuple[str, ...] = ()
    #: Whether this deployment runs the native Rust kernels, and which build. The same
    #: reasoning as `scan_reuse` below: the kernels are parity-proven to return exactly
    #: what the Python path returns, so a deployment without them answers identically and
    #: an order of magnitude slower on the off-target hot path, and a client had no way
    #: to learn which one it is talking to. `"STALE"` appears when the installed
    #: extension is older than the crate it sits beside — those kernels fall back to
    #: Python and their parity tests skip themselves.
    native_kernels: str = ""
    #: Which ways of reusing an expensive reference scan this deployment has enabled
    #: ("offtarget-cache", "genome-index"). A client cannot turn either on — they spend
    #: the operator's disk — and has no other way to learn that two deployments running
    #: the same code answer at very different speeds.
    scan_reuse: tuple[str, ...] = ()
    #: Whether every `/api/*` call except this one needs an `X-API-Token` header. The
    #: served page is not exempt from the gate and cannot guess it: on a token-protected
    #: deployment it loaded, showed this deployment's capabilities, and answered every
    #: action with `401 missing or invalid API token` — accurate, and unactionable in a
    #: browser, which cannot set a header by itself. Health is the one endpoint the gate
    #: lets through, so it is the only place the page can learn that it needs to ask.
    auth_required: bool = False
    #: Why a *configured* source is not loaded, keyed by source name; empty when every
    #: configured source loaded. Without it `gnomad_loaded: false` means either "the
    #: operator configured none" or "the operator configured one and it could not be
    #: read" — a broken deployment indistinguishable from a deliberate one, on the axis
    #: where the difference decides whether any population site can be nominated.
    source_errors: dict[str, str] = {}
    disclaimer: str


class DatasetRow(BaseModel):
    """One dataset registry row (summary form)."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str | None
    license: str | None
    #: A *licence* fact: AlleleForge is permitted to ship this. It is not a statement
    #: that the data is here — gnomAD v4.1 is CC0 and none of it ships — and this row
    #: carried it alone, which is the confusion the CLI table was fixed for.
    redistributable: bool
    #: The presence half. Whether a run on *this deployment* can use the dataset right
    #: now, and if not, whether it could even be fetched: the registry refuses to
    #: download what it cannot verify, and most descriptors carry no pinned checksum.
    bundled: bool = False
    cached: bool = False
    available: bool = False
    fetchable: bool = False
    #: The same one-line answer the CLI prints, so a client need not re-derive it.
    presence: str = ""


class DataListResponse(BaseModel):
    """The dataset registry listing."""

    model_config = ConfigDict(frozen=True)

    datasets: tuple[DatasetRow, ...]


class ModelRow(BaseModel):
    """One model-zoo card (summary form).

    The dataset registry has been answerable over HTTP since `GET /api/data` shipped.
    The model registry was not — while a request can ask for a trained model by name
    (`trained_efficiency`, ...) and `GET /api/health` says which ones the operator
    enabled, with nothing anywhere saying what those models are, what licence they carry
    or what they are documented to get wrong.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    chemistry: str | None
    license: str
    #: The licence half, split from the presence half for the same reason the dataset
    #: row splits them: "permitted" is not "present".
    research_use: bool = False
    commercial_use: bool = False
    #: The presence half. `available` is stricter than "the file is on disk": the
    #: registry refuses to load an unpinned checkpoint exactly as it refuses to fetch
    #: one, so an unpinned card is unusable however many bytes sit at its cache path.
    pinned: bool = False
    cached: bool = False
    available: bool = False
    fetchable: bool = False
    #: The same one-line answer the CLI prints, so a client need not re-derive it.
    presence: str = ""


class ModelListResponse(BaseModel):
    """The model registry listing."""

    model_config = ConfigDict(frozen=True)

    models: tuple[ModelRow, ...]


class BenchTaskRow(BaseModel):
    """One CRISPR-Bench task (summary form)."""

    model_config = ConfigDict(frozen=True)

    task: str
    kind: str
    chemistry: str | None
    dataset: str
    primary_metric: str
    metrics: tuple[str, ...]


class BenchListResponse(BaseModel):
    """The CRISPR-Bench task listing."""

    model_config = ConfigDict(frozen=True)

    tasks: tuple[BenchTaskRow, ...]


class JobSubmitResponse(BaseModel):
    """The handle returned when an async job is accepted."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    state: JobState
