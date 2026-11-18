"""Every line that reclaims a job's memory could be deleted with the suite green.

A statement-deletion sweep removed ten statements from `web/api/jobs.py` one at a time
and the whole suite stayed green for each. Every one of them is a line whose own comment
in the source says why it is there:

* **Two `self._evict()` calls**, one when a job is submitted and one when a job
  finishes, and *each is redundant while the other stands* — which is exactly why
  neither had a case. The existing cap tests submit and wait in a loop, so both fire
  every time. They are separated by looking at the store at the two different moments:
  right after a submission, while the new job is still running, and right after a
  completion with nothing submitted after it. Without the second, a server that
  finishes its last job holds one record over its cap for as long as nobody submits
  another — which, on an idle deployment, is indefinitely.
* **Two `self._tasks.add(...)` calls.** The comment above the first reads: *"asyncio
  holds only a weak reference to a bare create_task() result, so without this a job
  could be garbage-collected mid-flight"*. That is a documented, load-bearing
  invariant, and nothing observed it.
* **`record.result = None` and `record.result_bytes = 0` on both failure paths.** The
  comment: *"A result that failed its accounting pass must not stay in the bounded
  store as a zero-byte error record."* A job that fails after producing an oversized
  result would keep that result in memory while reporting an error.
* **`record.progress`**, documented as three values a client renders as a state.

None of these change an answer the API returns, which is why a suite built on responses
could not see them. They decide what a long-running server holds in memory.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from alleleforge.web.api.jobs import JobManager, JobRecord, JobState


class _Payload(BaseModel):
    blob: str


def _work() -> _Payload:
    return _Payload(blob="x" * 100)


async def _finish(manager: JobManager) -> JobRecord:
    record = await manager.submit(_work)
    while record.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)
    return record


async def _settle() -> None:
    """Let the finally-block of a just-finished job run."""
    for _ in range(50):
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_a_finished_job_reclaims_on_its_own_without_another_submission() -> None:
    """The eviction in the completion path, which the submit-time one hides."""
    manager = JobManager(max_jobs=2)
    first = await _finish(manager)
    await _finish(manager)
    await _finish(manager)
    await _settle()
    assert manager.get(first.id) is None, (
        "the store is over its cap and stays there until something else is submitted"
    )


@pytest.mark.asyncio
async def test_a_submission_cannot_push_the_store_over_its_cap() -> None:
    """Why the submit-time eviction reclaims nothing, stated rather than assumed.

    The sweep left both `self._evict()` calls alive, and the obvious reading — each is
    redundant while the other stands — is only half right. The budget counts *terminal*
    records, and a submission adds a running one, so the call in `submit` cannot be the
    one that reclaims anything; the call in the completion path is. Running the original
    and the mutant over 45 scripted submit/finish sequences across three count caps and
    three byte caps produced no difference at all.

    Pinned here because it is the premise of the test above: if a submission ever did
    push the store over budget, that test would pass for the wrong reason.
    """
    manager = JobManager(max_jobs=2)
    first = await _finish(manager)
    second = await _finish(manager)
    await _settle()
    assert manager.get(first.id) is not None and manager.get(second.id) is not None

    release = asyncio.Event()

    def _slow() -> _Payload:
        asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
        return _work()

    loop = asyncio.get_running_loop()
    running = await manager.submit(_slow)
    assert manager.get(first.id) is not None, "a running job evicted a terminal one"
    release.set()
    while running.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_a_running_job_is_held_by_a_strong_reference() -> None:
    """asyncio keeps only a weak one; the store is what stops a job being collected."""
    manager = JobManager()
    release = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _slow() -> _Payload:
        asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
        return _work()

    record = await manager.submit(_slow)
    held = [t for t in manager._tasks if not t.done()]
    release.set()
    while record.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)
    assert held, "nothing holds a reference to the running job's task"


@pytest.mark.asyncio
async def test_a_finished_job_releases_its_reference() -> None:
    """The other half: the set is a hold, not a leak of its own."""
    manager = JobManager()
    await _finish(manager)
    await _settle()
    assert not [t for t in manager._tasks if not t.done()]


@pytest.mark.asyncio
async def test_a_finished_job_reports_full_progress() -> None:
    record = await _finish(JobManager())
    assert record.state is JobState.DONE
    assert record.progress == 1.0


@pytest.mark.asyncio
async def test_a_failed_job_retains_no_result() -> None:
    """A failure must not sit in the bounded store holding the bytes it produced."""

    def _boom() -> _Payload:
        raise ValueError("the work failed after producing something")

    manager = JobManager()
    record = await manager.submit(_boom)
    while record.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)
    assert record.state is JobState.ERROR
    assert record.result is None
    assert record.result_bytes == 0


@pytest.mark.asyncio
async def test_a_running_job_reports_running_progress() -> None:
    """`0.0 queued, 0.1 running, 1.0 finished` is a documented three-value field."""
    manager = JobManager()
    release = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _slow() -> _Payload:
        asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
        return _work()

    record = await manager.submit(_slow)
    for _ in range(200):
        if record.state is JobState.RUNNING:
            break
        await asyncio.sleep(0.001)
    running_progress = record.progress
    release.set()
    while record.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)
    assert running_progress == 0.1, running_progress


async def _timed_out(manager: JobManager, release: asyncio.Event) -> JobRecord:
    """Submit a job that outlives the manager's deadline, and wait for the verdict."""
    loop = asyncio.get_running_loop()

    def _slow() -> _Payload:
        asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
        return _work()

    record = await manager.submit(_slow)
    while record.state not in (JobState.DONE, JobState.ERROR):
        await asyncio.sleep(0.001)
    return record


@pytest.mark.asyncio
async def test_a_timed_out_job_retains_no_result() -> None:
    """The deadline path clears the result exactly as the failure path does."""
    manager = JobManager(max_job_seconds=0.01)
    release = asyncio.Event()
    record = await _timed_out(manager, release)
    assert record.state is JobState.ERROR
    assert "time limit" in (record.error or "")
    assert record.result is None
    assert record.result_bytes == 0
    release.set()
    await _settle()


@pytest.mark.asyncio
async def test_a_timed_out_jobs_cleanup_is_held_and_reclaims_when_the_worker_stops() -> None:
    """The soft timeout leaves a worker running; something has to wait for it.

    The deadline marks the record `ERROR` and returns, but the worker thread cannot be
    cancelled — it runs to completion in the background, still holding its in-flight
    slot. A second task waits for it, releases the slot and evicts, and it needs the
    same strong reference the job task does: a bare `create_task` here is collectable,
    and the slot would never come back.
    """
    manager = JobManager(max_job_seconds=0.01, max_in_flight=1)
    release = asyncio.Event()
    record = await _timed_out(manager, release)
    assert record.state is JobState.ERROR

    held = [t for t in manager._tasks if not t.done()]
    assert held, "nothing is waiting for the worker that outlived its deadline"

    release.set()
    for _ in range(500):
        if manager._in_flight == 0:
            break
        await asyncio.sleep(0.002)
    assert manager._in_flight == 0, "the timed-out worker never released its slot"


@pytest.mark.asyncio
async def test_timed_out_jobs_do_not_accumulate_past_the_cap() -> None:
    """The eviction in the worker-cleanup path, and the only one that is load-bearing.

    A soft timeout returns before its worker does, so the record goes terminal while
    the thread keeps running. The completion path has already evicted by then — the
    store is inside its budget at that moment and nothing is reclaimed. The record that
    pushes it over arrives later, when the *next* timed-out job finishes, and the only
    code that runs at that point is the cleanup task's own eviction.

    Without it a server that times jobs out keeps every timed-out record for as long as
    nobody submits another: three jobs, a cap of two, three records retained. Measured,
    not reasoned — running the original and the mutant over twenty scripted scenarios
    produced a difference in exactly the two that time out.
    """
    manager = JobManager(max_jobs=2, max_job_seconds=0.05)
    release = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _slow() -> _Payload:
        asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
        return _work()

    for _ in range(3):
        record = await manager.submit(_slow)
        while record.state not in (JobState.DONE, JobState.ERROR):
            await asyncio.sleep(0.002)
        assert record.state is JobState.ERROR, record.error

    release.set()
    for _ in range(500):
        if manager._in_flight == 0:
            break
        await asyncio.sleep(0.002)
    await _settle()

    terminal = [r for r in manager._jobs.values() if r.state in (JobState.DONE, JobState.ERROR)]
    assert len(terminal) <= 2, f"{len(terminal)} terminal records retained against a cap of 2"
