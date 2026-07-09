"""Request and response models for the AlleleForge web API.

Requests are small typed envelopes; responses reuse the Phase 1 domain schemas
(``RankedMenu``, ``OffTargetReport``, ``DatasetDescriptor``) and the Phase 11
report model, so the same pydantic contracts validate the HTTP boundary that
validate the library. FastAPI generates the OpenAPI spec from these.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from alleleforge.types.offtarget import OffTargetReport

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
MAX_POPULATIONS = 64
MAX_CHEMISTRIES = 16

#: A variant input string bounded to :data:`MAX_VARIANT_LEN`, usable as a list item.
VariantStr = Annotated[str, Field(max_length=MAX_VARIANT_LEN)]
#: An ancestry/population label bounded so a huge list element can't slip the count cap.
PopulationStr = Annotated[str, Field(max_length=MAX_BUILD_LEN)]
#: A chemistry name bounded likewise.
ChemistryStr = Annotated[str, Field(max_length=MAX_BUILD_LEN)]


class ResolveRequest(BaseModel):
    """A request to normalize any variant input form."""

    model_config = ConfigDict(frozen=True)

    variant: str = Field(
        max_length=MAX_VARIANT_LEN, description="ClinVar / rsID / HGVS / VCF / coords input."
    )
    build: str = Field(
        default="hg38",
        max_length=MAX_BUILD_LEN,
        description="Reference build the input is expressed in.",
    )


class ResolveResponse(BaseModel):
    """The normalized variant and its analysis context."""

    model_config = ConfigDict(frozen=True)

    variant: str
    variant_class: str
    build: str
    source: str
    working_interval: str
    reference_recommendation: str | None = None


class DesignRequest(BaseModel):
    """A request to design a ranked, multi-chemistry editing menu."""

    model_config = ConfigDict(frozen=True)

    variant: str = Field(
        max_length=MAX_VARIANT_LEN, description="ClinVar / rsID / HGVS / VCF / coords input."
    )
    intent: str = Field(default="correct", description="correct | knock_out | install | revert.")
    chemistries: list[ChemistryStr] | None = Field(
        default=None,
        max_length=MAX_CHEMISTRIES,
        description="Restrict to these chemistries (default: all eligible).",
    )
    populations: list[PopulationStr] | None = Field(
        default=None,
        max_length=MAX_POPULATIONS,
        description="Ancestry labels to query and stratify off-target by.",
    )
    weights: list[float] | None = Field(
        default=None,
        description="Ranking weights [efficiency, cleanliness, safety, simplicity].",
        min_length=4,
        max_length=4,
    )
    max_per_chemistry: int | None = Field(
        default=None, ge=1, description="Cap candidates kept per chemistry."
    )
    run_offtarget: bool = Field(default=True, description="Run the off-target engine.")


class BatchRequest(BaseModel):
    """A request to design a cohort of variants in one streaming run."""

    model_config = ConfigDict(frozen=True)

    variants: list[VariantStr] = Field(
        min_length=1,
        max_length=MAX_BATCH_VARIANTS,
        description="Variant input forms (ClinVar / rsID / HGVS / coords).",
    )
    intent: str = Field(default="correct", description="correct | knock_out | install | revert.")
    chemistries: list[ChemistryStr] | None = Field(
        default=None,
        max_length=MAX_CHEMISTRIES,
        description="Restrict to these chemistries (default: all eligible).",
    )
    populations: list[PopulationStr] | None = Field(
        default=None,
        max_length=MAX_POPULATIONS,
        description="Ancestry labels to query and stratify off-target by.",
    )
    weights: list[float] | None = Field(
        default=None,
        description="Ranking weights [efficiency, cleanliness, safety, simplicity].",
        min_length=4,
        max_length=4,
    )
    max_per_chemistry: int | None = Field(
        default=None, ge=1, description="Cap candidates kept per chemistry."
    )
    run_offtarget: bool = Field(default=True, description="Run the off-target engine.")


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
    disclaimer: str


class OffTargetRequest(BaseModel):
    """A request for a standalone population-aware off-target search."""

    model_config = ConfigDict(frozen=True)

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
    populations: list[PopulationStr] | None = Field(
        default=None, max_length=MAX_POPULATIONS, description="Ancestry labels to stratify by."
    )


class OffTargetResponse(BaseModel):
    """A standalone off-target search result with its aggregate summary.

    The single-number aggregates a client wants to triage on — site count,
    worst-case score, and the genome-wide specificity score — are *methods* on
    :class:`OffTargetReport`, so they are absent from its serialized fields. This
    envelope projects them alongside the full report, giving an API client the
    same summary the ``aforge offtarget`` CLI surfaces.
    """

    model_config = ConfigDict(frozen=True)

    report: OffTargetReport
    n_sites: int = Field(description="Number of nominated off-target sites.")
    worst_score: float = Field(description="Highest single-site off-target score (0 if none).")
    specificity: float = Field(
        description="Aggregate genome-wide specificity 1/(1+Σ scores) in (0, 1]."
    )
    ancestry_stratification: dict[str, float] = Field(
        description="Worst-case off-target score per annotated ancestry."
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

    @classmethod
    def from_report(cls, report: OffTargetReport) -> OffTargetResponse:
        """Build the envelope from a report, computing its aggregate summary."""
        return cls(
            report=report,
            n_sites=report.n_sites,
            worst_score=report.worst_score(),
            specificity=report.specificity_score(),
            ancestry_stratification=report.ancestry_stratification(),
            effective_matrix=report.effective_matrix(),
        )


class HealthResponse(BaseModel):
    """Liveness and capability report."""

    model_config = ConfigDict(frozen=True)

    status: str
    version: str
    reference_loaded: bool
    disclaimer: str


class DatasetRow(BaseModel):
    """One dataset registry row (summary form)."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str | None
    license: str | None
    redistributable: bool


class DataListResponse(BaseModel):
    """The dataset registry listing."""

    model_config = ConfigDict(frozen=True)

    datasets: tuple[DatasetRow, ...]


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


class JobState(StrEnum):
    """Lifecycle state of an async design job."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobSubmitResponse(BaseModel):
    """The handle returned when an async job is accepted."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    state: JobState
