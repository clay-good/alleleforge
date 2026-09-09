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
import dataclasses
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from alleleforge.errors import reason
from alleleforge.web.api.models import JobState

#: Default cap on retained job records. A long-lived server would otherwise grow
#: ``_jobs`` without bound; only *terminal* (done/error) records are evicted, so an
#: in-flight job is never dropped.
DEFAULT_MAX_JOBS = 1000

#: Default cap on the bytes those retained records hold.
#:
#: A count is not a bound on memory. A finished design job keeps the ranked menu *and*
#: the report built from it — measured at **1.25 MiB** of JSON for a 200-candidate menu
#: on a small contig — so a thousand of them is over a gigabyte, and the served page now
#: submits every single-variant design through this store. The count cap was written when
#: a record held a polling envelope; it says nothing about what one weighs.
#:
#: 256 MiB is roughly two hundred results of that size. Both bounds apply: whichever is
#: reached first evicts oldest-terminal-first, and neither ever drops an in-flight job.
DEFAULT_MAX_RESULT_BYTES = 256 * 1024 * 1024

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
    #: Bytes this record's result holds, measured once when it finishes. Zero until then,
    #: and zero for a result that carries no serializable payload.
    result_bytes: int = 0


class JobManager:
    """Schedules and tracks in-process async jobs (one event loop, N threads)."""

    def __init__(
        self,
        *,
        max_jobs: int = DEFAULT_MAX_JOBS,
        max_in_flight: int = DEFAULT_MAX_IN_FLIGHT,
        max_job_seconds: float | None = None,
        max_result_bytes: int = DEFAULT_MAX_RESULT_BYTES,
    ) -> None:
        """Initialise an empty, size- and concurrency-bounded job store.

        Args:
            max_jobs: Maximum retained *terminal* job records. Older completed
                records are evicted oldest-first past this cap; in-flight jobs are
                never evicted.
            max_in_flight: Maximum concurrently in-flight (pending/running) jobs;
                :meth:`submit` raises :class:`JobCapacityError` past this cap.
            max_result_bytes: Maximum bytes the retained results may hold together.
                Evicted oldest-terminal-first like ``max_jobs``, and applied alongside
                it: whichever bound is reached first evicts.
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
        if max_result_bytes < 1:
            raise ValueError(f"max_result_bytes must be positive; got {max_result_bytes}")
        if max_job_seconds is not None and max_job_seconds <= 0:
            raise ValueError(f"max_job_seconds must be positive; got {max_job_seconds}")
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._max_jobs = max_jobs
        self._max_result_bytes = max_result_bytes
        self._max_in_flight = max_in_flight
        self._max_job_seconds = max_job_seconds
        self._in_flight = 0

    @staticmethod
    def _measure(result: Any) -> int:
        """Return the bytes ``result`` holds, as the length of its JSON.

        Introspective on purpose: the manager schedules opaque callables and must not
        learn what a design or a cohort is. Anything exposing `model_dump_json` is
        measured; a dataclass is measured by summing over its fields, which is what a
        finished design (menu + report) and a finished cohort (report + response) are.
        Serialization is not free — it is one extra pass, once, in the worker thread
        after the work is done, and it is the only honest way to bound a store whose
        contents this module cannot see.
        """
        dump = getattr(result, "model_dump_json", None)
        if callable(dump):
            return len(dump())
        if dataclasses.is_dataclass(result) and not isinstance(result, type):
            return sum(
                JobManager._measure(getattr(result, field.name))
                for field in dataclasses.fields(result)
            )
        return 0

    def retained_bytes(self) -> int:
        """Return the bytes the retained results hold."""
        return sum(record.result_bytes for record in self._jobs.values())

    def get(self, job_id: str) -> JobRecord | None:
        """Return the record for ``job_id``, or ``None`` if unknown."""
        return self._jobs.get(job_id)

    def _over_budget(self) -> bool:
        """Return whether either bound is exceeded."""
        return len(self._jobs) > self._max_jobs or self.retained_bytes() > self._max_result_bytes

    def _evict(self) -> None:
        """Evict oldest terminal records until the store is within both caps.

        Only ``DONE``/``ERROR`` records are removed, oldest-submitted first (dict
        insertion order), so an unbounded backlog of finished jobs cannot leak
        memory while a running or pending job is always retained.

        Two caps, because a count is not a bound on memory: a finished design keeps the
        ranked menu and the report built from it, over a megabyte for an ordinary menu,
        and the count cap was written when a record held a polling envelope.
        """
        if not self._over_budget():
            return
        for jid, record in list(self._jobs.items()):
            if not self._over_budget():
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
                record.result_bytes = self._measure(record.result)
                record.progress = 1.0
                record.state = JobState.DONE
            except TimeoutError:
                record.error = f"job exceeded the {self._max_job_seconds}s time limit"
                record.state = JobState.ERROR
            except Exception as exc:  # noqa: BLE001 - report any failure to the client
                # The same failure, submitted synchronously, comes back as a clean
                # `{"detail": "unrecognized variant input: ..."}`. Through a job it read
                # `HTTPException: 422: unrecognized variant input: ...` — the framework's
                # class name and an HTTP status glued to the front of the one sentence a
                # caller can act on, in a field whose whole job is carrying that sentence.
                # The status is already the shape of the *response*; it does not belong
                # inside the reason. Any other exception keeps its type, which is a real
                # clue when the message alone is opaque.
                detail = getattr(exc, "detail", None)
                record.error = str(detail) if detail else f"{type(exc).__name__}: {reason(exc)}"
                record.state = JobState.ERROR
            finally:
                # Progress is documented as three values — "0.0 queued, 0.1 running, 1.0
                # finished" — and clients are told to render it as a state rather than a
                # percentage. A failed or timed-out job used to keep the 0.1 it was given
                # on entry, so a job that had finished and would never advance reported
                # the running value in the one field its own documentation says to
                # display. `finished` is what this branch means, error or not; `state`
                # carries which kind.
                record.progress = 1.0
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
