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
