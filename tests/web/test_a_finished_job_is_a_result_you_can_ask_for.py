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
    assert "nosuchjob" in unknown.json()["detail"]


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
    assert "/api/batch" not in source, (
        "the TSV button re-POSTs the whole cohort to the blocking endpoint the panel "
        "already decided it could not hold a connection to"
    )
    assert "/result?format=tsv" in source, source
