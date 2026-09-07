# web-api Specification

## Purpose

Expose a thin async HTTP layer over the same library functions, schema-validated in and
out, with a strict "all compute is local, no sequence data leaves the box" invariant and a
research-use disclaimer on the surface.

## Requirements

### Requirement: The population-aware search is reachable over HTTP

Population-aware off-target nomination is the capability this tool exists for, so it
SHALL be reachable from the web shell as well as the CLI. The population source is
**operator-configured** — `create_app(gnomad=...)` or `ALLELEFORGE_GNOMAD_TSV` — because
a client-supplied path would be an arbitrary file read on the server. Since a client
cannot supply it, `GET /api/health` SHALL report whether one is configured: without it
every scan is reference-only whatever ancestry labels a request carries, and an empty
breakdown reads as "no risk found" rather than "nothing was searched".

#### Scenario: A configured deployment
- **WHEN** a population source is configured and a request asks for ancestry labels
- **THEN** population-origin sites are nominated with their per-ancestry frequencies

#### Scenario: An unconfigured deployment
- **WHEN** no source is configured
- **THEN** `gnomad_loaded` is false and the search description states that nothing was
  measured, without naming a flag that belongs to a different shell

The haplotype panel is the population source's sibling and SHALL be configurable the same
way (`create_app(haplotypes=...)` or `ALLELEFORGE_HAPLOTYPES`), and reported the same way,
since wiring one ancestry source and not the other leaves the capability half-reachable.

#### Scenario: A configured haplotype panel
- **WHEN** a panel is configured
- **THEN** the haplotype-aware pass runs for API callers and `haplotypes_loaded` is true

A source that was configured but could not be read SHALL be distinguishable from one that
was never configured. Both leave the capability unavailable; only one is a deployment
mistake, and the operator is the only party who can fix it.

#### Scenario: A configured source that fails to load
- **WHEN** an environment variable names a source that cannot be read
- **THEN** `GET /api/health` reports the reason under `source_errors`, rather than the
  same response an unconfigured deployment returns

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
and a non-empty variant list. A well-typed but semantically-invalid weights vector (a
negative, all-zero, or non-finite component that the length check cannot catch) SHALL map to
`422` — a bad request — not leak a `500`: the endpoint catches the `RankingWeights`
validation error and returns 422 rather than a server fault.

#### Scenario: Wrong weights length
- **WHEN** a request supplies a weights list whose length is not 4
- **THEN** it is rejected at the boundary with 422 before any compute

#### Scenario: Invalid weight values
- **WHEN** a `/api/design` or `/api/batch` request supplies four weights that are negative,
  all-zero, or non-finite
- **THEN** the service returns `422` (a bad request), never a `500`

### Requirement: String and list request fields are size-capped

Every string and list request field SHALL be bounded at the schema boundary — not only the
batch variant *count*: a variant/spacer/PAM/build string and the populations/chemistries
lists (and their elements) SHALL carry a generous maximum far above any legitimate input, so
a within-count request cannot smuggle a multi-megabyte field into genome-scale compute. This
is the request-size cap that bounds the work a caller can queue in one request.

#### Scenario: Oversized field
- **WHEN** a request supplies a spacer, variant, or populations list longer than its cap
- **THEN** it is rejected at the boundary with 422 before any scan, while any legitimate
  (real-world-sized) input is accepted unchanged

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

### Requirement: The off-target envelope says whose specificity it is

`POST /api/offtarget` SHALL accept the spacer's own locus — in the same shape a
reported site's `locus` has, so a client can hand one straight back — and exclude it
when given. The response SHALL carry `on_target_excluded`, because without it
`specificity` is not the quantity a design report prints under the same name. A
malformed locus SHALL be a 422, never a silently un-excluded search.

#### Scenario: No locus supplied
- **WHEN** the request omits `on_target`
- **THEN** the response reports `on_target_excluded: false` and the guide's own
  perfect match is among the sites

#### Scenario: A reported locus handed back
- **WHEN** a site's `locus` from a previous response is sent as `on_target`
- **THEN** that site is dropped, `on_target_excluded` is `true`, and the specificity
  is no lower than before

#### Scenario: Malformed locus
- **WHEN** `on_target` is not a valid interval
- **THEN** the request is rejected with 422

### Requirement: A scan can be scoped over HTTP

`POST /api/design` and `POST /api/offtarget` SHALL accept a list of intervals
restricting the off-target search. A restriction is *data*, not a filesystem path,
so it carries none of the server-side file-read risk that keeps the file-backed
safety inputs off this surface. A region SHALL NOT require a strand — a restriction
covers both — while still accepting a `locus` copied from a previous response. An
empty interval SHALL be rejected, since a zero-width restriction would scope the
scan to nothing and report every guide spotless.

#### Scenario: Region excluding the site
- **WHEN** the search is restricted to an interval that does not contain a known site
- **THEN** the site is not reported

#### Scenario: Empty interval
- **WHEN** a region's end is not after its start
- **THEN** the request is rejected with 422

### Requirement: The served frontend escapes everything it inserts

A cohort row is built from user input — the pasted variant list, and exception messages
quoting it back — and inserted with `innerHTML`. Every value the frontend interpolates
into markup SHALL be escaped at the boundary.

#### Scenario: A markup-bearing variant line
- **WHEN** a cohort list contains a line with HTML in it
- **THEN** it is displayed as text and nothing in it executes

### Requirement: The browser's cohort table honours the uncertainty contract

The cohort tab renders its own table rather than embedding a server-rendered report, so
the contract has to be met there too: an efficiency estimate SHALL appear with its
interval and its in-distribution status, and the recommended candidate's hazards SHALL be
shown. This is the triage view for users who will not open a terminal.

#### Scenario: An out-of-distribution recommendation
- **WHEN** a cohort row's best candidate has an out-of-distribution efficiency
- **THEN** the browser table shows the interval and marks it, rather than showing the
  estimate alone

### Requirement: An API result carries the qualifications its CLI equivalent prints

Where an endpoint answers the same question as a CLI command, its response SHALL carry
the qualifying statements that command prints, not only the numbers. In particular a
standalone off-target response SHALL carry the search description — the budgets and
cut-offs its numbers are conditional on, the searchable fraction of the requested
bases, any inert supplied source, and an explicit statement when no sequence was
searched at all.

#### Scenario: A search that covered nothing
- **WHEN** the reference or region scope yields no searchable bases
- **THEN** the response reports zero sites *and* states that no sequence was searched,
  so an empty run cannot be read as a clean one

### Requirement: The API token is enforced wherever the app is served

`ALLELEFORGE_API_TOKEN` SHALL be honored by the application itself, not only by the
`serve()` convenience wrapper. The documented deployment commands bind the
module-level app directly and never call that wrapper, so a token enforced only there
is absent on every path an operator is told to use — while appearing to be set.

#### Scenario: A token set in the environment, app served by uvicorn
- **WHEN** `ALLELEFORGE_API_TOKEN` is set and the app is created without an explicit
  token argument
- **THEN** an `/api/*` request without a matching `X-API-Token` header is rejected
  with 401, and `/api/health` stays reachable for liveness probes

### Requirement: The served frontend loads nothing off-origin

The bundled frontend SHALL reference no third-party origin in any position the browser
fetches on its own — `src`, `srcset`, `<link href>`, CSS `url()`/`@import`, `fetch`,
`XMLHttpRequest`, `WebSocket`, or `Worker`. The page is opened while pasting patient
variants; a third-party request leaks the fact and timing of every visit. A link the
user clicks (`<a href>`) is navigation, not a load, and is permitted.

#### Scenario: A CDN font or script is added
- **WHEN** an asset references a stylesheet, script, or font from another origin
- **THEN** the check fails, naming the asset and the target

### Requirement: The embedded report runs with no privileges

The frontend SHALL embed a rendered report in a sandboxed frame that denies
`allow-scripts`, `allow-same-origin` and `allow-forms`. The report is HTML assembled
from user-supplied strings; without a sandbox an escaping bug in the renderer is an
application compromise rather than a report defect.

#### Scenario: A report is displayed
- **WHEN** a design result is shown in the web UI
- **THEN** the frame denies script, same-origin and form privileges, and the parent
  page cannot read the frame's document

### Requirement: The served app enforces a content security policy

Every response SHALL carry a Content-Security-Policy whose `script-src` admits only
`'self'` — no third-party origin, no `'unsafe-inline'`, no `'unsafe-eval'` — together
with `nosniff`, a referrer policy, and frame controls. The project promises that the
frontend loads no third-party scripts; a promise enforced only by review is not a
control, and it was false for as long as the rendered report carried a CDN script tag.

#### Scenario: A third-party script is reintroduced into a report
- **WHEN** a rendered report references a script from another origin
- **THEN** the browser blocks the load, because a `srcdoc` frame inherits the parent's
  policy


### Requirement: A terminal job reports finished

`progress` is a coarse three-valued state a client is told to render as a state, not a
percentage. A job that has reached a terminal state SHALL report `1.0` whether it
succeeded, failed or timed out; `state` says which kind. A finished job reporting the
running value shows as still running to any client following that instruction.

#### Scenario: A job that fails
- **WHEN** an async job ends in `error`
- **THEN** its `progress` is `1.0` and its `error` carries the reason


### Requirement: The cohort table is reachable over HTTP

The per-item summary table is the file a cohort run gets forwarded in. `POST /api/batch`
SHALL serve it as TSV alongside the JSON body, produced by the same library function the
CLI writes it with, so the two shells cannot describe one run differently.

No `html`/`pdf`: a cohort has no single rendered document, the same reason `aforge batch`
has no `--format`. No `parquet` yet — there is no cohort Parquet writer, and adding one
requires the guard that its columns match the TSV's in order.

#### Scenario: Requesting the cohort table over HTTP
- **WHEN** `POST /api/batch?format=tsv` is called
- **THEN** the response is the same table, header and `#` notes included, that
  `aforge batch --summary-tsv` writes


### Requirement: Consequence annotation takes two keys, and neither alone

The predicted molecular consequence SHALL be reachable over HTTP, and SHALL require both
the operator enabling it (`ALLELEFORGE_VEP` or `create_app(effect=...)`) and the request
asking for it (`annotate_consequence`). The operator's key is required because the
outbound request is made by the operator's server; the request's key is required because
the variant belongs to the client, so a deployment that has enabled the capability SHALL
NOT annotate on a client's behalf.

A request asking for it where it is not enabled SHALL be refused with a `422` naming
`ALLELEFORGE_VEP`, not answered without the annotation: a client cannot otherwise tell
"this deployment does not offer it" from "VEP found nothing notable". `GET /api/health`
SHALL report `vep_enabled` so a client can see which it is before asking.

Where it is enabled, the API description SHALL NOT claim that no sequence data is
transmitted externally, and SHALL name the request field that causes the transmission.

#### Scenario: Asking a deployment that has not enabled it
- **WHEN** a request sets `annotate_consequence` on a deployment with no VEP configured
- **THEN** the response is a `422` naming `ALLELEFORGE_VEP`

#### Scenario: An enabled deployment serving a request that did not ask
- **WHEN** `annotate_consequence` is absent on a deployment that has VEP enabled
- **THEN** no variant is sent to the VEP server and the report carries no consequence
