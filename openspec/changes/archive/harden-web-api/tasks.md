# Tasks

## 1. Bound request size and concurrency
- [x] 1.1 Add a maximum `variants` length to the batch request schema; reject over-large
      requests at the boundary with 422.
- [x] 1.2 Add a max-in-flight-job semaphore; return 429 (or 503) when saturated.
- [x] 1.3 Tests for both limits.

## 2. Bound the job store
- [x] 2.1 Add a TTL / LRU eviction to `JobManager` so completed records are reclaimed.
      *(Size-bounded LRU eviction of terminal records; TTL not added.)*
- [x] 2.2 Test: the store stays bounded past the cap.

## 3. Optional auth on non-loopback binds
- [x] 3.1 Require an API token when bound to a non-loopback host; leave localhost open.
- [x] 3.2 Tests: token required off-loopback, not on localhost.

## 4. Per-request timeout and durability seam
- [x] 4.1 Add a per-request timeout to the synchronous design/batch paths.
      *(Ships as an optional per-job wall-clock limit on `JobManager` — a soft
      timeout marking an over-limit job ERROR; the sync request paths inherit the
      async job path.)*
- [x] 4.2 Document the durable-job-backend seam behind the `JobManager` interface.

## 5. Reconcile
- [x] 5.1 `make ci` green; default localhost behavior unchanged.
