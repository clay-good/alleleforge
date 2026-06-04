"""Request and response models for the AlleleForge web API.

Requests are small typed envelopes; responses reuse the Phase 1 domain schemas
(``RankedMenu``, ``OffTargetReport``, ``DatasetDescriptor``) and the Phase 11
report model, so the same pydantic contracts validate the HTTP boundary that
validate the library. FastAPI generates the OpenAPI spec from these.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ResolveRequest(BaseModel):
    """A request to normalize any variant input form."""

    model_config = ConfigDict(frozen=True)

    variant: str = Field(description="ClinVar / rsID / HGVS / VCF / coords input.")
    build: str = Field(default="hg38", description="Reference build the input is expressed in.")


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

    variant: str = Field(description="ClinVar / rsID / HGVS / VCF / coords input.")
    intent: str = Field(default="correct", description="correct | knock_out | install | revert.")
    chemistries: list[str] | None = Field(
        default=None, description="Restrict to these chemistries (default: all eligible)."
    )
    populations: list[str] | None = Field(
        default=None, description="Ancestry labels to query and stratify off-target by."
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


class OffTargetRequest(BaseModel):
    """A request for a standalone population-aware off-target search."""

    model_config = ConfigDict(frozen=True)

    spacer: str = Field(description="The on-target spacer (5'->3').")
    pam: str = Field(default="NGG", description="PAM pattern (IUPAC).")
    mismatches: int = Field(default=4, ge=0, le=8, description="Max mismatches.")
    populations: list[str] | None = Field(
        default=None, description="Ancestry labels to stratify by."
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
