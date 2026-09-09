"""The async job machinery was wired to the fast operation, not the slow one.

`POST /api/jobs/design` submits a single design — seconds of work — and polls. A
cohort is the operation this project is built for, and `POST /api/batch` blocked
until the whole thing finished: a three-hundred-variant run measured **3m 40s** on
one connection, past any ordinary reverse-proxy or browser timeout, and the stated
cohort size is larger than that. The only way to run a cohort over HTTP was the one
way that cannot survive it.

The status endpoint needed widening in the same breath. It serialized its result
with `isinstance(result, DesignReport)` — correct while a design was the only job
kind, and silently wrong the moment it was not: a cohort job would have reported
`state: done` with `result: null`, the work performed and the answer dropped.

Both entry points run the cohort through one function, so the two doors cannot come
to disagree about which configured sources a run was given, which is a mistake this
endpoint has already made once (see its own comment about population-awareness).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from alleleforge.web.api.models import JobState

_VARIANTS = ["chr2:71:A>C", "chr2:71:A>G"]


async def _run_to_completion(client: httpx.AsyncClient, variants: list[str]) -> dict:
    """Submit a cohort job and poll it to a terminal state."""
    submitted = await client.post("/api/jobs/batch", json={"variants": variants})
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["job_id"]
    for _ in range(1000):
        await asyncio.sleep(0.01)
        status = (await client.get(f"/api/jobs/{job_id}")).json()
        if status["state"] not in {JobState.PENDING, JobState.RUNNING}:
            return status
    raise AssertionError("the cohort job never reached a terminal state")


@pytest.mark.anyio
async def test_a_cohort_can_be_submitted_as_a_job(client: httpx.AsyncClient) -> None:
    status = await _run_to_completion(client, _VARIANTS)
    assert status["state"] == JobState.DONE, status
    assert status["progress"] == 1.0, status


@pytest.mark.anyio
async def test_a_finished_cohort_job_carries_its_result(client: httpx.AsyncClient) -> None:
    """The `isinstance` in the status endpoint must name this result shape too."""
    status = await _run_to_completion(client, _VARIANTS)
    result = status["result"]
    assert result is not None, "the job finished and its answer was dropped"
    assert result["total"] == len(_VARIANTS), result
    assert len(result["items"]) == len(_VARIANTS), result
    assert result["disclaimer"], result


@pytest.mark.anyio
async def test_the_two_doors_return_the_same_cohort(client: httpx.AsyncClient) -> None:
    """One runner behind both, so they cannot describe one run differently."""
    direct = (await client.post("/api/batch", json={"variants": _VARIANTS})).json()
    submitted = (await _run_to_completion(client, _VARIANTS))["result"]
    assert submitted is not None
    assert [item["item_id"] for item in submitted["items"]] == [
        item["item_id"] for item in direct["items"]
    ]
    assert submitted["total"] == direct["total"]
    assert submitted["succeeded"] == direct["succeeded"]


@pytest.mark.anyio
async def test_the_endpoint_is_in_the_schema(client: httpx.AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert "/api/jobs/batch" in paths, sorted(paths)
    assert "post" in paths["/api/jobs/batch"], paths["/api/jobs/batch"]


@pytest.mark.anyio
async def test_the_batch_description_does_not_offer_a_format_it_refuses(
    client: httpx.AsyncClient,
) -> None:
    """It advertised Parquet in the text a client reads before writing the request."""
    operation = (await client.get("/openapi.json")).json()["paths"]["/api/batch"]["post"]
    text = f"{operation.get('summary', '')} {operation.get('description', '')}"
    assert "arquet" not in text, text
    refused = await client.post("/api/batch?format=parquet", json={"variants": _VARIANTS})
    assert refused.status_code == 422, refused.text
