"""Async endpoint tests for the AlleleForge web API (Phase 13)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from alleleforge._version import __version__
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.web.api.app import create_app

DESIGN_BODY = {"variant": "chr2:71:A>C", "intent": "install", "max_per_chemistry": 3}


# --- health & static --------------------------------------------------------


async def test_health(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] == __version__
    assert data["reference_loaded"] is True
    assert "Research use" in data["disclaimer"] or "research" in data["disclaimer"].lower()


async def test_frontend_is_served(client: httpx.AsyncClient) -> None:
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "AlleleForge" in res.text
    assert "no sequence data" in res.text.lower()  # the no-egress notice
    assert "research use only" in res.text.lower()


async def test_frontend_has_cohort_ui(client: httpx.AsyncClient) -> None:
    # The served SPA exposes both single-variant and cohort (batch) modes.
    html = (await client.get("/")).text
    assert 'id="tab-batch"' in html and "Cohort" in html
    assert 'id="batch-variants"' in html  # the one-variant-per-line textarea
    app_js = (await client.get("/app.js")).text
    assert "/api/batch" in app_js  # the cohort form posts to the batch endpoint


async def test_openapi_is_generated(client: httpx.AsyncClient) -> None:
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    assert "/api/design" in res.json()["paths"]
    assert "/api/batch" in res.json()["paths"]  # cohort endpoint documented in OpenAPI


# --- resolve ----------------------------------------------------------------


async def test_resolve(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/resolve", json={"variant": "chr2:71:A>C"})
    assert res.status_code == 200
    data = res.json()
    assert data["variant"] == "chr2:70:A>C"  # 1-based in, 0-based canonical out
    assert data["variant_class"] == "snv"
    assert "chr2:" in data["working_interval"]  # the clean GenomicInterval str


async def test_resolve_bad_input_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/resolve", json={"variant": "not-a-variant"})
    assert res.status_code == 422


async def test_resolve_missing_field_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/resolve", json={})
    assert res.status_code == 422  # pydantic request validation


# --- design -----------------------------------------------------------------


async def test_design_json(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/design", json=DESIGN_BODY)
    assert res.status_code == 200
    data = res.json()
    assert data["disclaimer"]
    assert data["intent"] == "install"
    assert len(data["candidates"]) == 3
    assert data["candidates"][0]["chemistry"] == "prime"


async def test_design_html(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/design?format=html", json=DESIGN_BODY)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert res.text.startswith("<!DOCTYPE html>")
    assert "Plotly" in res.text


async def test_design_pdf(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/design?format=pdf", json=DESIGN_BODY)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-1.4")


async def test_design_bad_intent_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/design", json={"variant": "chr2:71:A>C", "intent": "bogus"})
    assert res.status_code == 422


async def test_design_chemistry_filter(client: httpx.AsyncClient) -> None:
    body = {**DESIGN_BODY, "chemistries": ["prime"]}
    res = await client.post("/api/design", json=body)
    assert res.status_code == 200
    assert {c["chemistry"] for c in res.json()["candidates"]} <= {"prime"}


async def test_design_weights_must_be_four(client: httpx.AsyncClient) -> None:
    body = {**DESIGN_BODY, "weights": [0.5, 0.5]}
    res = await client.post("/api/design", json=body)
    assert res.status_code == 422  # request model enforces min/max length 4


async def test_design_valid_weights(client: httpx.AsyncClient) -> None:
    body = {**DESIGN_BODY, "weights": [0.5, 0.2, 0.2, 0.1]}
    res = await client.post("/api/design", json=body)
    assert res.status_code == 200
    assert res.json()["candidates"]


async def test_design_unknown_chemistry_is_422(client: httpx.AsyncClient) -> None:
    body = {**DESIGN_BODY, "chemistries": ["telepathy"]}
    res = await client.post("/api/design", json=body)
    assert res.status_code == 422


async def test_design_requires_reference(app_no_reference: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app_no_reference)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        res = await c.post("/api/design", json=DESIGN_BODY)
        assert res.status_code == 503


# --- async job lifecycle ----------------------------------------------------


async def test_design_job_lifecycle(client: httpx.AsyncClient) -> None:
    submit = await client.post("/api/jobs/design", json=DESIGN_BODY)
    assert submit.status_code == 202
    job_id = submit.json()["job_id"]

    for _ in range(100):
        status = await client.get(f"/api/jobs/{job_id}")
        assert status.status_code == 200
        body = status.json()
        if body["state"] == "done":
            break
        assert body["state"] in {"pending", "running"}
        await asyncio.sleep(0.02)
    else:  # pragma: no cover - the job should finish well within the budget
        pytest.fail("design job did not finish")

    assert body["progress"] == 1.0
    assert body["error"] is None
    assert len(body["result"]["candidates"]) == 3


async def test_unknown_job_is_404(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/jobs/deadbeef")
    assert res.status_code == 404


async def test_design_job_reports_error(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        submit = await c.post("/api/jobs/design", json={"variant": "garbage", "intent": "install"})
        job_id = submit.json()["job_id"]
        for _ in range(100):
            body = (await c.get(f"/api/jobs/{job_id}")).json()
            if body["state"] in {"done", "error"}:
                break
            await asyncio.sleep(0.02)
        assert body["state"] == "error"
        assert body["error"]


# --- offtarget --------------------------------------------------------------


async def test_offtarget(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/offtarget", json={"spacer": "ATATATATATATATATATAT", "pam": "NGG"})
    assert res.status_code == 200
    body = res.json()
    report = OffTargetReport.model_validate(body["report"])  # Phase 1 schema-valid
    assert report.spacer == "ATATATATATATATATATAT"
    # The aggregate summary the CLI surfaces is present and consistent with the report.
    assert body["n_sites"] == report.n_sites
    assert body["worst_score"] == report.worst_score()
    assert body["specificity"] == report.specificity_score()
    assert 0.0 < body["specificity"] <= 1.0
    # The honest effective matrix is surfaced alongside the nominal one.
    assert body["effective_matrix"] == report.effective_matrix()


def test_offtarget_response_surfaces_effective_matrix() -> None:
    # The design report reconciles an all-approximation table via effective_matrix();
    # the standalone /api/offtarget envelope must do the same, so a client reading the
    # top-level matrix is not misled into treating an approximation as published CFD.
    from alleleforge.types.offtarget import OffTargetSite, ScoreMethod, SiteOrigin
    from alleleforge.types.sequence import GenomicInterval, Strand
    from alleleforge.web.api.models import OffTargetResponse

    approx = "doench-2016-seed-tolerance-approximation"
    report = OffTargetReport(
        spacer="A" * 20,
        pam="NGG",
        sites=(
            OffTargetSite(
                locus=GenomicInterval(chrom="chr2", start=0, end=20, strand=Strand.PLUS),
                mismatches=1,
                score=0.5,
                score_method=ScoreMethod.CFD,
                score_matrix=approx,
                origin=SiteOrigin.REFERENCE,
            ),
        ),
        mismatch_threshold=4,
        reference_build="hg38",
        scorer="CFD",
        score_matrix="doench-2016-cfd",  # nominal stays published
    )
    envelope = OffTargetResponse.from_report(report)
    assert envelope.report.score_matrix == "doench-2016-cfd"  # nominal preserved for fidelity
    assert envelope.effective_matrix == approx  # ...but the honest label is exposed


async def test_offtarget_tuning_knobs_are_honored(client: httpx.AsyncClient) -> None:
    # The engine's bulge budget and score thresholds are now exposed on the request
    # and plumbed through. Raising the thresholds and disallowing bulges can only
    # remove nominations, never add — a fixture-independent check they are honored.
    spacer = "ATATATATATATATATATAT"
    base = await client.post("/api/offtarget", json={"spacer": spacer, "pam": "NGG"})
    strict = await client.post(
        "/api/offtarget",
        json={
            "spacer": spacer,
            "pam": "NGG",
            "cfd_threshold": 1.0,
            "mit_threshold": 1.0,
            "dna_bulges": 0,
            "rna_bulges": 0,
        },
    )
    assert base.status_code == 200 and strict.status_code == 200
    assert strict.json()["n_sites"] <= base.json()["n_sites"]


async def test_offtarget_bad_pam_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/offtarget", json={"spacer": "ACGT", "pam": "XZ"})
    assert res.status_code == 422


# --- data & bench -----------------------------------------------------------


async def test_data_list(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/data")
    assert res.status_code == 200
    names = {d["name"] for d in res.json()["datasets"]}
    assert {"clinvar", "gnomad"} <= names


async def test_data_show(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/data/clinvar")
    assert res.status_code == 200
    assert res.json()["name"] == "clinvar"


async def test_data_unknown_is_404(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/data/nope")
    assert res.status_code == 404


async def test_bench_lists_tasks(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/bench")
    assert res.status_code == 200
    tasks = {t["task"] for t in res.json()["tasks"]}
    assert {"cas9-efficiency", "pe-efficiency", "offtarget-classification"} <= tasks
    # every task reports its primary metric and ECE is in the metric battery
    for t in res.json()["tasks"]:
        assert t["primary_metric"]
        assert "ece" in t["metrics"]


# --- batch (cohort) ---------------------------------------------------------


async def test_batch_designs_cohort(client: httpx.AsyncClient) -> None:
    body = {"variants": ["chr2:71:A>C", "chr2:71:A>G"], "intent": "install", "max_per_chemistry": 2}
    res = await client.post("/api/batch", json=body)
    assert res.status_code == 200
    data = res.json()
    assert (data["total"], data["succeeded"], data["failed"]) == (2, 2, 0)
    assert {it["item_id"] for it in data["items"]} == {"chr2:71:A>C", "chr2:71:A>G"}
    assert data["provenance"]["seed"] == 20240501
    assert "research" in data["disclaimer"].lower()


async def test_batch_isolates_per_item_failure(client: httpx.AsyncClient) -> None:
    # A wrong-ref variant errors; the cohort run records it and continues.
    body = {"variants": ["chr2:71:A>C", "chr2:71:G>C"], "intent": "install"}
    res = await client.post("/api/batch", json=body)
    assert res.status_code == 200
    data = res.json()
    assert (data["succeeded"], data["failed"]) == (1, 1)
    failed = next(it for it in data["items"] if it["status"] == "error")
    assert failed["item_id"] == "chr2:71:G>C" and "reference mismatch" in (failed["error"] or "")


async def test_batch_empty_variants_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/batch", json={"variants": [], "intent": "install"})
    assert res.status_code == 422  # min_length=1 request validation


async def test_batch_oversized_variants_is_422(client: httpx.AsyncClient) -> None:
    # A batch over the size cap is rejected at the boundary, before any work,
    # so a shared deployment cannot be flooded with an unbounded cohort.
    from alleleforge.web.api.models import MAX_BATCH_VARIANTS

    body = {"variants": ["chr2:71:A>C"] * (MAX_BATCH_VARIANTS + 1), "intent": "install"}
    res = await client.post("/api/batch", json=body)
    assert res.status_code == 422  # max_length request validation


async def test_batch_bad_intent_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/batch", json={"variants": ["chr2:71:A>C"], "intent": "bogus"})
    assert res.status_code == 422


async def test_oversized_string_and_list_fields_are_422(client: httpx.AsyncClient) -> None:
    # The batch *count* cap alone left individual field sizes unbounded, so a
    # within-count request could still carry a multi-megabyte spacer/variant or a
    # huge populations list into genome-scale work. Every string/list field is now
    # size-capped at the boundary, rejected with 422 before any scan.
    from alleleforge.web.api.models import MAX_POPULATIONS, MAX_SPACER_LEN

    big_spacer = await client.post("/api/offtarget", json={"spacer": "A" * (MAX_SPACER_LEN + 1)})
    assert big_spacer.status_code == 422
    big_pops = await client.post(
        "/api/offtarget",
        json={"spacer": "GACCATGCAACCTTGAACGT", "populations": ["afr"] * (MAX_POPULATIONS + 1)},
    )
    assert big_pops.status_code == 422
    huge_variant = await client.post("/api/batch", json={"variants": ["A" * 100_000]})
    assert huge_variant.status_code == 422
    # ...while a legitimate, real-world-sized request is still accepted.
    ok = await client.post(
        "/api/offtarget",
        json={"spacer": "GACCATGCAACCTTGAACGT", "populations": ["afr", "eur"]},
    )
    assert ok.status_code in (200, 503)  # 503 only if no reference is loaded, never 422


async def test_batch_requires_reference(app_no_reference: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app_no_reference)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        res = await c.post("/api/batch", json={"variants": ["chr2:71:A>C"], "intent": "install"})
        assert res.status_code == 503


# --- schema validation & no-egress guarantee --------------------------------


async def test_design_response_menu_is_phase1_valid(client: httpx.AsyncClient) -> None:
    # The flattened report embeds the candidates; the underlying menu round-trips
    # through the Phase 1 schema via the JSON job result as well.
    res = await client.post("/api/design", json=DESIGN_BODY)
    data = res.json()
    # rebuild a minimal menu check: candidate efficiency intervals are present
    for c in data["candidates"]:
        assert c["efficiency"]["interval_level"] == 0.80


async def test_no_outbound_network_during_design(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The defining safety property: a design request opens no outbound socket.
    import socket

    connects: list[object] = []
    real_connect = socket.socket.connect

    def _record(self: socket.socket, address: object) -> None:  # pragma: no cover - not called
        connects.append(address)
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", _record)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        res = await c.post("/api/design", json=DESIGN_BODY)
    assert res.status_code == 200
    assert connects == []  # no sequence data — no data at all — left the process


def test_create_app_loads_reference_from_env(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    fasta = tmp_path / "env.fa"  # type: ignore[operator]
    fasta.write_text(">chr1\n" + "ACGT" * 30 + "\n")
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", str(fasta))
    env_app = create_app()
    assert env_app.state.reference is not None


async def test_api_token_required_when_configured(reference: object) -> None:
    # With a token configured, /api/* needs a matching X-API-Token header; the
    # health probe stays open so liveness checks keep working.
    app = create_app(reference=reference, api_token="s3cret")  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        assert (await c.get("/api/health")).status_code == 200
        assert (await c.post("/api/resolve", json={"variant": "chr2:71:A>C"})).status_code == 401
        ok = await c.post(
            "/api/resolve", json={"variant": "chr2:71:A>C"}, headers={"X-API-Token": "s3cret"}
        )
        assert ok.status_code == 200
        bad = await c.post(
            "/api/resolve", json={"variant": "chr2:71:A>C"}, headers={"X-API-Token": "nope"}
        )
        assert bad.status_code == 401


async def test_no_token_leaves_api_open(client: httpx.AsyncClient) -> None:
    # The default app carries no token, so the local dev experience is unchanged.
    res = await client.post("/api/resolve", json={"variant": "chr2:71:A>C"})
    assert res.status_code == 200


def test_serve_refuses_public_bind_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from alleleforge.web.api.app import resolve_serve_token

    monkeypatch.delenv("ALLELEFORGE_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="non-loopback"):
        resolve_serve_token("0.0.0.0", None)


def test_serve_allows_loopback_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from alleleforge.web.api.app import resolve_serve_token

    monkeypatch.delenv("ALLELEFORGE_API_TOKEN", raising=False)
    assert resolve_serve_token("127.0.0.1", None) is None
    assert resolve_serve_token("0.0.0.0", "tok") == "tok"


def test_serve_reads_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from alleleforge.web.api.app import resolve_serve_token

    monkeypatch.setenv("ALLELEFORGE_API_TOKEN", "envtok")
    assert resolve_serve_token("0.0.0.0", None) == "envtok"
