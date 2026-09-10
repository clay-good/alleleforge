"""The reason to submit a job is that the deployment keeps answering while it runs.

`POST /api/jobs/batch` exists because a three-hundred-variant cohort blocked a connection
for 3m 40s, past any ordinary proxy timeout. Every test of it checks that the job is
accepted, that it finishes, and that the two doors agree about the answer — and none
checks the property the machinery was built for: that the *rest of the deployment*
responds while the job is in flight.

The job runs on a worker thread (`asyncio.to_thread`), so the property has two halves and
this file pins both: the `202` must arrive before the work could have finished, and the
deployment must answer a request while the job is in flight. A regression that runs the
work inline satisfies neither — and fails both of these, which an earlier draft did not:
it polled for `state == running`, and inline work was already *finished* by the first
poll, so the test skipped itself rather than failing.

The worker-thread arrangement is necessary and not sufficient. What a thread gets you
depends on what it runs: a native kernel that holds the GIL for its whole body serializes
against the loop anyway, which is why the scan kernels release it (see
`test_the_scan_releases_the_interpreter`). This file measures the scheduling; that one
measures what the scheduling is worth.
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
from alleleforge.web.api.models import JobState

#: Long enough that a blocked event loop is unmistakable, short enough for a test suite.
_BLOCK_SECONDS = 0.4


class _SlowReference:
    """A reference whose reads block, so the job is slow for a reason the test controls.

    `time.sleep` releases the GIL, exactly as the native kernels now do; what is measured
    is whether the server's event loop is free while a worker thread is busy, not how
    fast this machine designs.
    """

    def __init__(self, inner: ReferenceGenome) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def fetch_result(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(_BLOCK_SECONDS)
        return self._inner.fetch_result(*args, **kwargs)


@pytest.fixture
def slow_app(tmp_path: Path) -> FastAPI:
    import random

    rng = random.Random(12)
    sequence = "".join(rng.choice("ACGT") for _ in range(2000))
    fasta = tmp_path / "slow.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    return create_app(reference=_SlowReference(ReferenceGenome(fasta, build="hg38")))


@pytest.mark.anyio
async def test_submission_returns_before_the_work_could_have_finished(slow_app: FastAPI) -> None:
    """The deterministic half: `202` arrives while the work is still ahead of it.

    If the job ran on the event loop, the POST would return only after the whole design —
    which is the failure this endpoint exists to prevent, and the one a *skip* would hide:
    an earlier draft of this test polled for `state == running`, and under that regression
    the job was already finished by the first poll, so the test skipped itself rather than
    failing.
    """
    transport = httpx.ASGITransport(app=slow_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        variant = "chr1:1001:" + _ref_base(slow_app) + ">A"
        start = time.perf_counter()
        submitted = await client.post("/api/jobs/design", json={"variant": variant})
        elapsed = time.perf_counter() - start
        assert submitted.status_code == 202, submitted.text
        assert elapsed < _BLOCK_SECONDS, (
            f"submitting took {elapsed:.2f}s, longer than one blocking read: the work is "
            "running on the event loop rather than on a worker thread"
        )
        # And the job is real: it reaches a terminal state and carries a result.
        for _ in range(400):
            await asyncio.sleep(0.02)
            status = (await client.get(f"/api/jobs/{submitted.json()['job_id']}")).json()
            if status["state"] not in {JobState.PENDING, JobState.RUNNING}:
                break
        assert status["state"] == JobState.DONE, status


@pytest.mark.anyio
async def test_health_answers_while_a_job_runs(slow_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=slow_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        submitted = await client.post(
            "/api/jobs/design", json={"variant": "chr1:1001:" + _ref_base(slow_app) + ">A"}
        )
        assert submitted.status_code == 202, submitted.text
        job_id = submitted.json()["job_id"]

        # Wait for the job to actually be running, so what follows is measured against
        # work in flight rather than against a job still queued.
        running = False
        for _ in range(200):
            await asyncio.sleep(0.01)
            state = (await client.get(f"/api/jobs/{job_id}")).json()["state"]
            if state == JobState.RUNNING:
                running = True
                break
            if state == JobState.DONE:
                break
        assert running, (
            "the job never appeared as running: on a design whose every read blocks it "
            "cannot have finished between two polls, so it did not run concurrently"
        )

        start = time.perf_counter()
        health = await client.get("/api/health")
        elapsed = time.perf_counter() - start
        assert health.status_code == 200
        assert elapsed < _BLOCK_SECONDS, (
            f"a health check took {elapsed:.2f}s while a job was running: the worker "
            "thread is holding the event loop"
        )


def _ref_base(app: FastAPI) -> str:
    from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

    reference = app.state.reference
    return str(
        reference.fetch(
            GenomicInterval(
                chrom="chr1",
                start=1000,
                end=1001,
                strand=Strand.PLUS,
                coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
            )
        )
    )
