"""An in-process async job queue for long-running design requests.

The default AlleleForge deployment is single-user and local, so the "task queue"
is deliberately in-process: an :class:`asyncio` task per job, with the work run
in a worker thread so the event loop stays responsive. Jobs expose a state
(pending → running → done/error) and a coarse progress fraction through a
status endpoint. A production multi-user deployment can swap this for a real
broker behind the same interface; nothing else in the API changes.

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

    def __init__(self, *, max_jobs: int = DEFAULT_MAX_JOBS) -> None:
        """Initialise an empty, size-bounded job store.

        Args:
            max_jobs: Maximum retained *terminal* job records. Older completed
                records are evicted oldest-first past this cap; in-flight jobs are
                never evicted.

        Raises:
            ValueError: If ``max_jobs`` is not positive.
        """
        if max_jobs < 1:
            raise ValueError(f"max_jobs must be positive; got {max_jobs}")
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._max_jobs = max_jobs

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
        """
        record = JobRecord(id=uuid.uuid4().hex)
        self._jobs[record.id] = record
        self._evict()  # reclaim old terminal records this submission may push over the cap

        async def _run() -> None:
            record.state = JobState.RUNNING
            record.progress = 0.1
            try:
                record.result = await asyncio.to_thread(work)
                record.progress = 1.0
                record.state = JobState.DONE
            except Exception as exc:  # noqa: BLE001 - report any failure to the client
                record.error = f"{type(exc).__name__}: {exc}"
                record.state = JobState.ERROR
            finally:
                # This record is now terminal; reclaim any backlog over the cap.
                self._evict()

        # Keep a strong reference until the task finishes. asyncio holds only a
        # weak reference to a bare create_task() result, so without this a job
        # could be garbage-collected mid-flight; the job *record* in the store
        # does not keep the running task alive.
        task = asyncio.create_task(_run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record
