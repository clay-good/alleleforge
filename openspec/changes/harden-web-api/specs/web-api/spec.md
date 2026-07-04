# web-api (delta)

## ADDED Requirements

### Requirement: Requests and jobs are resource-bounded

The service SHALL bound resource consumption so it is safe to expose beyond loopback: the
batch endpoint SHALL cap the number of variants per request and reject an over-large
request at the boundary; the job manager SHALL cap in-flight jobs and reject or queue
beyond the cap; and the job store SHALL bound its size with a TTL or LRU eviction so
completed records are reclaimed.

#### Scenario: Over-large batch
- **WHEN** a batch request exceeds the maximum variant count
- **THEN** it is rejected at the boundary before any compute

#### Scenario: Job store stays bounded
- **WHEN** many jobs complete over a long-lived server
- **THEN** the job store evicts old records rather than growing without bound

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
