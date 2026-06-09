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

    def __init__(self) -> None:
        """Initialise an empty job store."""
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def get(self, job_id: str) -> JobRecord | None:
        """Return the record for ``job_id``, or ``None`` if unknown."""
        return self._jobs.get(job_id)

    async def submit(self, work: Callable[[], Any]) -> JobRecord:
        """Accept ``work`` (a zero-arg callable), schedule it, and return its record.

        The callable runs in a worker thread; ``work`` should be a self-contained
        library call. The returned record updates in place as the job runs.
        """
        record = JobRecord(id=uuid.uuid4().hex)
        self._jobs[record.id] = record

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

        # Keep a strong reference until the task finishes. asyncio holds only a
        # weak reference to a bare create_task() result, so without this a job
        # could be garbage-collected mid-flight; the job *record* in the store
        # does not keep the running task alive.
        task = asyncio.create_task(_run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record
