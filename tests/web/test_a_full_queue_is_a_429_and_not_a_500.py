"""The in-flight cap is the deployment's only defense, and nothing checked its answer.

`JobManager` takes a `max_in_flight` cap and raises `JobCapacityError` past it. Both
async doors — `POST /api/jobs/design` and `POST /api/jobs/batch` — catch that and turn it
into a `429`, which is the one status a client can act on: it means *retry later*, and a
well-behaved client backs off on it. `tests/web/test_jobs.py` covers the manager's own
refusal; no test covered what the HTTP layer does with it.

Deleting either `raise HTTPException(429)` does not restore a 500 by accident — it is
worse than that. The `except` body becomes a no-op, execution falls through to
`return JobSubmitResponse(job_id=record.id, ...)` with `record` never bound, and the
caller gets an `UnboundLocalError` as a 500. So a deployment at capacity would report
*its own internal defect* instead of a documented, retryable limit, and a client would
have no reason to back off — it would retry immediately into the same wall.

Both deletions survived `tests/web`.

The 409 below is the third survivor in the same helper: `/api/jobs/{id}/result` renders a
finished job's own payload, and the `else` branch answers the case where that payload is
neither a design nor a cohort. Only two endpoints submit work, so the branch is
unreachable over HTTP alone — it is reachable through the injected manager, which is a
supported entry point (`create_app(jobs=...)`), and that is how it is pinned here.

Found by deleting each refusal (`scripts/mutate.py --mode raise`).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app
from alleleforge.web.api.jobs import JobManager

#: Long enough that the first job is unambiguously still in flight when the second
#: arrives, short enough for a suite.
_BLOCK_SECONDS = 1.5


class _SlowReference:
    """A reference whose reads block, so the first job stays in flight on purpose.

    `time.sleep` releases the GIL, so the event loop is free to accept the second
    submission — which is the whole point: the 429 must come from the cap, not from a
    server too busy to answer.
    """

    def __init__(self, inner: ReferenceGenome) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def fetch_result(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(_BLOCK_SECONDS)
        return self._inner.fetch_result(*args, **kwargs)


def _one_at_a_time_app(tmp_path: Path) -> FastAPI:
    import random

    rng = random.Random(12)
    fasta = tmp_path / "slow.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(2000)) + "\n")
    return create_app(
        reference=_SlowReference(ReferenceGenome(fasta, build="hg38")),
        jobs=JobManager(max_in_flight=1),
    )


def _ref_base(app: FastAPI) -> str:
    from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

    return str(
        app.state.reference.fetch(
            GenomicInterval(
                chrom="chr1",
                start=1000,
                end=1001,
                strand=Strand.PLUS,
                coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
            )
        )
    )


async def _wait_until_in_flight(client: httpx.AsyncClient, job_id: str) -> None:
    """Block until the first job is actually running, so the cap is really occupied."""
    for _ in range(400):
        await asyncio.sleep(0.01)
        if (await client.get(f"/api/jobs/{job_id}")).json()["state"] == "running":
            return
    pytest.fail(
        "the first job never reached `running`: on a reference whose every read blocks "
        "it cannot have finished, so the cap was never occupied and the second "
        "submission below would not be measuring anything"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "route, body",
    [
        ("/api/jobs/design", None),
        ("/api/jobs/batch", {"variants": ["chr1:1001:{ref}>A"]}),
    ],
    ids=["design", "batch"],
)
async def test_a_submission_past_the_in_flight_cap_is_refused_with_429(
    tmp_path: Path, route: str, body: dict[str, Any] | None
) -> None:
    """Both async doors, because each carries its own copy of the handler."""
    app = _one_at_a_time_app(tmp_path)
    variant = "chr1:1001:" + _ref_base(app) + ">A"
    payload = (
        {"variant": variant}
        if body is None
        else {"variants": [v.format(ref=_ref_base(app)) for v in body["variants"]]}
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post(route, json=payload)
        assert first.status_code == 202, first.text
        await _wait_until_in_flight(client, first.json()["job_id"])

        second = await client.post(route, json=payload)

    assert second.status_code == 429, (
        f"a submission past the cap answered {second.status_code}, not 429. A 500 here "
        "is the shape of the deleted guard: the handler falls through to a `record` it "
        "never bound. 429 is the only answer a client can act on — it is the one that "
        "means retry later, and the one a backoff is written against.",
        second.text,
    )
    detail = second.json()["detail"]
    # The cap is a number the operator chose, so the refusal names it: "retry later" with
    # no indication of what the limit is leaves nothing to tune.
    assert "max 1" in detail, detail
    assert "retry" in detail.lower(), detail


@pytest.mark.anyio
async def test_a_retained_result_that_renders_as_nothing_is_a_409(tmp_path: Path) -> None:
    """The third refusal in the same helper: a payload that is neither design nor cohort.

    409, not 500: the job exists, it finished, and the question "render this as JSON" is
    the one that cannot be answered. Deleting the raise drops through to
    `isinstance(rendered, ...)` on an unbound name — a 500 that blames the server for a
    request that was simply not renderable.
    """
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "ACGT" * 100 + "\n")
    jobs = JobManager()
    app = create_app(reference=ReferenceGenome(fasta, build="hg38"), jobs=jobs)

    record = await jobs.submit(lambda: 42)  # not a FinishedDesign, not a FinishedCohort
    for _ in range(400):
        await asyncio.sleep(0.01)
        if jobs.get(record.id) is not None and jobs.get(record.id).state == "done":
            break

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/jobs/{record.id}/result?format=json")

    assert response.status_code == 409, (response.status_code, response.text)
    assert "no renderable result" in response.json()["detail"], response.text
