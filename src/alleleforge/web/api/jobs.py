"""An in-process async job queue for long-running design requests.

The default AlleleForge deployment is single-user and local, so the "task queue"
is deliberately in-process: an :class:`asyncio` task per job, with the work run
in a worker thread so the event loop stays responsive. Jobs expose a state
(pending → running → done/error) and a coarse progress fraction through a
status endpoint.

**Durable-backend seam.** :class:`JobManager`'s ``submit(work) -> JobRecord`` and
``get(job_id) -> JobRecord | None`` are the whole interface the API depends on, so
a multi-user or restart-surviving deployment can back them with a real broker /
persistent store (the CLI's resumable-manifest model in
:mod:`alleleforge.design.cohort` is the shape a durable job record would take)
without touching any endpoint. Today the store is in-memory, so a restart loses
in-flight job state — bounded and concurrency-capped, but not yet durable.

No work here ever makes a network call — the queue only schedules library
functions that run entirely on local data.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from alleleforge.web.api.models import JobState

#: Default cap on retained job records. A long-lived server would otherwise grow
#: ``_jobs`` without bound; only *terminal* (done/error) records are evicted, so an
#: in-flight job is never dropped.
DEFAULT_MAX_JOBS = 1000

#: Default cap on concurrently in-flight (pending/running) jobs. Each job spawns a
#: worker thread, so an uncapped submission path is a thread-pool amplifier; past
#: this cap :meth:`JobManager.submit` refuses new work until a job finishes.
DEFAULT_MAX_IN_FLIGHT = 16


class JobCapacityError(RuntimeError):
    """Raised by :meth:`JobManager.submit` when the in-flight cap is reached."""


@dataclass
class JobRecord:
    """The mutable state of one async job."""

    id: str
    state: JobState = JobState.PENDING
    progress: float = 0.0
    result: Any = None
    error: str | None = None


class JobManager:
    """Schedules and tracks in-process async jobs (one event loop, N threads)."""

    def __init__(
        self,
        *,
        max_jobs: int = DEFAULT_MAX_JOBS,
        max_in_flight: int = DEFAULT_MAX_IN_FLIGHT,
        max_job_seconds: float | None = None,
    ) -> None:
        """Initialise an empty, size- and concurrency-bounded job store.

        Args:
            max_jobs: Maximum retained *terminal* job records. Older completed
                records are evicted oldest-first past this cap; in-flight jobs are
                never evicted.
            max_in_flight: Maximum concurrently in-flight (pending/running) jobs;
                :meth:`submit` raises :class:`JobCapacityError` past this cap.
            max_job_seconds: Optional per-job wall-clock limit. A job that exceeds
                it is marked ``ERROR`` (a soft timeout: the worker thread cannot be
                cancelled, so it runs to completion in the background, but its
                result is discarded and the caller sees the timeout). ``None``
                (default) leaves jobs unbounded, as before.

        Raises:
            ValueError: If either cap is not positive, or the timeout is not positive.
        """
        if max_jobs < 1:
            raise ValueError(f"max_jobs must be positive; got {max_jobs}")
        if max_in_flight < 1:
            raise ValueError(f"max_in_flight must be positive; got {max_in_flight}")
        if max_job_seconds is not None and max_job_seconds <= 0:
            raise ValueError(f"max_job_seconds must be positive; got {max_job_seconds}")
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._max_jobs = max_jobs
        self._max_in_flight = max_in_flight
        self._max_job_seconds = max_job_seconds
        self._in_flight = 0

    def get(self, job_id: str) -> JobRecord | None:
        """Return the record for ``job_id``, or ``None`` if unknown."""
        return self._jobs.get(job_id)

    def _evict(self) -> None:
        """Evict oldest terminal records until the store is within its cap.

        Only ``DONE``/``ERROR`` records are removed, oldest-submitted first (dict
        insertion order), so an unbounded backlog of finished jobs cannot leak
        memory while a running or pending job is always retained.
        """
        if len(self._jobs) <= self._max_jobs:
            return
        for jid, record in list(self._jobs.items()):
            if len(self._jobs) <= self._max_jobs:
                break
            if record.state in (JobState.DONE, JobState.ERROR):
                del self._jobs[jid]

    async def submit(self, work: Callable[[], Any]) -> JobRecord:
        """Accept ``work`` (a zero-arg callable), schedule it, and return its record.

        The callable runs in a worker thread; ``work`` should be a self-contained
        library call. The returned record updates in place as the job runs.

        Raises:
            JobCapacityError: If the in-flight-job cap is already reached, so a
                caller cannot exhaust the worker threadpool.
        """
        if self._in_flight >= self._max_in_flight:
            raise JobCapacityError(
                f"server at capacity: {self._in_flight} job(s) in flight "
                f"(max {self._max_in_flight}); retry once one finishes"
            )
        record = JobRecord(id=uuid.uuid4().hex)
        self._jobs[record.id] = record
        self._in_flight += 1
        self._evict()  # reclaim old terminal records this submission may push over the cap

        async def _run() -> None:
            record.state = JobState.RUNNING
            record.progress = 0.1
            try:
                if self._max_job_seconds is not None:
                    record.result = await asyncio.wait_for(
                        asyncio.to_thread(work), self._max_job_seconds
                    )
                else:
                    record.result = await asyncio.to_thread(work)
                record.progress = 1.0
                record.state = JobState.DONE
            except TimeoutError:
                record.error = f"job exceeded the {self._max_job_seconds}s time limit"
                record.state = JobState.ERROR
            except Exception as exc:  # noqa: BLE001 - report any failure to the client
                record.error = f"{type(exc).__name__}: {exc}"
                record.state = JobState.ERROR
            finally:
                # This record is now terminal; free its slot and reclaim any backlog.
                self._in_flight -= 1
                self._evict()

        # Keep a strong reference until the task finishes. asyncio holds only a
        # weak reference to a bare create_task() result, so without this a job
        # could be garbage-collected mid-flight; the job *record* in the store
        # does not keep the running task alive.
        task = asyncio.create_task(_run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record
