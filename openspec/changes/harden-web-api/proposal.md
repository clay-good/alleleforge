# Harden the web API for safe exposure

## Why

The web layer is a faithful thin shell, but it is only safe on loopback today, which
limits who can offer AlleleForge as a shared service:

- **No authentication, rate limiting, or request-size cap.** Any caller can flood
  `/api/jobs/design` or submit an unbounded `POST /api/batch` — the `variants` list has
  only `min_length=1`, no maximum (`web/api/models.py:70-71`).
- **Unbounded, non-durable job store.** `JobManager._jobs` grows without eviction or TTL
  (`web/api/jobs.py:41, 55`); a long-lived server leaks memory. Each submission spawns a
  thread via `asyncio.to_thread` with no concurrency cap, so job submission is an unbounded
  thread-pool amplifier, and a restart loses all job state (a resumable manifest exists for
  the CLI but not here).

None of this changes the core "compute is local, no sequence data leaves the box"
invariant; it makes that invariant safe to expose.

## What Changes

- Add a **request-size cap** on `/api/batch` (a maximum `variants` length) and a **maximum
  in-flight job** semaphore, so submission cannot exhaust memory or threads.
- Add a **job TTL / LRU eviction** so the job store is bounded.
- Add an **optional API token** required when the server is bound to a non-loopback host
  (off by default for localhost, so the local dev experience is unchanged).
- Add a **per-request timeout** on the synchronous design/batch paths.
- Document the durable-job-backend seam so the existing `JobManager` interface can later be
  backed by a resumable store.

## Status (partial)

Task 1.1 has shipped: the batch request schema now caps `variants` at
`MAX_BATCH_VARIANTS` (1000), so an over-large cohort is rejected at the boundary
with 422 before any work is scheduled — a shared deployment can no longer be
flooded with an unbounded batch. Still open: the max-in-flight-job semaphore
(task 1.2), the job-store TTL/LRU eviction (task 2), optional off-loopback auth
(task 3), and the per-request timeout + durability seam (task 4). The default
localhost experience is unchanged.

## Impact

- Specs: `web-api` (ADDED resource-safety requirements: size cap, job bounds, optional
  auth, timeout).
- Code: `web/api/app.py`, `web/api/jobs.py`, `web/api/models.py`.
- Tests: an over-large batch is rejected at the boundary; the job store evicts past its
  cap; a token is required on a non-loopback bind and not on localhost; a run past the
  timeout is aborted cleanly. The default localhost experience is unchanged.
