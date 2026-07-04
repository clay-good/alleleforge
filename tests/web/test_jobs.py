"""Unit tests for the in-process async JobManager (Phase 13)."""

from __future__ import annotations

import asyncio

from alleleforge.web.api.jobs import JobManager
from alleleforge.web.api.models import JobState


async def _drain(mgr: JobManager, ids: list[str]) -> None:
    """Yield to the loop until every job has finished (or fail after a bound)."""
    for _ in range(10_000):
        records = [mgr.get(i) for i in ids]
        if all(r is not None and r.state in (JobState.DONE, JobState.ERROR) for r in records):
            return
        await asyncio.sleep(0)
    raise AssertionError("jobs did not finish")


async def _settle_tasks(mgr: JobManager) -> None:
    """Yield until the done-callbacks have discarded finished tasks (eventually)."""
    for _ in range(10_000):
        if not mgr._tasks:
            return
        await asyncio.sleep(0)
    raise AssertionError("task tracking set was not released")


async def test_jobs_complete_and_tasks_are_released() -> None:
    mgr = JobManager()
    records = [await mgr.submit(lambda v=v: v * 2) for v in range(5)]
    await _drain(mgr, [r.id for r in records])

    done = [mgr.get(r.id) for r in records]
    assert all(r is not None and r.state is JobState.DONE for r in done)
    assert [r.result for r in done if r is not None] == [0, 2, 4, 6, 8]
    # The done-callback discards each finished task, so the tracking set is bounded
    # — and holding the strong reference is what kept the jobs alive to completion
    # (asyncio only weakly references a bare create_task result).
    await _settle_tasks(mgr)


async def test_job_error_is_captured_not_raised() -> None:
    mgr = JobManager()

    def _boom() -> None:
        raise ValueError("kaboom")

    record = await mgr.submit(_boom)
    await _drain(mgr, [record.id])
    final = mgr.get(record.id)
    assert final is not None
    assert final.state is JobState.ERROR
    assert final.error is not None and "kaboom" in final.error
    await _settle_tasks(mgr)  # a failed task is released too


async def test_job_store_is_bounded_by_max_jobs() -> None:
    # A long-lived server must not grow the job store without bound; only terminal
    # records are evicted (oldest-first), never an in-flight job.
    mgr = JobManager(max_jobs=3)
    records = [await mgr.submit(lambda v=v: v) for v in range(10)]
    await _settle_tasks(mgr)
    for _ in range(1000):  # let the final eviction run
        if len(mgr._jobs) <= 3:
            break
        await asyncio.sleep(0)
    assert len(mgr._jobs) <= 3
    assert mgr.get(records[-1].id) is not None  # the most recent survives
    assert mgr.get(records[0].id) is None  # the oldest was evicted


async def test_max_jobs_must_be_positive() -> None:
    import pytest

    with pytest.raises(ValueError, match="must be positive"):
        JobManager(max_jobs=0)


async def test_in_flight_cap_refuses_when_saturated() -> None:
    import pytest

    from alleleforge.web.api.jobs import JobCapacityError

    # With one in-flight slot, a second submit is refused before the first job
    # (whose slot is still held) finishes — so the worker threadpool can't be
    # exhausted by a submission flood.
    mgr = JobManager(max_in_flight=1)
    r1 = await mgr.submit(lambda: 1)  # takes the only slot (counted synchronously)
    with pytest.raises(JobCapacityError, match="at capacity"):
        await mgr.submit(lambda: 2)
    await _drain(mgr, [r1.id])  # first job finishes, freeing the slot
    r3 = await mgr.submit(lambda: 3)  # now admitted
    await _drain(mgr, [r3.id])
    assert mgr.get(r3.id) is not None


async def test_max_in_flight_must_be_positive() -> None:
    import pytest

    with pytest.raises(ValueError, match="max_in_flight must be positive"):
        JobManager(max_in_flight=0)
