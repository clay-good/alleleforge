"""The AlleleForge FastAPI application.

A thin async HTTP layer over the library — **no business logic beyond
orchestration**. Each endpoint validates its request with a pydantic model,
calls the same library functions the Python API and CLI expose, and returns a
Phase 1 / Phase 11 schema-validated response. Long design runs can go through an
in-process async job queue with a status endpoint.

Two invariants from the specification:

* **All compute is local and user-controlled.** The app makes no outbound
  network call and transmits no sequence data externally; the served frontend
  states this prominently.
* **The reference genome is supplied by the deployment.** Pass a
  :class:`ReferenceGenome` to :func:`create_app`, or set
  ``ALLELEFORGE_REFERENCE_FASTA``. Endpoints that need it return ``503`` until
  one is configured, so the service starts cleanly without it.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from alleleforge._version import __version__
from alleleforge.config import Settings
from alleleforge.report.builder import RESEARCH_USE_DISCLAIMER, DesignReport, build_report
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.web.api.jobs import JobManager
from alleleforge.web.api.models import (
    BatchItemResult,
    BatchRequest,
    BatchResponse,
    BenchListResponse,
    BenchTaskRow,
    DataListResponse,
    DatasetRow,
    DesignRequest,
    HealthResponse,
    JobSubmitResponse,
    OffTargetRequest,
    OffTargetResponse,
    ResolveRequest,
    ResolveResponse,
)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class DesignFormat(StrEnum):
    """Renderings the design endpoint can return."""

    json = "json"
    html = "html"
    pdf = "pdf"


def _load_reference_from_env() -> Any | None:
    """Load a reference genome from ``ALLELEFORGE_REFERENCE_FASTA`` if set."""
    path = os.environ.get("ALLELEFORGE_REFERENCE_FASTA")
    if not path:
        return None
    from alleleforge.genome.reference import ReferenceGenome

    return ReferenceGenome(Path(path), build="hg38")


def _require_reference(request: Request) -> Any:
    """Return the configured reference genome, or raise ``503``."""
    reference = request.app.state.reference
    if reference is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "No reference genome configured. Pass reference= to create_app() "
                "or set ALLELEFORGE_REFERENCE_FASTA."
            ),
        )
    return reference


def _resolve(request: Request, variant: str, build: str) -> Any:
    """Resolve an input form, mapping a parse error to ``422``."""
    from alleleforge.variant.resolver import resolve as resolve_variant

    reference = request.app.state.reference
    try:
        return resolve_variant(variant, build=build, reference=reference)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _design_options(
    intent_str: str, chemistries_in: list[str] | None, weights_in: list[float] | None
) -> tuple[Any, Any, Any]:
    """Parse the shared design knobs (intent/chemistries/weights), or raise ``422``."""
    from alleleforge.design.ranking import DEFAULT_WEIGHTS, RankingWeights
    from alleleforge.types.edit import Chemistry, EditIntent

    try:
        intent = EditIntent(intent_str)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown intent {intent_str!r}") from exc
    chemistries = None
    if chemistries_in:
        try:
            chemistries = [Chemistry(c) for c in chemistries_in]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"unknown chemistry: {exc}") from exc
    weights = DEFAULT_WEIGHTS
    if weights_in is not None:
        e, c, s, p = weights_in
        weights = RankingWeights(efficiency=e, cleanliness=c, safety=s, simplicity=p)
    return intent, chemistries, weights


def _design_to_report(request: Request, req: DesignRequest) -> DesignReport:
    """Resolve + design + build a report for a design request (or ``4xx``)."""
    from alleleforge.design.designer import design as run_design

    reference = _require_reference(request)
    intent, chemistries, weights = _design_options(req.intent, req.chemistries, req.weights)

    resolved = _resolve(request, req.variant, "hg38")
    settings: Settings = request.app.state.settings
    menu = run_design(
        resolved,
        reference=reference,
        intent=intent,
        chemistries=chemistries,
        weights=weights,
        populations=req.populations,
        run_offtarget=req.run_offtarget,
        max_candidates_per_chemistry=req.max_per_chemistry,
        settings=settings,
    )
    return build_report(menu, variant=str(resolved.variant), intent=intent.value)


def create_app(
    *,
    reference: Any | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Build the AlleleForge FastAPI application.

    Args:
        reference: A pre-loaded :class:`ReferenceGenome`. If ``None``, one is
            loaded from ``ALLELEFORGE_REFERENCE_FASTA`` when that is set.
        settings: Settings to thread into provenance (default: a fresh instance).

    Returns:
        The configured :class:`FastAPI` app (frontend mounted at ``/``).
    """
    app = FastAPI(
        title="AlleleForge API",
        version=__version__,
        description=(
            "Variant-driven, uncertainty-aware CRISPR edit design. Research use "
            "only; all compute is local and no sequence data is transmitted "
            "externally."
        ),
    )
    app.state.reference = reference if reference is not None else _load_reference_from_env()
    app.state.settings = settings or Settings()
    app.state.jobs = JobManager()

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness and capability report."""
        return HealthResponse(
            status="ok",
            version=__version__,
            reference_loaded=app.state.reference is not None,
            disclaimer=RESEARCH_USE_DISCLAIMER,
        )

    @app.post("/api/resolve", response_model=ResolveResponse)
    async def resolve_endpoint(req: ResolveRequest, request: Request) -> ResolveResponse:
        """Normalize any input form to a canonical variant."""
        resolved = _resolve(request, req.variant, req.build)
        v = resolved.variant
        rec = resolved.reference_recommendation
        return ResolveResponse(
            variant=str(v),
            variant_class=v.variant_class.value,
            build=v.build,
            source=resolved.source,
            working_interval=str(resolved.working_interval),
            reference_recommendation=rec.recommended_build if rec is not None else None,
        )

    @app.post("/api/design", response_model=DesignReport)
    def design_endpoint(
        req: DesignRequest,
        request: Request,
        fmt: Annotated[DesignFormat, Query(alias="format")] = DesignFormat.json,
    ) -> DesignReport | Response:
        """Design a ranked, multi-chemistry menu (JSON, HTML, or PDF)."""
        report = _design_to_report(request, req)
        if fmt is DesignFormat.html:
            return HTMLResponse(render_html(report))
        if fmt is DesignFormat.pdf:
            return Response(render_pdf(report), media_type="application/pdf")
        return report

    @app.post("/api/jobs/design", response_model=JobSubmitResponse, status_code=202)
    async def submit_design_job(req: DesignRequest, request: Request) -> JobSubmitResponse:
        """Submit an async design job; poll ``/api/jobs/{id}`` for the result."""
        jobs: JobManager = request.app.state.jobs
        record = await jobs.submit(lambda: _design_to_report(request, req))
        return JobSubmitResponse(job_id=record.id, state=record.state)

    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str, request: Request) -> dict[str, Any]:
        """Return an async job's state, progress, and result (when done)."""
        jobs: JobManager = request.app.state.jobs
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown job {job_id!r}")
        result = record.result
        return {
            "job_id": record.id,
            "state": record.state.value,
            "progress": record.progress,
            "error": record.error,
            "result": result.model_dump(mode="json") if isinstance(result, DesignReport) else None,
        }

    @app.post("/api/batch", response_model=BatchResponse)
    def batch_endpoint(req: BatchRequest, request: Request) -> BatchResponse:
        """Design a whole cohort in one streaming run (per-item failures isolated)."""
        from alleleforge.design.cohort import design_many

        reference = _require_reference(request)
        intent, chemistries, weights = _design_options(req.intent, req.chemistries, req.weights)
        settings: Settings = request.app.state.settings
        report = design_many(
            req.variants,
            reference=reference,
            intent=intent,
            chemistries=chemistries,
            weights=weights,
            populations=req.populations,
            run_offtarget=req.run_offtarget,
            max_candidates_per_chemistry=req.max_per_chemistry,
            settings=settings,
        )
        return BatchResponse(
            total=report.total,
            succeeded=report.succeeded,
            failed=report.failed,
            items=tuple(
                BatchItemResult(
                    item_id=it.item_id, status=it.status, summary=it.summary, error=it.error
                )
                for it in report.items
            ),
            provenance=report.provenance,
            disclaimer=RESEARCH_USE_DISCLAIMER,
        )

    @app.post("/api/offtarget", response_model=OffTargetResponse)
    def offtarget_endpoint(req: OffTargetRequest, request: Request) -> OffTargetResponse:
        """Run a standalone population-aware off-target search for a spacer."""
        from alleleforge.offtarget.engine import search
        from alleleforge.types.guide import PAM

        reference = _require_reference(request)
        try:
            report = search(
                req.spacer,
                PAM(pattern=req.pam),
                reference=reference,
                mismatches=req.mismatches,
                dna_bulges=req.dna_bulges,
                rna_bulges=req.rna_bulges,
                cfd_threshold=req.cfd_threshold,
                mit_threshold=req.mit_threshold,
                maf=req.maf,
                populations=req.populations,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return OffTargetResponse.from_report(report)

    @app.get("/api/data", response_model=DataListResponse)
    async def data_list() -> DataListResponse:
        """List every registered dataset with its version and license."""
        from alleleforge.data.registry import DEFAULT_REGISTRY

        rows = tuple(
            DatasetRow(
                name=name,
                version=d.version,
                license=d.license,
                redistributable=d.redistributable,
            )
            for name in DEFAULT_REGISTRY.names
            for d in (DEFAULT_REGISTRY.get(name),)
        )
        return DataListResponse(datasets=rows)

    @app.get("/api/data/{name}")
    async def data_show(name: str) -> dict[str, Any]:
        """Show one dataset's full provenance descriptor."""
        from alleleforge.data.registry import DEFAULT_REGISTRY

        if name not in DEFAULT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"unknown dataset {name!r}")
        return DEFAULT_REGISTRY.get(name).model_dump(mode="json")

    @app.get("/api/bench", response_model=BenchListResponse)
    async def bench() -> BenchListResponse:
        """List the CRISPR-Bench tasks, their datasets, and primary metrics."""
        from alleleforge.benchmark.tasks import TASKS

        return BenchListResponse(
            tasks=tuple(
                BenchTaskRow(
                    task=t.name,
                    kind=t.kind.value,
                    chemistry=t.chemistry,
                    dataset=t.dataset,
                    primary_metric=t.primary_metric,
                    metrics=tuple(t.metrics),
                )
                for name in sorted(TASKS)
                for t in (TASKS[name],)
            )
        )

    if _FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

    return app


#: The ASGI application for ``uvicorn alleleforge.web.api.app:app`` deploys.
app = create_app()


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:  # pragma: no cover - runtime entry
    """Run the API with uvicorn (used by the console entry / docker image)."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
