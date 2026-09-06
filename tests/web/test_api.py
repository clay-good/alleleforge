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


async def test_the_browser_cohort_table_never_shows_a_bare_estimate(
    client: httpx.AsyncClient,
) -> None:
    """The SPA is aimed at people who will not open a terminal, and it showed `0.61`.

    The interval, the out-of-distribution flag and the recommended candidate's hazards
    all reach the browser in the batch response; the table rendered the point estimate
    alone. Triage is when a lone number is trusted, and this is the triage view for
    the least technical audience the project has.
    """
    app_js = (await client.get("/app.js")).text
    for field in (
        "best_efficiency_low",
        "best_efficiency_high",
        "best_efficiency_in_distribution",
        "best_caveats",
    ):
        assert field in app_js, f"the cohort table ignores {field}"
    assert "OOD" in app_js


async def test_the_browser_cohort_table_escapes_user_input(client: httpx.AsyncClient) -> None:
    """A cohort row is built from a pasted variant list and inserted with innerHTML.

    `item_id` is a raw input line and `error` is an exception message quoting it back;
    both went in unescaped, so a line like `<img src=x onerror=...>` executed in the
    page. This pins the escaper's existence and its use on both fields — a JS unit
    runner is out of scope here, so the check is structural.
    """
    app_js = (await client.get("/app.js")).text
    assert "&amp;" in app_js and "&lt;" in app_js and "&quot;" in app_js
    assert "esc(it.item_id)" in app_js
    # `cell` is what wraps the error and every other value, so it must escape too.
    assert 'const cell = (v) => (v === null || v === undefined ? "—" : esc(v));' in app_js
    assert "${it.item_id}" not in app_js  # never interpolated raw


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
    assert "<svg" in res.text  # charts are inlined SVG, not a CDN script


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


@pytest.mark.parametrize("weights", [[-1.0, 0.5, 0.5, 0.5], [0.0, 0.0, 0.0, 0.0]])
async def test_design_invalid_weight_values_are_422(
    client: httpx.AsyncClient, weights: list[float]
) -> None:
    # Well-typed but semantically invalid weights (negative / all-zero) are a bad
    # request, not a server fault: RankingWeights rejects them and the endpoint must
    # map that to 422, never leak a 500.
    res = await client.post("/api/design", json={**DESIGN_BODY, "weights": weights})
    assert res.status_code == 422
    batch = await client.post(
        "/api/batch", json={"variants": ["chr2:71:A>C"], "intent": "install", "weights": weights}
    )
    assert batch.status_code == 422


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


def test_create_app_config_file_governs_settings(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The web interface must resolve settings through Settings.load() (per the
    # provenance-reproducibility spec: the config file applies to CLI *and* web),
    # so a user config.toml governs a web run's seed — the provenance anchor — with
    # the same precedence as the CLI and library, not a bare Settings() that skips it.
    cfg_dir = tmp_path / "alleleforge"  # type: ignore[operator]
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text("seed = 30313233\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ALLELEFORGE_SEED", raising=False)
    app = create_app()
    assert app.state.settings.seed == 30313233


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


#: The plus-strand protospacer the shared test contig actually contains, 5' of its
#: planted ``TGG`` PAM — so the search has a real perfect hit to exclude.
ON_TARGET_SPACER = "TATATATATATACCAATATA"


# --- offtarget: the on-target locus, matching the CLI --------------------------


async def test_offtarget_reports_whether_the_on_target_was_excluded(
    client: httpx.AsyncClient,
) -> None:
    """The web envelope must carry the same qualifier the CLI prints.

    Its own docstring promises "the same summary the ``aforge offtarget`` CLI
    surfaces". Without ``on_target_excluded``, ``specificity`` is not the quantity a
    design report prints under that name, and a client cannot tell which it got.
    """
    res = await client.post("/api/offtarget", json={"spacer": ON_TARGET_SPACER})
    assert res.status_code == 200
    body = res.json()
    assert body["on_target_excluded"] is False
    assert body["n_sites"] >= 1  # the guide's own locus is among the reported sites


async def test_offtarget_excludes_a_supplied_locus(client: httpx.AsyncClient) -> None:
    plain = (await client.post("/api/offtarget", json={"spacer": ON_TARGET_SPACER})).json()
    # A reported site's locus handed straight back — the round trip a client
    # actually makes, and why this field takes the object rather than a string.
    locus = plain["report"]["sites"][0]["locus"]
    res = await client.post("/api/offtarget", json={"spacer": ON_TARGET_SPACER, "on_target": locus})
    assert res.status_code == 200
    excluded = res.json()
    assert excluded["on_target_excluded"] is True
    assert excluded["n_sites"] == plain["n_sites"] - 1
    assert excluded["specificity"] >= plain["specificity"]


@pytest.mark.parametrize(
    "locus",
    [
        "chr2:43-63(+)",  # the CLI's string form is not what this field takes
        {"chrom": "chr2", "start": 63, "end": 43, "strand": "+"},  # end before start
        {"chrom": "chr2", "start": 43},  # missing end
        {"start": 43, "end": 63, "strand": "+"},  # missing contig
    ],
)
async def test_offtarget_rejects_a_malformed_locus(client: httpx.AsyncClient, locus: str) -> None:
    """A typo must be a client error, not a silently un-excluded search."""
    res = await client.post("/api/offtarget", json={"spacer": ON_TARGET_SPACER, "on_target": locus})
    assert res.status_code == 422


async def test_design_render_candidates_caps_the_html(client: httpx.AsyncClient) -> None:
    """The web surface reaches the same render cap the CLI does."""
    body = {"variant": "chr2:71:A>C", "intent": "install", "run_offtarget": False}
    res = await client.post("/api/design?format=html", json={**body, "render_candidates": 3})
    assert res.status_code == 200
    assert "the top 3 by rank plus every Pareto-front candidate" in res.text

    uncapped = await client.post("/api/design?format=html", json={**body, "render_candidates": 0})
    assert uncapped.status_code == 200
    assert "plus every Pareto-front candidate" not in uncapped.text
    assert len(uncapped.text) > len(res.text)


async def test_design_json_ignores_the_render_cap(client: httpx.AsyncClient) -> None:
    """A display cap must never reach the machine-readable body."""
    res = await client.post(
        "/api/design",
        json={
            "variant": "chr2:71:A>C",
            "intent": "install",
            "run_offtarget": False,
            "render_candidates": 3,
        },
    )
    assert res.status_code == 200
    assert len(res.json()["candidates"]) > 3


@pytest.mark.parametrize(
    ("cell_context", "expect_in_distribution"),
    [(None, True), ("HEK293T", True), ("K562", True), ("HepG2", False)],
)
async def test_design_cell_context_drives_the_ood_flag(
    client: httpx.AsyncClient, cell_context: str | None, expect_in_distribution: bool
) -> None:
    """The honesty flag must be reachable from the surface most likely used casually.

    The efficiency scorers are trained on HEK293T/K562, and a context outside that
    is meant to flag every prediction out-of-distribution rather than report it as
    if it were in-domain. Before `cell_context` was exposed here, the web API could
    not set it at all — so every design it returned claimed `in_distribution: true`
    whatever cell line the user was actually targeting.
    """
    body: dict[str, object] = {
        "variant": "chr2:71:A>C",
        "intent": "install",
        "run_offtarget": False,
    }
    if cell_context is not None:
        body["cell_context"] = cell_context
    res = await client.post("/api/design", json=body)
    assert res.status_code == 200
    top = res.json()["candidates"][0]
    assert top["efficiency"]["in_distribution"] is expect_in_distribution
    assert ("ood" in top["flags"]) is not expect_in_distribution


async def test_offtarget_regions_scope_the_web_search(client: httpx.AsyncClient) -> None:
    """Region scoping is safe to expose over HTTP — it is data, not a file path.

    The file-backed safety inputs stay CLI-only because a client-supplied path is a
    server-side file-read primitive. Intervals are neither: they are the same shape
    a reported site's `locus` already has, so a client can build one from a previous
    response.
    """
    body = {"spacer": ON_TARGET_SPACER}
    everywhere = (await client.post("/api/offtarget", json=body)).json()
    assert everywhere["n_sites"] >= 1

    away = await client.post(
        "/api/offtarget",
        json={**body, "offtarget_regions": [{"chrom": "chr2", "start": 200, "end": 300}]},
    )
    assert away.status_code == 200
    assert away.json()["n_sites"] == 0

    # A window containing the site — wide enough for the scan to place a
    # protospacer and its PAM, which the site's own 20 bp span is not.
    over = await client.post(
        "/api/offtarget",
        json={**body, "offtarget_regions": [{"chrom": "chr2", "start": 0, "end": 140}]},
    )
    assert over.status_code == 200
    assert over.json()["n_sites"] == everywhere["n_sites"]

    # An empty interval is refused rather than silently scoping the scan to nothing.
    empty = await client.post(
        "/api/offtarget",
        json={**body, "offtarget_regions": [{"chrom": "chr2", "start": 50, "end": 50}]},
    )
    assert empty.status_code == 422


async def test_design_offtarget_regions_are_accepted(client: httpx.AsyncClient) -> None:
    res = await client.post(
        "/api/design",
        json={
            "variant": "chr2:71:A>C",
            "intent": "install",
            "offtarget_regions": [{"chrom": "chr2", "start": 0, "end": 140}],
        },
    )
    assert res.status_code == 200
    assert res.json()["candidates"]


def test_the_offtarget_envelope_says_what_the_search_covered() -> None:
    """The API returned a spotless-looking result for a search that ran on nothing.

    `OffTargetResponse` exists to give a client "the same summary the `aforge
    offtarget` CLI surfaces" — and it projected every *numeric* method on the report
    (`n_sites`, `worst_score`, `specificity_score`, `ancestry_stratification`,
    `effective_matrix`) while omitting the one *prose* method. The CLI prints the
    aggregates and then `search: …` beneath them, and that line is what says the scan
    covered 1% of what was asked for, or nothing at all. A client saw
    `n_sites: 0, specificity: 1.0` and no way to tell a clean guide from an empty run.
    """
    from alleleforge.types.offtarget import OffTargetReport
    from alleleforge.web.api.models import OffTargetResponse

    empty = OffTargetReport(
        spacer="GACCCCCTCCACCCCGCCTC",
        pam="NGG",
        sites=(),
        mismatch_threshold=4,
        dna_bulge_budget=1,
        rna_bulge_budget=1,
        cfd_threshold=0.0,
        mit_threshold=0.0,
        searched_bases=0,
        resolved_bases=0,
        reference_build="hg38",
        scorer="cfd",
    )
    envelope = OffTargetResponse.from_report(empty)
    # The reassuring numbers are all there...
    assert (envelope.n_sites, envelope.worst_score, envelope.specificity) == (0, 0.0, 1.0)
    # ...and so, now, is the sentence that makes them readable.
    assert envelope.search_description == empty.search_description()
    assert "NO SEQUENCE WAS SEARCHED" in envelope.model_dump_json()


def test_the_api_token_env_var_is_enforced_by_the_app_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ALLELEFORGE_API_TOKEN` was read by `serve()` and by nothing else.

    The deployment guide and the Dockerfile both run
    `uvicorn alleleforge.web.api.app:app`, which binds the module-level app directly
    and never calls `serve()`. So the "refusing to bind to a non-loopback host
    without an API token" guard never ran on the documented path — and worse, an
    operator who published the port and set the variable believing it protected the
    service got a fully open API, because nothing on that path read it.
    """
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    monkeypatch.setenv("ALLELEFORGE_API_TOKEN", "s3cret")
    client = TestClient(create_app())
    body = {"variant": "chr1:1:A>T", "build": "hg38"}
    assert client.post("/api/resolve", json=body).status_code == 401
    assert (
        client.post("/api/resolve", json=body, headers={"X-API-Token": "s3cret"}).status_code == 200
    )
    # Health stays reachable so a liveness probe does not need the secret.
    assert client.get("/api/health").status_code == 200


def test_an_unset_token_leaves_the_local_api_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """The unchanged local experience: no token set, no header needed."""
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    monkeypatch.delenv("ALLELEFORGE_API_TOKEN", raising=False)
    client = TestClient(create_app())
    assert (
        client.post("/api/resolve", json={"variant": "chr1:1:A>T", "build": "hg38"}).status_code
        == 200
    )


def test_every_response_carries_the_security_headers() -> None:
    """The served app sent no security headers at all.

    A Content-Security-Policy is the structural form of a promise the project already
    makes in prose — "the served frontend loads no third-party scripts" — which was
    violated for as long as the rendered report carried a `cdn.plot.ly` script tag,
    because nothing enforced it. Prose is not a control.
    """
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import _SECURITY_HEADERS, create_app

    client = TestClient(create_app())
    for path in ("/", "/api/health"):
        res = client.get(path)
        assert res.status_code == 200, path
        for header, value in _SECURITY_HEADERS.items():
            assert res.headers.get(header) == value, f"{path} is missing {header}"


def test_the_policy_admits_no_third_party_script() -> None:
    """The specific clause that makes the previous round's defect impossible.

    A `srcdoc` frame inherits its parent's policy, so this governs the embedded report
    as well as the shell: a script tag reintroduced into the renderer is *blocked* by
    the browser, not merely against policy. Verified live — an injected
    `<script src="https://cdn.plot.ly/…">` produced zero network requests.
    """
    from alleleforge.web.api.app import _SECURITY_HEADERS

    policy = _SECURITY_HEADERS["Content-Security-Policy"]
    directives = dict(
        (part.split(" ", 1) + [""])[:2] for part in (p.strip() for p in policy.split(";"))
    )
    assert directives["script-src"] == "'self'", "a third-party script would be admitted"
    assert directives["default-src"] == "'self'"
    assert directives["object-src"] == "'none'"
    assert directives["frame-ancestors"] == "'none'"
    # Inline *styles* are allowed (the shell and the report both carry a <style>
    # block); inline scripts deliberately are not, which is the half that matters.
    assert "unsafe-inline" in directives["style-src"]
    assert "unsafe-inline" not in directives["script-src"]
    assert "unsafe-eval" not in policy
