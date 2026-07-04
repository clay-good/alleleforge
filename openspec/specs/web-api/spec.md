# web-api Specification

## Purpose

Expose a thin async HTTP layer over the same library functions, schema-validated in and
out, with a strict "all compute is local, no sequence data leaves the box" invariant and a
research-use disclaimer on the surface.

## Requirements

### Requirement: A schema-validated endpoint surface

The service SHALL expose health, resolve, design, async design jobs, batch, off-target,
and data/bench read endpoints; every request SHALL be validated by a frozen schema, and a
variant parse error SHALL map to HTTP 422.

#### Scenario: Invalid input
- **WHEN** an off-target request has an invalid spacer
- **THEN** the service returns 422

### Requirement: Genome-dependent endpoints fail clearly when unconfigured

Endpoints needing a reference SHALL return HTTP 503 with a remediation message until a
reference is configured.

#### Scenario: No reference
- **WHEN** a design request arrives with no reference configured
- **THEN** the service returns 503 with how to configure one

### Requirement: Numeric request fields are bounded

Numeric request fields SHALL be bounded at the schema boundary: mismatches 0–8, bulges
0–4, thresholds and MAF 0–1, max-per-chemistry at least 1, weights of length exactly 4,
and a non-empty variant list.

#### Scenario: Wrong weights length
- **WHEN** a request supplies a weights list whose length is not 4
- **THEN** it is rejected at the boundary with 422 before any compute

### Requirement: Async jobs have a defined lifecycle

Async design jobs SHALL follow `pending → running → done|error`, exposing state,
progress, and error, and returning the serialized report when done; an unknown job id
SHALL return 404, and a job's exception SHALL be captured into its record without crashing
the server loop.

#### Scenario: Job failure
- **WHEN** a submitted job's work raises
- **THEN** the record transitions to error with the exception type and message, and the
  poll returns that error with a null result

### Requirement: Research-use and local-compute are stated

Responses SHALL carry the research-use disclaimer where user-facing, and the API
description SHALL state research-use-only and local-compute; no endpoint SHALL transmit
sequence data off the host.

#### Scenario: Health disclaimer
- **WHEN** the health endpoint is queried
- **THEN** the response carries the research-use disclaimer

### Requirement: Requests and jobs are resource-bounded

The service SHALL bound resource consumption so it is safe to expose beyond loopback: the
batch endpoint SHALL cap the number of variants per request and reject an over-large
request at the boundary; the job manager SHALL cap in-flight jobs and reject beyond the
cap; the job store SHALL bound its size with LRU eviction of terminal records so completed
records are reclaimed; and a job MAY carry a wall-clock limit past which it is marked
errored.

#### Scenario: Over-large batch
- **WHEN** a batch request exceeds the maximum variant count
- **THEN** it is rejected at the boundary before any compute

#### Scenario: Saturated in-flight cap
- **WHEN** the number of in-flight jobs is already at the cap
- **THEN** a new submission is rejected (429) rather than exhausting the threadpool

#### Scenario: Job store stays bounded
- **WHEN** many jobs complete over a long-lived server
- **THEN** the job store evicts old terminal records rather than growing without bound

### Requirement: Non-loopback binds require authentication

When the server is bound to a non-loopback host, the service SHALL require an API token on
requests; when bound to localhost it MAY run without a token so the local development
experience is unchanged.

#### Scenario: Off-loopback without a token
- **WHEN** the server is bound to a non-loopback host and a request arrives without a valid
  token
- **THEN** the request is rejected as unauthorized

#### Scenario: Localhost unchanged
- **WHEN** the server is bound to localhost
- **THEN** requests are served without a token
