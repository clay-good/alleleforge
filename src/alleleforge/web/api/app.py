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
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from alleleforge._version import __version__
from alleleforge.config import Settings
from alleleforge.report.builder import (
    DEFAULT_RENDER_CANDIDATES,
    RESEARCH_USE_DISCLAIMER,
    DesignReport,
    build_report,
)
from alleleforge.report.html import render_html
from alleleforge.report.pdf import render_pdf
from alleleforge.types.sequence import GenomicInterval
from alleleforge.web.api.jobs import JobCapacityError, JobManager
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
    JobStatusResponse,
    JobSubmitResponse,
    OffTargetRequest,
    OffTargetResponse,
    Region,
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
        try:
            weights = RankingWeights(efficiency=e, cleanliness=c, safety=s, simplicity=p)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"invalid ranking weights: {exc}") from exc
    return intent, chemistries, weights


def _regions(regions: list[Region] | None) -> list[GenomicInterval] | None:
    """Convert request regions to intervals, or ``None`` for "search everything".

    An empty list must stay ``None``: restricting a scan to no intervals would find
    nothing and report every guide spotless.
    """
    if not regions:
        return None
    try:
        return [region.to_interval() for region in regions]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
        offtarget_regions=_regions(req.offtarget_regions),
        cell_context=req.cell_context,
        run_offtarget=req.run_offtarget,
        max_candidates_per_chemistry=req.max_per_chemistry,
        allow_ng=req.allow_ng,
        allow_spry=req.allow_spry,
        settings=settings,
    )
    return build_report(menu, variant=str(resolved.variant), intent=intent.value)


#: Request paths that never require the API token (liveness must stay probeable).
_TOKEN_EXEMPT_PATHS = frozenset({"/api/health"})


#: Response headers applied to every response. The Content-Security-Policy is the
#: structural form of a promise the project already makes in prose — "the served
#: frontend loads no third-party scripts" — which was violated for as long as the
#: rendered report carried a `cdn.plot.ly` script tag, because nothing enforced it. A
#: `srcdoc` frame inherits its parent's policy, so this governs the embedded report as
#: well as the shell: a script tag reintroduced into the renderer is *blocked*, not
#: merely against policy.
#:
#: `style-src` allows inline styles because both the shell and the report carry a
#: `<style>` block; scripts have no such allowance, which is the half that matters.
_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": "; ".join(
        (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "font-src 'self'",
            "base-uri 'none'",
            "form-action 'none'",
            "object-src 'none'",
            "frame-ancestors 'none'",
        )
    ),
    # A JSON response mislabelled by a proxy must not be sniffed into script.
    "X-Content-Type-Options": "nosniff",
    # The report links out to jbrowse.org; a local deployment's URL is not their business.
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


#: How much of a rejected value the 422 shows back. Long enough to see a typo in a
#: variant string or a PAM, short enough that the response is not a mirror.
MAX_ECHOED_INPUT = 200


def _truncate_echoed(value: Any) -> Any:
    """Return ``value`` trimmed to something safe to put in an error body.

    FastAPI's default validation error includes the offending ``input`` verbatim, so a
    field bounded at 128 characters still answered a 100 KB value with a 100 KB error:
    the bounds constrain what is *accepted* and not what is *reflected*. Every string
    field on these models was already bounded and every one of them behaved this way,
    which is why this belongs on the handler rather than on any field.
    """
    if isinstance(value, str) and len(value) > MAX_ECHOED_INPUT:
        return f"{value[:MAX_ECHOED_INPUT]}… ({len(value)} characters, truncated)"
    if isinstance(value, list) and len(value) > 10:
        return [*value[:10], f"… ({len(value)} items, truncated)"]
    return value


def create_app(
    *,
    reference: Any | None = None,
    settings: Settings | None = None,
    api_token: str | None = None,
) -> FastAPI:
    """Build the AlleleForge FastAPI application.

    Args:
        reference: A pre-loaded :class:`ReferenceGenome`. If ``None``, one is
            loaded from ``ALLELEFORGE_REFERENCE_FASTA`` when that is set.
        settings: Settings to thread into provenance (default: ``Settings.load()``,
            resolving the user config file + env with the standard precedence).
        api_token: When set, every ``/api/*`` request (except ``/api/health``)
            SHALL carry a matching ``X-API-Token`` header or is rejected with 401.
            Defaults to ``ALLELEFORGE_API_TOKEN`` from the environment, and only
            leaves the API open when that is unset too — the localhost default.

    Returns:
        The configured :class:`FastAPI` app (frontend mounted at ``/``).
    """
    # Read the environment here, not only in `resolve_serve_token`. The deployment
    # guide and the Dockerfile both run `uvicorn alleleforge.web.api.app:app`, which
    # binds the module-level app directly and never calls `serve()` — so the
    # non-loopback guard did not run, and an operator who published the port and set
    # ALLELEFORGE_API_TOKEN believing it protected the service got a fully open API:
    # the variable was read by nothing on that path. Defaulting it here makes the
    # token work on every path, and leaves `resolve_serve_token` its distinct job of
    # *requiring* one before a public bind.
    if api_token is None:
        api_token = os.environ.get("ALLELEFORGE_API_TOKEN") or None
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
    # Resolve through Settings.load() so the web interface honors the user config file
    # (~/.config/alleleforge/config.toml) with the same precedence as the CLI and library
    # — the provenance-reproducibility spec requires the config file to apply to web runs,
    # not only the seed. A bare Settings() would read env vars but silently skip the file.
    app.state.settings = settings or Settings.load()
    app.state.jobs = JobManager()

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> Response:
        """Answer a rejected request without mirroring it back.

        Same body as FastAPI's default -- `loc`, `msg`, `type` per error, which is what
        a caller needs to find their mistake -- with the echoed `input` trimmed.
        """
        errors = []
        for error in exc.errors():
            trimmed = dict(error)
            if "input" in trimmed:
                trimmed["input"] = _truncate_echoed(trimmed["input"])
            trimmed.pop("ctx", None)  # may carry the value again, and the message has it
            errors.append(trimmed)
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    @app.middleware("http")
    async def _security_headers(request: Request, call_next: Any) -> Response:
        """Attach the fixed security headers to every response."""
        response: Response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    if api_token:

        @app.middleware("http")
        async def _require_api_token(request: Request, call_next: Any) -> Response:
            """Gate ``/api/*`` on a matching ``X-API-Token`` header."""
            path = request.url.path
            if path.startswith("/api/") and path not in _TOKEN_EXEMPT_PATHS:
                if request.headers.get("x-api-token") != api_token:
                    return JSONResponse({"detail": "missing or invalid API token"}, status_code=401)
            response: Response = await call_next(request)
            return response

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
        # 0 means "draw them all"; the JSON body is never capped either way.
        cap = (
            DEFAULT_RENDER_CANDIDATES
            if req.render_candidates is None
            else (req.render_candidates or None)
        )
        if fmt is DesignFormat.html:
            return HTMLResponse(render_html(report, max_candidates=cap))
        if fmt is DesignFormat.pdf:
            return Response(render_pdf(report, max_candidates=cap), media_type="application/pdf")
        return report

    @app.post("/api/jobs/design", response_model=JobSubmitResponse, status_code=202)
    async def submit_design_job(req: DesignRequest, request: Request) -> JobSubmitResponse:
        """Submit an async design job; poll ``/api/jobs/{id}`` for the result."""
        jobs: JobManager = request.app.state.jobs
        try:
            record = await jobs.submit(lambda: _design_to_report(request, req))
        except JobCapacityError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        return JobSubmitResponse(job_id=record.id, state=record.state)

    @app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
    async def job_status(job_id: str, request: Request) -> JobStatusResponse:
        """Return an async job's state, progress, and result (when done)."""
        jobs: JobManager = request.app.state.jobs
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown job {job_id!r}")
        result = record.result
        return JobStatusResponse(
            job_id=record.id,
            state=record.state.value,
            progress=record.progress,
            error=record.error,
            result=result.model_dump(mode="json") if isinstance(result, DesignReport) else None,
        )

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
            offtarget_regions=_regions(req.offtarget_regions),
            cell_context=req.cell_context,
            allow_ng=req.allow_ng,
            allow_spry=req.allow_spry,
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
        from alleleforge.offtarget.scoring import scorer_for
        from alleleforge.types.guide import PAM

        reference = _require_reference(request)
        # `on_target` is validated as a GenomicInterval by the request model, so a
        # malformed locus is already a 422 — never a silently skipped exclusion.
        locus = req.on_target
        try:
            # An unknown name raises ValueError listing the known scorers, which the
            # handler already turns into a 422. The alternative — the model ignoring
            # the field — served a CFD result to a client that asked for Cas12a.
            scorer = scorer_for(req.scorer) if req.scorer else None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            report = search(
                req.spacer,
                PAM(pattern=req.pam),
                reference=reference,
                scorer=scorer,
                on_target=locus,
                regions=_regions(req.offtarget_regions),
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
        return OffTargetResponse.from_report(report, on_target_excluded=locus is not None)

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

#: Hosts treated as loopback: an open (token-free) API is safe only on these.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", ""})


def _is_loopback(host: str) -> bool:
    """Return ``True`` if ``host`` is a loopback address the API may serve openly."""
    return host in _LOOPBACK_HOSTS


def resolve_serve_token(host: str, api_token: str | None) -> str | None:
    """Return the API token to enforce, refusing an unauthenticated public bind.

    Binding to a non-loopback host exposes the service, so a token is mandatory
    there; localhost stays open for the unchanged local dev experience. The token
    comes from ``api_token`` or the ``ALLELEFORGE_API_TOKEN`` environment variable.

    Raises:
        ValueError: If ``host`` is non-loopback and no token is available.
    """
    token = api_token if api_token is not None else os.environ.get("ALLELEFORGE_API_TOKEN")
    if not _is_loopback(host) and not token:
        raise ValueError(
            f"refusing to bind the API to non-loopback host {host!r} without an API token; "
            "set ALLELEFORGE_API_TOKEN (or pass api_token), or bind to 127.0.0.1"
        )
    return token


def serve(
    host: str = "127.0.0.1", port: int = 8000, *, api_token: str | None = None
) -> None:  # pragma: no cover - runtime entry
    """Run the API with uvicorn (used by the console entry / docker image).

    A non-loopback bind requires an API token (see :func:`resolve_serve_token`).
    """
    import uvicorn

    token = resolve_serve_token(host, api_token)
    application = create_app(api_token=token) if token else app
    uvicorn.run(application, host=host, port=port)
