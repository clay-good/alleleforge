"""A cap on the *number* of retained jobs is not a bound on memory.

`JobManager` evicted oldest-terminal-first past a thousand records, on the reasoning that
"a long-lived server would otherwise grow `_jobs` without bound". That was written when a
record held a polling envelope. A finished **design** job now keeps the ranked menu *and*
the report built from it — measured at 1.25 MiB of JSON for a 200-candidate menu on a
30 kb contig — and the served page submits every single-variant design through this store,
so the count cap permits well over a gigabyte of retained results.

Both bounds apply now, whichever is reached first. The count cap counts terminal records,
not in-flight work; the byte cap never drops an in-flight job. The size is measured once,
when the work finishes, by serializing what the record holds: the manager schedules opaque
callables and must not learn what a design is, so it introspects — anything with
`model_dump_json`, and any dataclass by summing its fields, which is the shape of both
finished-result types. A result too large to retain becomes a pollable error rather than a
job id that can only return 404.
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import BaseModel

from alleleforge.web.api.jobs import DEFAULT_MAX_RESULT_BYTES, JobManager, JobState


class _Payload(BaseModel):
    blob: str


class _UnserializablePayload:
    def model_dump_json(self) -> str:
        raise ValueError("cannot serialize result")


@dataclasses.dataclass(frozen=True)
class _Pair:
    left: _Payload
    right: _Payload


def _payload(size: int) -> _Payload:
    return _Payload(blob="x" * size)


@pytest.mark.anyio
async def test_a_finished_result_is_measured() -> None:
    manager = JobManager()
    record = await manager.submit(lambda: _payload(5_000))
    while record.state is not JobState.DONE:
        await _tick()
    assert record.result_bytes > 5_000, record.result_bytes
    assert manager.retained_bytes() == record.result_bytes


@pytest.mark.anyio
async def test_non_ascii_json_is_measured_in_bytes_not_characters() -> None:
    manager = JobManager(max_result_bytes=200)
    payload = _Payload(blob="🧬" * 100)
    record = await manager.submit(lambda: payload)
    while record.state not in (JobState.DONE, JobState.ERROR):
        await _tick()

    encoded = payload.model_dump_json().encode("utf-8")
    assert len(encoded) > len(payload.model_dump_json()), "fixture must distinguish bytes"
    assert record.state is JobState.ERROR
    assert f"{len(encoded)} bytes" in (record.error or "")
    assert "200-byte retained-result limit" in (record.error or "")
    assert record.result is None
    assert record.result_bytes == 0
    assert manager.get(record.id) is record, "the caller must be able to poll the refusal"


@pytest.mark.anyio
async def test_in_flight_records_do_not_spend_the_terminal_record_budget() -> None:
    import threading

    release_second = threading.Event()
    manager = JobManager(max_jobs=1, max_in_flight=2)
    first = await manager.submit(lambda: _payload(100))
    second = await manager.submit(lambda: release_second.wait(10))

    try:
        while first.state is not JobState.DONE:
            await _tick()
        assert second.state is JobState.RUNNING
        assert manager.get(first.id) is first
    finally:
        release_second.set()

    while second.state is not JobState.DONE:
        await _tick()
    assert manager.get(first.id) is None
    assert manager.get(second.id) is second


@pytest.mark.anyio
async def test_result_measurement_does_not_run_on_the_event_loop(monkeypatch) -> None:
    import threading

    loop_thread = threading.get_ident()
    measurement_threads: list[int] = []

    def measure(_result: object) -> int:
        measurement_threads.append(threading.get_ident())
        return 1

    monkeypatch.setattr(JobManager, "_measure", staticmethod(measure))
    manager = JobManager()
    record = await manager.submit(lambda: _payload(100))
    while record.state is not JobState.DONE:
        await _tick()

    assert measurement_threads
    assert measurement_threads != [loop_thread], "serializing the result blocked the event loop"


@pytest.mark.anyio
async def test_a_result_that_cannot_be_measured_is_not_retained_unaccounted() -> None:
    manager = JobManager(max_result_bytes=1)
    payload = _UnserializablePayload()
    record = await manager.submit(lambda: payload)
    while record.state not in (JobState.DONE, JobState.ERROR):
        await _tick()

    assert record.state is JobState.ERROR
    assert record.result is None, "failed measurement retained a result recorded as zero bytes"


@pytest.mark.anyio
async def test_a_dataclass_of_models_is_measured_by_its_fields() -> None:
    """The shape both finished-result types actually have."""
    manager = JobManager()
    record = await manager.submit(lambda: _Pair(_payload(1_000), _payload(2_000)))
    while record.state is not JobState.DONE:
        await _tick()
    assert record.result_bytes > 3_000, record.result_bytes


@pytest.mark.anyio
async def test_the_byte_budget_evicts_before_the_count_cap_would() -> None:
    """A thousand records is not the bound that matters when each holds a megabyte."""
    manager = JobManager(max_jobs=1_000, max_result_bytes=20_000)
    ids = []
    for _ in range(6):
        record = await manager.submit(lambda: _payload(5_000))
        while record.state is not JobState.DONE:
            await _tick()
        ids.append(record.id)

    assert manager.retained_bytes() <= 20_000, manager.retained_bytes()
    assert len(manager._jobs) < 6, "nothing was evicted; the byte budget did not apply"
    # Least-recently-used, as the count cap does. Nothing was reread in this loop,
    # so completion order is recency order.
    assert manager.get(ids[-1]) is not None, "the newest result was evicted"
    assert manager.get(ids[0]) is None, "the oldest result survived"


@pytest.mark.anyio
async def test_reading_a_terminal_record_refreshes_its_eviction_recency() -> None:
    manager = JobManager(max_jobs=2)
    first = await manager.submit(lambda: _payload(100))
    while first.state is not JobState.DONE:
        await _tick()
    second = await manager.submit(lambda: _payload(100))
    while second.state is not JobState.DONE:
        await _tick()

    assert manager.get(first.id) is first

    third = await manager.submit(lambda: _payload(100))
    while third.state is not JobState.DONE:
        await _tick()

    assert manager.get(first.id) is first
    assert manager.get(second.id) is None
    assert manager.get(third.id) is third


@pytest.mark.anyio
async def test_completion_makes_a_record_more_recent_than_an_earlier_completion() -> None:
    import threading

    release_first = threading.Event()
    manager = JobManager(max_jobs=1, max_in_flight=2)
    first = await manager.submit(lambda: release_first.wait(10))
    second = await manager.submit(lambda: _payload(100))

    while second.state is not JobState.DONE:
        await _tick()
    assert manager.get(second.id) is second

    release_first.set()
    while first.state is not JobState.DONE:
        await _tick()

    assert manager.get(first.id) is first
    assert manager.get(second.id) is None


@pytest.mark.anyio
async def test_an_unfinished_job_is_never_evicted_for_size() -> None:
    """The rule the count cap already kept, which the new bound must not break."""
    import threading

    started = threading.Event()
    release = threading.Event()

    def slow() -> _Payload:
        started.set()
        release.wait(timeout=10)
        return _payload(100)

    manager = JobManager(max_result_bytes=1)
    pending = await manager.submit(slow)
    # Polled, not `Event.wait()`: blocking this thread would stop the event loop that
    # has to schedule the worker in the first place.
    for _ in range(500):
        if started.is_set():
            break
        await _tick()
    assert started.is_set(), "the slow job never started"
    try:
        for _ in range(3):
            done = await manager.submit(lambda: _payload(5_000))
            while done.state not in (JobState.DONE, JobState.ERROR):
                await _tick()
            assert done.state is JobState.ERROR
        assert manager.get(pending.id) is not None, "an in-flight job was evicted"
    finally:
        release.set()


def test_the_default_budget_is_stated_in_bytes() -> None:
    assert DEFAULT_MAX_RESULT_BYTES == 256 * 1024 * 1024


@pytest.mark.parametrize("bad", [0, -1])
def test_a_nonsense_budget_is_refused(bad: int) -> None:
    with pytest.raises(ValueError, match="max_result_bytes"):
        JobManager(max_result_bytes=bad)


async def _tick() -> None:
    import asyncio

    await asyncio.sleep(0.01)


def test_the_operator_can_size_the_store() -> None:
    """The bounds are a memory decision, so they must be reachable from a deployment.

    This documentation was written before the parameter existed — the deployment guide
    described `create_app(jobs=JobManager(...))` in the same edit that added the byte
    budget, which is the "a documented flag that does not exist" defect this project
    keeps finding in other people's prose.
    """
    from alleleforge.web.api.app import create_app

    app = create_app(jobs=JobManager(max_jobs=3, max_result_bytes=1_234))
    assert app.state.jobs._max_jobs == 3
    assert app.state.jobs._max_result_bytes == 1_234


@pytest.mark.anyio
async def test_an_oversized_result_remains_pollable_over_http(reference) -> None:
    import httpx

    from alleleforge.web.api.app import create_app

    app = create_app(reference=reference, jobs=JobManager(max_result_bytes=1))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        submitted = await client.post(
            "/api/jobs/design",
            json={"variant": "chr2:71:A>C", "intent": "install", "max_per_chemistry": 1},
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]

        for _ in range(500):
            status = await client.get(f"/api/jobs/{job_id}")
            if status.json()["state"] in ("done", "error"):
                break
            await _tick()

        assert status.status_code == 200
        assert status.json()["state"] == "error"
        assert "1-byte retained-result limit" in status.json()["error"]
        result = await client.get(f"/api/jobs/{job_id}/result")
        assert result.status_code == 409
        assert result.json()["detail"] == status.json()["error"]


def test_a_deployment_that_says_nothing_gets_the_defaults() -> None:
    from alleleforge.web.api.app import create_app
    from alleleforge.web.api.jobs import DEFAULT_MAX_JOBS

    app = create_app()
    assert app.state.jobs._max_jobs == DEFAULT_MAX_JOBS
    assert app.state.jobs._max_result_bytes == DEFAULT_MAX_RESULT_BYTES
