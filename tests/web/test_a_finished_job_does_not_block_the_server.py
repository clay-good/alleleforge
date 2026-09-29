"""Polling a finished background job must not move its heavy work onto the event loop.

The callable and retained-result accounting run in a worker thread, but a successful poll
also serializes the report. A real design can exceed a megabyte and a cohort can be much
larger. Doing that pass inside the async route freezes health checks and every other poll
at the moment the background job is supposedly ready.

This test blocks the report's serialization under thread control. If it runs on the event
loop, the health coroutine cannot execute until the block times out; if the response is
built in a worker, health answers while serialization is still deliberately blocked.
"""

from __future__ import annotations

import asyncio
import threading
import time

import httpx

from alleleforge.report.builder import DesignReport

_BLOCK_SECONDS = 0.4
_DESIGN = {"variant": "chr2:71:A>C", "intent": "install", "max_per_chemistry": 3}


async def test_health_answers_while_a_finished_result_is_serialized(
    client: httpx.AsyncClient, monkeypatch
) -> None:
    submitted = await client.post("/api/jobs/design", json=_DESIGN)
    assert submitted.status_code == 202
    job_id = submitted.json()["job_id"]
    for _ in range(500):
        status = await client.get(f"/api/jobs/{job_id}")
        if status.json()["state"] in ("done", "error"):
            break
        await asyncio.sleep(0.01)
    assert status.json()["state"] == "done", status.text

    original_dump = DesignReport.model_dump
    loop_thread = threading.get_ident()
    serialization_threads: list[int] = []
    serialization_started = threading.Event()
    release_serialization = threading.Event()

    def blocked_dump(self, *args, **kwargs):
        serialization_threads.append(threading.get_ident())
        serialization_started.set()
        release_serialization.wait(_BLOCK_SECONDS)
        return original_dump(self, *args, **kwargs)

    monkeypatch.setattr(DesignReport, "model_dump", blocked_dump)

    async def health_after_serialization_starts() -> httpx.Response:
        while not serialization_started.is_set():
            await asyncio.sleep(0)
        return await client.get("/api/health")

    started = time.perf_counter()
    health_task = asyncio.create_task(health_after_serialization_starts())
    status_task = asyncio.create_task(client.get(f"/api/jobs/{job_id}"))
    try:
        health = await health_task
        elapsed = time.perf_counter() - started
    finally:
        release_serialization.set()
    polled = await status_task

    assert health.status_code == 200
    assert polled.status_code == 200
    assert serialization_threads and loop_thread not in serialization_threads
    assert elapsed < _BLOCK_SECONDS, (
        f"health waited {elapsed:.2f}s for finished-result serialization: the status "
        "handler is blocking the event loop"
    )
