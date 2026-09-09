"""A cap on the *number* of retained jobs is not a bound on memory.

`JobManager` evicted oldest-terminal-first past a thousand records, on the reasoning that
"a long-lived server would otherwise grow `_jobs` without bound". That was written when a
record held a polling envelope. A finished **design** job now keeps the ranked menu *and*
the report built from it — measured at 1.25 MiB of JSON for a 200-candidate menu on a
30 kb contig — and the served page submits every single-variant design through this store,
so the count cap permits well over a gigabyte of retained results.

Both bounds apply now, whichever is reached first, and neither ever evicts an in-flight
job. The size is measured once, when the work finishes, by serializing what the record
holds: the manager schedules opaque callables and must not learn what a design is, so it
introspects — anything with `model_dump_json`, and any dataclass by summing its fields,
which is the shape of both finished-result types.
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import BaseModel

from alleleforge.web.api.jobs import DEFAULT_MAX_RESULT_BYTES, JobManager, JobState


class _Payload(BaseModel):
    blob: str


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
    # Oldest-first, as the count cap does.
    assert manager.get(ids[-1]) is not None, "the newest result was evicted"
    assert manager.get(ids[0]) is None, "the oldest result survived"


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
            while done.state is not JobState.DONE:
                await _tick()
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


def test_a_deployment_that_says_nothing_gets_the_defaults() -> None:
    from alleleforge.web.api.app import create_app
    from alleleforge.web.api.jobs import DEFAULT_MAX_JOBS

    app = create_app()
    assert app.state.jobs._max_jobs == DEFAULT_MAX_JOBS
    assert app.state.jobs._max_result_bytes == DEFAULT_MAX_RESULT_BYTES
