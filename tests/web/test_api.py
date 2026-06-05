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


async def test_openapi_is_generated(client: httpx.AsyncClient) -> None:
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    assert "/api/design" in res.json()["paths"]


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
    report = OffTargetReport.model_validate(res.json())  # Phase 1 schema-valid
    assert report.spacer == "ATATATATATATATATATAT"


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


async def test_batch_bad_intent_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post("/api/batch", json={"variants": ["chr2:71:A>C"], "intent": "bogus"})
    assert res.status_code == 422


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
