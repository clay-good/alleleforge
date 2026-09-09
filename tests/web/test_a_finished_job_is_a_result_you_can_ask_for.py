"""A finished job had one rendering, and the page paid for that by running the cohort twice.

`POST /api/design` offers six renderings and `POST /api/batch` two. Their async twins —
the doors the documentation tells a client behind a proxy timeout to use, and the ones the
served page actually uses for a cohort — offered exactly one: the JSON envelope
`GET /api/jobs/{id}` returns. So the audience that *has* to go async, because their run is
the long one, was the audience that could not have the TSV, the PDF, or the full menu.

The page shows what that costs. `downloadBatchTsv` re-`POST`ed the whole cohort to the
blocking `/api/batch?format=tsv` — the endpoint the comment three functions above it says
"fails exactly on the cohorts this panel exists for". So the TSV button spent the cohort's
whole runtime again (the page's own note measures a 300-variant run at 3m 40s) on a result
already sitting in the browser, over a connection the panel had already concluded could not
be held open that long. The answer was in the job store the entire time.

`GET /api/jobs/{id}/result?format=…` renders a *finished* job's stored result in any format
its synchronous twin offers. Nothing is recomputed.

The store is bounded and in-memory, though — it keeps the most recent finished jobs and
does not survive a restart — so a result can be gone while the cohort is still on the
page. That is the one case where re-running is the only way to get the table, and the page
does it behind a `404`, having said so first: this button's whole point is not spending the
run twice, and doing it silently would be the old behaviour wearing a new URL.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

_APP_JS = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
).read_text(encoding="utf-8")


async def _finished(client: httpx.AsyncClient, path: str, body: dict[str, object]) -> str:
    """Submit a job and poll it to a terminal state; return its id."""
    submitted = await client.post(path, json=body)
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["job_id"]
    for _ in range(600):
        status = (await client.get(f"/api/jobs/{job_id}")).json()
        if status["state"] in ("done", "error"):
            assert status["state"] == "done", status
            return str(job_id)
    raise AssertionError("job never finished")


@pytest.mark.anyio
async def test_a_design_job_can_be_read_in_every_format_the_sync_call_offers(
    client: httpx.AsyncClient,
) -> None:
    job_id = await _finished(client, "/api/jobs/design", {"variant": "chr2:71:A>C"})
    for fmt, prefix in (
        ("json", "application/json"),
        ("menu", "application/json"),
        ("html", "text/html"),
        ("pdf", "application/pdf"),
        ("tsv", "text/tab-separated-values"),
    ):
        response = await client.get(f"/api/jobs/{job_id}/result?format={fmt}")
        assert response.status_code == 200, (fmt, response.text)
        assert response.headers["content-type"].startswith(prefix), (
            fmt,
            response.headers["content-type"],
        )


@pytest.mark.anyio
async def test_the_menu_from_a_job_carries_what_the_report_withheld(
    client: httpx.AsyncClient,
) -> None:
    """The whole point of `menu`: an async client is not the one who gets the truncation."""
    job_id = await _finished(client, "/api/jobs/design", {"variant": "chr2:71:A>C"})
    report = (await client.get(f"/api/jobs/{job_id}/result?format=json")).json()
    menu = (await client.get(f"/api/jobs/{job_id}/result?format=menu")).json()

    candidate = report["candidates"][0]
    assert candidate["n_outcome_alleles"] > len(candidate["outcome_top"]), candidate
    alleles = menu["candidates"][0]["outcome"]["alleles"]
    assert len(alleles) == candidate["n_outcome_alleles"], alleles


@pytest.mark.anyio
async def test_a_cohort_job_yields_the_same_flat_table_the_blocking_call_does(
    client: httpx.AsyncClient,
) -> None:
    job_id = await _finished(client, "/api/jobs/batch", {"variants": ["chr2:71:A>C"]})
    response = await client.get(f"/api/jobs/{job_id}/result?format=tsv")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/tab-separated-values")

    from_job = response.text
    blocking = await client.post("/api/batch?format=tsv", json={"variants": ["chr2:71:A>C"]})
    from_sync = blocking.text
    assert from_job.splitlines()[0] == from_sync.splitlines()[0], "the two tables disagree"


@pytest.mark.anyio
async def test_a_job_offers_only_the_formats_its_own_kind_has(client: httpx.AsyncClient) -> None:
    """A cohort has no PDF — `aforge batch` has none either — and says so rather than 500ing."""
    job_id = await _finished(client, "/api/jobs/batch", {"variants": ["chr2:71:A>C"]})
    response = await client.get(f"/api/jobs/{job_id}/result?format=pdf")
    assert response.status_code == 422, response.text
    assert "tsv" in response.json()["detail"], response.text


@pytest.mark.anyio
async def test_an_unfinished_or_unknown_job_has_no_result(client: httpx.AsyncClient) -> None:
    unknown = await client.get("/api/jobs/nosuchjob/result")
    assert unknown.status_code == 404, unknown.text
    detail = unknown.json()["detail"]
    assert "nosuchjob" in detail
    # A caller here has usually just watched this job finish: the store keeps the most
    # recent finished jobs and does not survive a restart, so "unknown" alone leaves them
    # holding an id with nothing to do about it.
    assert "retained" in detail and "again" in detail, detail


@pytest.mark.anyio
async def test_a_result_is_behind_the_same_token_as_the_run(reference) -> None:
    """The result carries the cohort's variants; a new route must not be a new door."""
    from alleleforge.web.api.app import create_app

    app = create_app(reference=reference, api_token="secret")
    headers = {"X-API-Token": "secret"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        submitted = await client.post(
            "/api/jobs/batch", json={"variants": ["chr2:71:A>C"]}, headers=headers
        )
        assert submitted.status_code == 202, submitted.text
        job_id = submitted.json()["job_id"]
        for _ in range(600):
            status = (await client.get(f"/api/jobs/{job_id}", headers=headers)).json()
            if status["state"] in ("done", "error"):
                break
        assert status["state"] == "done", status

        assert (await client.get(f"/api/jobs/{job_id}/result?format=tsv")).status_code == 401
        allowed = await client.get(f"/api/jobs/{job_id}/result?format=tsv", headers=headers)
        assert allowed.status_code == 200, allowed.text


@pytest.mark.anyio
async def test_a_failed_job_does_not_render_as_a_result(client: httpx.AsyncClient) -> None:
    submitted = await client.post("/api/jobs/design", json={"variant": "not-a-variant"})
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["job_id"]
    for _ in range(600):
        status = (await client.get(f"/api/jobs/{job_id}")).json()
        if status["state"] in ("done", "error"):
            break
    assert status["state"] == "error", status
    response = await client.get(f"/api/jobs/{job_id}/result")
    assert response.status_code == 409, response.text
    assert status["error"] in response.json()["detail"], response.text


def test_the_page_downloads_the_cohort_table_from_the_job_it_already_ran() -> None:
    """The behavioural half: the button must not re-run the cohort to format it."""
    body = re.search(r"async function downloadBatchTsv\(\)\s*\{(.*?)\n\}", _APP_JS, re.S)
    assert body is not None, "downloadBatchTsv is gone; this guard needs rewriting"
    # Comments are stripped: this function's own comment explains what it stopped doing,
    # and naming the old endpoint there must not read as still calling it.
    source = "\n".join(
        line for line in body.group(1).splitlines() if not line.lstrip().startswith("//")
    )
    assert "/result?format=tsv" in source, source
    # `/api/batch` may still appear, but only *after* the job result has been asked for
    # and only behind a 404 — the store keeps the most recent finished jobs and does not
    # survive a restart, so re-running is the last resort rather than the first move. The
    # ordering is the whole claim: reaching for the blocking endpoint first is what this
    # button stopped doing.
    if "/api/batch" in source:
        assert source.index("/result?format=tsv") < source.index("/api/batch"), source
        assert "404" in source[: source.index("/api/batch")], (
            "the cohort is re-designed unconditionally rather than only when the "
            "finished run is gone"
        )


def test_the_progress_line_is_not_the_last_thing_the_reader_sees() -> None:
    """A "…designing it again" message must not outlive the download it describes.

    Driving this in a browser — run a cohort, restart the server, click Download TSV —
    the file arrived and the status line still read "The server no longer holds that run
    — designing it again to build the table…". A progress message left standing after the
    work finished reads as work still running. It also has something to say that the
    ordinary path does not: this table came from a *second* run, so it is not the same
    document as the JSON downloaded from the first.
    """
    body = re.search(r"async function downloadBatchTsv\(\)\s*\{(.*?)\n\}", _APP_JS, re.S)
    assert body is not None, "downloadBatchTsv is gone; this guard needs rewriting"
    source = body.group(1)
    if "/api/batch" not in source:
        pytest.skip("the page no longer falls back to re-running the cohort")
    assert "a.click()" in source, source
    after = source[source.index("a.click()") :]
    assert "batchStatus.textContent" in after, (
        "nothing tells the reader the download finished; the progress line is the last "
        "message left on screen"
    )
    assert "new run" in after, after


def test_the_page_says_so_before_it_re_runs_a_cohort_it_lost() -> None:
    """The fallback is minutes of work nobody asked for; it must not happen in silence."""
    body = re.search(r"async function downloadBatchTsv\(\)\s*\{(.*?)\n\}", _APP_JS, re.S)
    assert body is not None, "downloadBatchTsv is gone; this guard needs rewriting"
    source = body.group(1)
    if "/api/batch" not in source:
        pytest.skip("the page no longer falls back to re-running the cohort")
    before = source[: source.index("/api/batch")]
    assert "batchStatus.textContent" in before, (
        "the cohort is re-designed with no word to the reader about why the download "
        "is suddenly taking minutes"
    )
