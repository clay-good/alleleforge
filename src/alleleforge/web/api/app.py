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

import importlib
import os
import tempfile
from collections.abc import Iterable
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
from alleleforge.design.cohort_summary import cohort_rows, cohort_to_tsv
from alleleforge.errors import ChecksumError, ConsentError, MissingDependencyError
from alleleforge.model_zoo.registry import LicenseError
from alleleforge.report.builder import (
    DEFAULT_RENDER_CANDIDATES,
    RESEARCH_USE_CORE,
    RESEARCH_USE_DISCLAIMER,
    DesignReport,
    build_report,
)
from alleleforge.report.export import report_to_parquet, report_to_tsv
from alleleforge.report.html import render_html
from alleleforge.report.oligos import scheme_by_name
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


class BatchFormat(StrEnum):
    """Renderings the cohort endpoint can return.

    No `html`/`pdf`: a cohort produces per-item summaries, not one rendered document —
    the same reason `aforge batch` has no `--format`. What it does produce is the flat
    per-patient table a pipeline reads, which was CLI-only until the summary moved into
    the library.

    No `parquet` yet, deliberately: the design endpoint offers one because
    `report_to_parquet` exists, and there is no cohort equivalent. Adding it means a new
    writer plus the guard that its columns match the TSV's in order — two tables of the
    same numbers disagreeing about their columns is a defect this project has already had
    once — which is a feature, not the reachability fix this enum is part of.
    """

    json = "json"
    tsv = "tsv"


class DesignFormat(StrEnum):
    """Renderings the design endpoint can return.

    The same set `aforge design --format` offers. The two flat tables are the surface a
    *pipeline* reads, and they were CLI-only (Parquet, Python-only) — so the one
    audience that cannot open an HTML page was the one the HTTP shell had nothing for.
    """

    json = "json"
    html = "html"
    pdf = "pdf"
    tsv = "tsv"
    parquet = "parquet"


def _report_parquet_bytes(report: DesignReport) -> bytes:
    """Return the Parquet export as bytes.

    The writer takes a path because Parquet's file-level key/value metadata — where
    the notes the TSV carries as `#` comment lines live — belongs to the file. Over
    HTTP there is no path, so one is borrowed and removed; the alternative is a body
    without the disclaimer, provenance and coordinate convention, which is the whole
    reason those notes were put there.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            return Path(report_to_parquet(report, Path(tmp) / "design.parquet")).read_bytes()
    except MissingDependencyError as exc:
        # 501, not 500: the deployment did not install the optional writer. The
        # message already names the extra to install, and a client can act on it.
        raise HTTPException(status_code=501, detail=str(exc)) from exc


#: Why the configured reference could not be opened, for `_require_reference` to
#: relay. `create_app()` runs at module scope, so raising here takes the whole
#: process down at import — `uvicorn alleleforge.web.api.app:app`, the command in
#: the deployment guide and the Dockerfile, exits with a traceback and the container
#: never starts. A service that answers "no genome, here is why" is strictly better
#: than one that will not boot, and the documented no-reference path already exists.
_REFERENCE_LOAD_ERROR: str | None = None


def _load_reference_from_env() -> Any | None:
    """Load a reference genome from ``ALLELEFORGE_REFERENCE_FASTA`` if set."""
    global _REFERENCE_LOAD_ERROR
    _REFERENCE_LOAD_ERROR = None
    path = os.environ.get("ALLELEFORGE_REFERENCE_FASTA")
    if not path:
        return None
    try:
        from alleleforge.genome.reference import ReferenceGenome

        return ReferenceGenome(Path(path), build="hg38")
    except (OSError, ImportError) as exc:
        # `ImportError` as well as `OSError`: "the operator's environment is not what
        # the app needs" is one situation with two exception types. A missing `.fai`
        # on a read-only mount raises the first; a `pip install "alleleforge[web]"`
        # without a FASTA reader raised the second, and only the first was caught —
        # so that install died at import instead of starting and saying why.
        _REFERENCE_LOAD_ERROR = str(exc)
        return None


#: Set when a configured population source could not be read, so `/api/health` can say
#: so rather than reporting the same `false` as "none configured".
_GNOMAD_LOAD_ERROR: str | None = None


def _load_gnomad_from_env() -> Any | None:
    """Load a population allele-frequency source from ``ALLELEFORGE_GNOMAD_TSV`` if set.

    Population-aware off-target nomination is the capability this project exists for, and
    over HTTP it was unreachable: the request model accepts `populations` but no source,
    `create_app` took no source, and no environment variable supplied one — so every API
    scan was reference-only and every ancestry breakdown came back empty. The source is
    operator-configured, exactly like the reference genome, because a client-supplied path
    would be an arbitrary file read on the server.
    """
    global _GNOMAD_LOAD_ERROR
    _GNOMAD_LOAD_ERROR = None
    path = os.environ.get("ALLELEFORGE_GNOMAD_TSV")
    if not path:
        return None
    try:
        from alleleforge.data.gnomad import GnomadDB

        return GnomadDB.from_sites_tsv(Path(path))
    except (OSError, ValueError, ImportError) as exc:
        _GNOMAD_LOAD_ERROR = str(exc)
        return None


#: As `_GNOMAD_LOAD_ERROR`, for the haplotype panel.
_HAPLOTYPES_LOAD_ERROR: str | None = None


def _load_haplotypes_from_env() -> Any:
    """Load a phased-haplotype panel from ``ALLELEFORGE_HAPLOTYPES`` if set.

    The sibling of the population source. The CLI names both in one breath — "no
    population alleles were searched ... pass --gnomad or --haplotypes" — and wiring only
    the first into the web shell would leave exactly the asymmetry that produced these
    findings: one ancestry source reachable over HTTP and the other not.

    Returns the *panel*, not its haplotypes: the panel carries the provenance descriptor,
    and flattening it strips the record of which data made the run haplotype-aware.
    """
    global _HAPLOTYPES_LOAD_ERROR
    _HAPLOTYPES_LOAD_ERROR = None
    path = os.environ.get("ALLELEFORGE_HAPLOTYPES")
    if not path:
        return ()
    try:
        from alleleforge.data.haplotypes import HaplotypePanel

        return HaplotypePanel.from_tsv(Path(path), source=path)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        _HAPLOTYPES_LOAD_ERROR = str(exc)
        return ()


#: As `_GNOMAD_LOAD_ERROR`, for the accessibility tracks.
_ENCODE_TRACKS_LOAD_ERROR: str | None = None


def _load_encode_tracks_from_env() -> Any | None:
    """Load accessibility tracks from ``ALLELEFORGE_ENCODE_TRACKS`` if set.

    The file is operator-configured like the other data sources; *which* track to read is
    per-request, because one bedGraph can hold several cell types and the choice belongs
    to the caller. Without the file the chromatin adjustment is unreachable over HTTP.
    """
    global _ENCODE_TRACKS_LOAD_ERROR
    _ENCODE_TRACKS_LOAD_ERROR = None
    path = os.environ.get("ALLELEFORGE_ENCODE_TRACKS")
    if not path:
        return None
    try:
        from alleleforge.data.annotations import EncodeTracks

        return EncodeTracks.from_bedgraph(Path(path))
    except (OSError, ValueError, ImportError) as exc:
        _ENCODE_TRACKS_LOAD_ERROR = str(exc)
        return None


#: As `_GNOMAD_LOAD_ERROR`, for the persistent genome index.
_GENOME_INDEX_LOAD_ERROR: str | None = None


def _load_reuse_from_env(reference: Any | None) -> tuple[Any | None, Any | None]:
    """Build the cross-run scan cache and genome index this deployment opted into.

    Reuse is the operator's call rather than a request field, and for once that is not
    about safety: the store and the index live on the server's disk, so a client asking
    for either would be spending the operator's resources on its own request. The
    operator therefore needs a way to say yes — ``ALLELEFORGE_OFFTARGET_CACHE`` and
    ``ALLELEFORGE_GENOME_INDEX``.

    The index is built at startup rather than on the first request. It is
    content-addressed on disk, so a restart with a warm cache memory-maps it in
    moments; a cold one pays the whole build, and paying it while the service is
    starting is better than stalling whichever request happens to arrive first.
    """
    global _GENOME_INDEX_LOAD_ERROR
    _GENOME_INDEX_LOAD_ERROR = None
    cache = None
    if os.environ.get("ALLELEFORGE_OFFTARGET_CACHE"):
        from alleleforge.offtarget.cache import OffTargetCache

        cache = OffTargetCache()
    index = None
    if os.environ.get("ALLELEFORGE_GENOME_INDEX") and reference is not None:
        try:
            from alleleforge.genome.index import GenomeIndex

            index = GenomeIndex.build_genome(reference)
        except (OSError, ValueError, ImportError) as exc:
            _GENOME_INDEX_LOAD_ERROR = str(exc)
    return cache, index


def _reuse_names(state: Any) -> tuple[str, ...]:
    """Return the reuse mechanisms this deployment has enabled, by name.

    Named rather than a pair of booleans, for the reason `chromatin_tracks` is a list:
    a client comparing two deployments' response times has no other way to learn which
    of them is serving stored scans.
    """
    enabled = []
    if state.offtarget_cache is not None:
        enabled.append("offtarget-cache")
    if state.genome_index is not None:
        enabled.append("genome-index")
    return tuple(enabled)


def _require_reference(request: Request) -> Any:
    """Return the configured reference genome, or raise ``503``."""
    reference = request.app.state.reference
    if reference is None:
        raise HTTPException(
            status_code=503,
            detail=_REFERENCE_LOAD_ERROR
            or (
                "No reference genome configured. Pass reference= to create_app() "
                "or set ALLELEFORGE_REFERENCE_FASTA."
            ),
        )
    return reference


def _effect(request: Request, annotate: bool) -> Any | None:
    """Return the configured effect predictor when a request asked for one, or 422.

    Refused rather than ignored, for the reason `chromatin_track` is: a client that
    asked for the consequence and got a report without one cannot tell "this deployment
    does not offer it" from "VEP looked and found nothing notable".
    """
    if not annotate:
        return None
    predictor = request.app.state.effect
    if predictor is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "annotate_consequence was requested but this deployment has not enabled "
                "consequence annotation (ALLELEFORGE_VEP), so no variant is sent to a "
                "VEP server from here"
            ),
        )
    return predictor


def _resolve(request: Request, variant: str, build: str, *, annotate: bool = False) -> Any:
    """Resolve an input form, mapping a parse error to ``422``."""
    from alleleforge.variant.resolver import resolve as resolve_variant

    reference = request.app.state.reference
    effect = _effect(request, annotate)
    try:
        return resolve_variant(variant, build=build, reference=reference, effect=effect)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _load_effect_from_env() -> Any | None:
    """Build a VEP effect predictor when ``ALLELEFORGE_VEP`` is set, else ``None``.

    The third operator-configured capability, and the only one that sends data *out*.
    The reference, the population source and the haplotype panel are operator-configured
    because a client-supplied path would be a server-side file read; this one is
    operator-configured because enabling it means this deployment will disclose its
    clients' variants — chromosome, position, both alleles, possibly from a patient
    VCF — to a third-party public server. A client can then ask per request, but cannot
    turn the capability on.

    Set the variable to ``1`` for Ensembl's public server, or to a base URL to point at
    a private VEP instance (which is how a deployment gets the annotation without the
    disclosure).
    """
    value = os.environ.get("ALLELEFORGE_VEP")
    if not value:
        return None
    from alleleforge.variant.effect import VepRestPredictor

    server = value if value.startswith("http") else "https://rest.ensembl.org"
    return VepRestPredictor(server=server, consent=True)


#: The trained-model opt-ins, keyed by the request field that asks for one, mapping to
#: the `design()` keyword it fills and the adapter that fills it. The request field names
#: match `aforge design`'s flags exactly (`--trained-efficiency`, ...) so the two shells
#: do not give one capability two vocabularies.
_TRAINED_MODELS: dict[str, tuple[str, str, str]] = {
    "trained_efficiency": (
        "cas9_efficiency_scorer",
        "alleleforge.scoring.cas9_efficiency",
        "TrainedRuleSet3Scorer",
    ),
    "trained_outcome": (
        "cas9_outcome_predictor",
        "alleleforge.scoring.cas9_outcome",
        "LindelAdapter",
    ),
    "trained_base_outcome": (
        "base_outcome_predictor",
        "alleleforge.scoring.base_outcome",
        "BeDictAdapter",
    ),
    "trained_prime": (
        "prime_efficiency_scorer",
        "alleleforge.scoring.prime_efficiency",
        "DeepPrimeAdapter",
    ),
}


def _load_trained_models_from_env() -> frozenset[str]:
    """Return the trained models ``ALLELEFORGE_TRAINED_MODELS`` permits.

    The operator's half of the same split `ALLELEFORGE_VEP` uses, for the same kind of
    reason: each trained model is a consent-gated weight download or an external
    checkout that lives on the *operator's* disk, so only they can turn one on, while
    which model scores a given run is the client's choice. A client that could not ask
    got the transparent baseline every time, with no way to know a trained model existed.

    The value is a comma-separated list of request-field names, or ``1``/``all`` for
    every one. An unrecognized name raises at startup rather than silently enabling
    nothing: a typo that leaves the deployment quietly baseline-only is exactly the
    failure this gate exists to make visible.
    """
    value = os.environ.get("ALLELEFORGE_TRAINED_MODELS", "").strip()
    if not value:
        return frozenset()
    if value in {"1", "all", "true"}:
        return frozenset(_TRAINED_MODELS)
    names = {n.strip() for n in value.split(",") if n.strip()}
    unknown = sorted(names - set(_TRAINED_MODELS))
    if unknown:
        raise ValueError(
            f"ALLELEFORGE_TRAINED_MODELS names unknown model(s): {unknown}; "
            f"choose from {sorted(_TRAINED_MODELS)}, or '1' for all of them"
        )
    return frozenset(names)


def _trained_scorers(request: Request, req: Any) -> dict[str, Any]:
    """Return the `design()` scorer arguments a request asked for, or ``422``/``503``.

    Refused rather than ignored, for the reason `annotate_consequence` is: a client that
    asked for the trained model and got a baseline-scored menu cannot tell "this
    deployment does not offer it" from "the trained model returned this". Every number
    on the menu would differ, and nothing on the artifact would say which model made it.

    Only *construction* failures are mapped here. An adapter that constructs and then
    cannot load its weights degrades exactly as it does on the command line — the
    chemistry is skipped with the reason in the menu rationale — because the two shells
    calling one `design()` must not invent two failure modes for one condition.
    """
    enabled: frozenset[str] = request.app.state.trained_models
    out: dict[str, Any] = {}
    for field, (kwarg, module, cls) in _TRAINED_MODELS.items():
        if not getattr(req, field, False):
            continue
        if field not in enabled:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{field} was requested but this deployment has not enabled it "
                    f"(ALLELEFORGE_TRAINED_MODELS). Enabled here: "
                    f"{sorted(enabled) or 'none'}. GET /api/health lists them under "
                    "`trained_models`; without one the baseline scorer is used, and the "
                    "request is refused rather than answered by a different model."
                ),
            )
        try:
            adapter = getattr(importlib.import_module(module), cls)
            # The operator consented by enabling it; the client chose it per request.
            out[kwarg] = adapter(consent=True)
        except (MissingDependencyError, ConsentError, ChecksumError, LicenseError) as exc:
            # Enabled by the operator but not actually installable here. 503, not 422:
            # the client's request is well-formed and the deployment is the problem.
            raise HTTPException(
                status_code=503,
                detail=f"{field} is enabled on this deployment but unavailable: {exc}",
            ) from exc
    return out


def _chromatin_tracks(request: Request, track: str | None) -> Any | None:
    """Return the configured tracks when a valid track name was asked for, or raise 422.

    The CLI checks the name where it is supplied, because an unknown one used to raise
    inside the chemistry, be caught as a decline reason, and produce an empty menu with
    exit 0. The same mistake over HTTP deserves the same answer, and a `422` a client can
    act on has to carry the vocabulary — there is no `--help` on the other end.
    """
    if track is None:
        return None
    tracks = request.app.state.encode_tracks
    if tracks is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "chromatin_track was requested but this deployment has no accessibility "
                "tracks configured, so the adjustment cannot run"
            ),
        )
    available = tuple(tracks.tracks)
    if track not in available:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unknown chromatin_track {track!r}; this deployment has: "
                f"{', '.join(available) or 'none'}"
            ),
        )
    return tracks


def _design_options(
    intent_str: str, chemistries_in: list[str] | None, weights_in: list[float] | None
) -> tuple[Any, Any, Any]:
    """Parse the shared design knobs (intent/chemistries/weights), or raise ``422``."""
    from alleleforge.design.ranking import DEFAULT_WEIGHTS, OBJECTIVES, RankingWeights
    from alleleforge.types.edit import Chemistry, EditIntent

    # A `422` a client cannot act on is worse than the CLI's equivalent: there is no
    # `--help` on the other end of an HTTP call, so the accepted vocabulary has to
    # travel with the refusal.
    def _known(values: Iterable[object]) -> str:
        return ", ".join(sorted(str(getattr(v, "value", v)) for v in values))

    try:
        intent = EditIntent(intent_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"unknown intent {intent_str!r}; choose one of: {_known(EditIntent)}",
        ) from exc
    chemistries = None
    if chemistries_in:
        known = {c.value for c in Chemistry}
        unknown = sorted(c for c in chemistries_in if c not in known)
        if unknown:
            # Not pydantic's "'PRIME' is not a valid Chemistry", which names the class.
            raise HTTPException(
                status_code=422,
                detail=(
                    f"unknown chemistry: {', '.join(repr(c) for c in unknown)}; "
                    f"choose one of: {_known(Chemistry)}"
                ),
            )
        chemistries = [Chemistry(c) for c in chemistries_in]
    weights = DEFAULT_WEIGHTS
    if weights_in is not None:
        try:
            weights = RankingWeights(**dict(zip(OBJECTIVES, weights_in, strict=True)))
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

    resolved = _resolve(request, req.variant, "hg38", annotate=req.annotate_consequence)
    settings: Settings = request.app.state.settings
    tracks = _chromatin_tracks(request, req.chromatin_track)
    menu = run_design(
        resolved,
        reference=reference,
        intent=intent,
        chemistries=chemistries,
        weights=weights,
        populations=req.populations,
        # The operator-configured population source, so `populations` on a request means
        # something over HTTP. Without it the scan is reference-only whatever ancestry
        # labels were asked for, and the report says so.
        gnomad=request.app.state.gnomad,
        haplotypes=request.app.state.haplotypes,
        encode_tracks=tracks,
        chromatin_track=req.chromatin_track,
        offtarget_regions=_regions(req.offtarget_regions),
        offtarget_cache=request.app.state.offtarget_cache,
        genome_index=request.app.state.genome_index,
        cell_context=req.cell_context,
        run_offtarget=req.run_offtarget,
        max_candidates_per_chemistry=req.max_per_chemistry,
        allow_ng=req.allow_ng,
        allow_spry=req.allow_spry,
        settings=settings,
        **_trained_scorers(request, req),
    )
    scheme = scheme_by_name(req.vector_scheme) if req.vector_scheme else None
    return build_report(menu, variant=str(resolved.variant), intent=intent.value, scheme=scheme)


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
    gnomad: Any | None = None,
    haplotypes: Any | None = None,
    effect: Any | None = None,
    offtarget_cache: Any | None = None,
    genome_index: Any | None = None,
    encode_tracks: Any | None = None,
    trained_models: Iterable[str] | None = None,
    settings: Settings | None = None,
    api_token: str | None = None,
) -> FastAPI:
    """Build the AlleleForge FastAPI application.

    Args:
        reference: A pre-loaded :class:`ReferenceGenome`. If ``None``, one is
            loaded from ``ALLELEFORGE_REFERENCE_FASTA`` when that is set.
        gnomad: A pre-loaded population allele-frequency source. If ``None``, one is
            loaded from ``ALLELEFORGE_GNOMAD_TSV`` when that is set. Without it every
            scan this API runs is reference-only, whatever `populations` a request asks
            for — the capability was unreachable over HTTP entirely.
        offtarget_cache: A cross-run store of reference-only off-target scans. If
            ``None``, one is opened when ``ALLELEFORGE_OFFTARGET_CACHE`` is set.
        genome_index: A persistent memory-mapped FM-index over the reference. If
            ``None``, one is built at startup when ``ALLELEFORGE_GENOME_INDEX`` is set.
        trained_models: Which trained-model opt-ins this deployment permits, named by
            the request field that asks for one (``"trained_efficiency"``, ...). If
            ``None``, read from ``ALLELEFORGE_TRAINED_MODELS``. Each is a consent-gated
            download or an external checkout on the operator's disk, so the operator
            enables and the client chooses per request — without this every menu the API
            returned was scored by the transparent baseline, with no way to ask.
        effect: A pre-loaded variant-consequence predictor. If ``None``, one is built
            from ``ALLELEFORGE_VEP`` when that is set. Without it a request asking for
            `annotate_consequence` is refused rather than answered without one.
        haplotypes: A pre-loaded phased-haplotype panel. If ``None``, one is loaded from
            ``ALLELEFORGE_HAPLOTYPES`` when that is set. Without it the haplotype-aware
            pass — the one that finds a site existing only on a co-inherited combination
            of alleles — never runs for an API caller.
        encode_tracks: Pre-loaded accessibility tracks for the ePRIDICT-style
            open-chromatin adjustment. If ``None``, loaded from
            ``ALLELEFORGE_ENCODE_TRACKS`` when set. Which track a run reads is chosen
            per request, since one bedGraph can hold several cell types.
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
    # Resolved before the app is built: it decides what the API description says about
    # data leaving this machine.
    _vep_predictor = effect if effect is not None else _load_effect_from_env()
    app = FastAPI(
        title="AlleleForge API",
        version=__version__,
        # "No sequence data is transmitted externally" stops being true the moment an
        # operator enables consequence annotation, and this string is what an OpenAPI
        # client reads to decide whether it may send patient variants here. It states
        # what this deployment does, not what the default deployment does.
        description=(
            "Variant-driven, uncertainty-aware CRISPR edit design. Research use "
            "only; all compute is local and no sequence data is transmitted "
            "externally."
            if _vep_predictor is None
            else "Variant-driven, uncertainty-aware CRISPR edit design. Research use "
            "only. Compute is local, but this deployment has consequence annotation "
            "enabled: a request setting `annotate_consequence` sends that variant to "
            "an external VEP server."
        ),
    )
    app.state.reference = reference if reference is not None else _load_reference_from_env()
    app.state.gnomad = gnomad if gnomad is not None else _load_gnomad_from_env()
    app.state.haplotypes = haplotypes if haplotypes is not None else _load_haplotypes_from_env()
    app.state.encode_tracks = (
        encode_tracks if encode_tracks is not None else _load_encode_tracks_from_env()
    )
    app.state.effect = _vep_predictor
    app.state.trained_models = (
        frozenset(trained_models) if trained_models is not None else _load_trained_models_from_env()
    )
    unknown = sorted(app.state.trained_models - set(_TRAINED_MODELS))
    if unknown:
        raise ValueError(
            f"create_app(trained_models=...) names unknown model(s): {unknown}; "
            f"choose from {sorted(_TRAINED_MODELS)}"
        )
    _env_cache, _env_index = _load_reuse_from_env(app.state.reference)
    app.state.offtarget_cache = offtarget_cache if offtarget_cache is not None else _env_cache
    app.state.genome_index = genome_index if genome_index is not None else _env_index
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
            gnomad_loaded=app.state.gnomad is not None,
            haplotypes_loaded=bool(app.state.haplotypes),
            vep_enabled=app.state.effect is not None,
            trained_models=tuple(sorted(app.state.trained_models)),
            scan_reuse=_reuse_names(app.state),
            # The names, not a flag: a client picks one per request and has no other way
            # to discover what this deployment's bedGraph contains.
            # `_*_LOAD_ERROR` was recorded for each optional source and read by
            # nothing, so a path that could not be opened reported exactly what an
            # unconfigured deployment reports. The reference's error already reached a
            # caller through the 503; the other two reached no one.
            source_errors={
                name: error
                for name, error in (
                    ("reference", _REFERENCE_LOAD_ERROR),
                    ("genome_index", _GENOME_INDEX_LOAD_ERROR),
                    ("gnomad", _GNOMAD_LOAD_ERROR),
                    ("haplotypes", _HAPLOTYPES_LOAD_ERROR),
                    ("encode_tracks", _ENCODE_TRACKS_LOAD_ERROR),
                )
                if error
            },
            chromatin_tracks=(
                tuple(app.state.encode_tracks.tracks) if app.state.encode_tracks is not None else ()
            ),
            # The core sentence only. A liveness probe has no candidates below it and
            # nominates no off-target site, and `RESEARCH_USE_CORE` exists because "a
            # caveat that does not describe the thing it is attached to is noise".
            disclaimer=RESEARCH_USE_CORE,
        )

    @app.post("/api/resolve", response_model=ResolveResponse)
    async def resolve_endpoint(req: ResolveRequest, request: Request) -> ResolveResponse:
        """Normalize any input form to a canonical variant."""
        from alleleforge.design.designer import _reference_snapshot

        resolved = _resolve(request, req.variant, req.build, annotate=req.annotate_consequence)
        v = resolved.variant
        effect = resolved.effect
        rec = resolved.reference_recommendation
        return ResolveResponse(
            variant=str(v),
            variant_class=v.variant_class.value,
            changes_the_sequence=v.ref != v.alt,
            build=v.build,
            source=resolved.source,
            working_interval=str(resolved.working_interval),
            reference_checked=request.app.state.reference is not None,
            reference=(
                _reference_snapshot(request.app.state.reference)
                if request.app.state.reference is not None
                else None
            ),
            reference_recommendation=rec.recommended_build if rec is not None else None,
            reference_recommendation_reason=rec.reason if rec is not None else None,
            consequence_checked=req.annotate_consequence,
            consequence=effect.consequence.value if effect else None,
            impact=effect.impact.name if effect else None,
            gene=effect.gene if effect else None,
        )

    @app.post("/api/design", response_model=DesignReport)
    def design_endpoint(
        req: DesignRequest,
        request: Request,
        fmt: Annotated[DesignFormat, Query(alias="format")] = DesignFormat.json,
    ) -> DesignReport | Response:
        """Design a ranked, multi-chemistry menu (JSON, HTML, PDF, TSV, or Parquet)."""
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
        if fmt is DesignFormat.tsv:
            # `text/tab-separated-values`, charset declared: the `#` note block carries
            # a reference-genome description that may hold a non-ASCII gene name.
            return Response(
                report_to_tsv(report), media_type="text/tab-separated-values; charset=utf-8"
            )
        if fmt is DesignFormat.parquet:
            return Response(
                _report_parquet_bytes(report), media_type="application/vnd.apache.parquet"
            )
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
    def batch_endpoint(
        req: BatchRequest,
        request: Request,
        fmt: Annotated[BatchFormat, Query(alias="format")] = BatchFormat.json,
    ) -> BatchResponse | Response:
        """Design a whole cohort in one run (JSON, TSV, or Parquet; failures isolated)."""
        from alleleforge.design.cohort import design_many

        reference = _require_reference(request)
        intent, chemistries, weights = _design_options(req.intent, req.chemistries, req.weights)
        settings: Settings = request.app.state.settings
        # The same configured sources the single-variant endpoint uses. Wiring them there
        # and not here would leave a cohort run reference-only while an identical
        # one-variant request was population-aware — the difference invisible in both
        # results except to a reader who compared the search descriptions.
        report = design_many(
            req.variants,
            reference=reference,
            intent=intent,
            chemistries=chemistries,
            weights=weights,
            populations=req.populations,
            gnomad=request.app.state.gnomad,
            haplotypes=request.app.state.haplotypes,
            encode_tracks=_chromatin_tracks(request, req.chromatin_track),
            chromatin_track=req.chromatin_track,
            effect=_effect(request, req.annotate_consequence),
            run_offtarget=req.run_offtarget,
            max_candidates_per_chemistry=req.max_per_chemistry,
            offtarget_regions=_regions(req.offtarget_regions),
            offtarget_cache=request.app.state.offtarget_cache,
            genome_index=request.app.state.genome_index,
            cell_context=req.cell_context,
            allow_ng=req.allow_ng,
            allow_spry=req.allow_spry,
            settings=settings,
            **_trained_scorers(request, req),
        )
        if fmt is not BatchFormat.json:
            # The same table `aforge batch --summary-tsv` writes, from the same library
            # function, so the two shells cannot describe one run differently.
            return Response(
                cohort_to_tsv(cohort_rows(report), report.provenance),
                media_type="text/tab-separated-values; charset=utf-8",
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
                gnomad=request.app.state.gnomad,
                haplotypes=request.app.state.haplotypes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        from alleleforge.design.designer import _reference_snapshot

        return OffTargetResponse.from_report(
            report,
            on_target_excluded=locus is not None,
            reference=_reference_snapshot(reference),
        )

    @app.get("/api/data", response_model=DataListResponse)
    async def data_list() -> DataListResponse:
        """List every registered dataset with its version and license."""
        from alleleforge.data.registry import DEFAULT_REGISTRY, dataset_presence, dataset_status

        rows = tuple(
            DatasetRow(
                name=name,
                version=d.version,
                license=d.license,
                **status,
                presence=dataset_presence(status),
            )
            for name in DEFAULT_REGISTRY.names
            for d in (DEFAULT_REGISTRY.get(name),)
            for status in (dataset_status(name, d),)
        )
        return DataListResponse(datasets=rows)

    @app.get("/api/data/{name}")
    async def data_show(name: str) -> dict[str, Any]:
        """Show one dataset's provenance descriptor and whether a run can use it."""
        from alleleforge.data.registry import (
            DEFAULT_REGISTRY,
            dataset_presence,
            dataset_status,
        )

        if name not in DEFAULT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"unknown dataset {name!r}")
        descriptor = DEFAULT_REGISTRY.get(name)
        # The descriptor says what the dataset *is*. Whether this deployment can use it
        # is the question a client asks the endpoint, and it was answerable only by
        # knowing that `redistributable` is a permission and that a null `sha256` means
        # the registry will not even fetch it.
        status = dataset_status(name, descriptor)
        return {
            **descriptor.model_dump(mode="json"),
            **status,
            "presence": dataset_presence(status),
        }

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
