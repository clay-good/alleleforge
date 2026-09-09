# Web UI & API

Phase 13 is the accessible front door for users who will not touch a terminal: a
FastAPI backend that exposes the library over HTTP, and a dependency-free served
single-page frontend that drives the variant-first journey in the browser.

!!! warning "Local, private, no egress"
    All compute is local and user-controlled. The app makes **no outbound network
    call** and transmits **no sequence data externally** — a property asserted by
    a test that fails if any socket connects during a design request. The served
    frontend states this prominently and uses no third-party scripts.

## Running it

```bash
pip install "alleleforge[web]"
export ALLELEFORGE_REFERENCE_FASTA=/path/to/hg38.fa
uvicorn alleleforge.web.api.app:app --port 8000
# open http://localhost:8000  (frontend)  ·  http://localhost:8000/docs  (OpenAPI)
```

Or one-command with Docker (`docker compose up --build`, reference FASTA mounted
at `./data/reference.fa`). The async job worker is **in-process** — the default
deployment is single-user and local — so no broker or separate worker container
is required.

## Endpoints

The app is a thin async layer over the library: each endpoint validates its
request with a pydantic model, calls the same functions the Python API and CLI
expose, and returns a Phase 1 / Phase 11 schema-validated response. OpenAPI is
auto-generated at `/openapi.json`.

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness, the disclaimer, and which data sources this deployment loaded: the reference, the population sites, the haplotype panel, and the accessibility track names a request may choose from — plus `source_errors`, the reason a *configured* source failed to load, so a broken mount is not reported as a deliberate absence. |
| `POST /api/resolve` | Normalize any input form to a canonical variant. |
| `POST /api/design` | Variant → ranked menu; `?format=json\|html\|pdf\|tsv\|parquet\|menu` — the same set `aforge design --format` offers. `menu` returns the ranked menu itself rather than the report built from it, which is the only form carrying each candidate's *full* outcome spectrum; every other format truncates it and says so. |
| `POST /api/jobs/design` | Submit an async design job (`202`, returns a job id). |
| `POST /api/jobs/batch` | Submit an async **cohort** job (`202`, returns a job id). A cohort is the long operation — a 300-variant run takes minutes — so this is the door a client behind a proxy timeout should use; `POST /api/batch` blocks until the whole cohort is designed. Both run the same cohort through the same function. |
| `GET /api/jobs/{job_id}` | Poll an async job: `state` (`pending` → `running` → `done` / `error`, an enum in the schema so a generated client can switch on it), a three-valued `progress`, and the result or the failure reason. |
| `POST /api/batch` | Variant list → per-item summaries; `?format=json\|tsv` — the TSV is the same per-patient table `aforge batch --summary-tsv` writes, from the same library function. No `html`/`pdf`: a cohort has no single document. |
| `POST /api/offtarget` | Standalone population-aware off-target search, including the `scorer` choice (`cfd` / `mit` / `cfd-cas12a`) so a Cas12a run is labelled as the unvalidated approximation rather than as the published matrix. |
| `GET /api/data` / `GET /api/data/{name}` | Inspect the dataset registry. |
| `GET /api/bench` | List the CRISPR-Bench tasks with their kind, chemistry, dataset and metric battery. |
| `GET /` | The served single-page frontend. |

Every request model forbids unknown fields, so a misspelled or unsupported parameter is a
`422` naming it rather than a `200` describing a different run than the one asked for.

The data a run reads is supplied by the deployment, never by the request: a
client-supplied filesystem path would be a server-side file-read primitive. The reference
genome (`create_app(reference=...)` or `ALLELEFORGE_REFERENCE_FASTA`) gates the endpoints
that need it with a `503` until it is configured, so the service starts cleanly without
one. The population sites (`ALLELEFORGE_GNOMAD_TSV`), the phased-haplotype panel
(`ALLELEFORGE_HAPLOTYPES`) and the accessibility tracks (`ALLELEFORGE_ENCODE_TRACKS`) are
optional in the same way: without them a scan is reference-only whatever ancestry labels a
request carries, which is why `GET /api/health` reports what is loaded.

`ALLELEFORGE_VEP` is the one operator-configured capability that is not about reading a
file. Enabling it lets a request set `annotate_consequence` and get the variant's
predicted molecular consequence — which means this deployment sends that variant, a
chromosome, a position and both alleles, to an external VEP server. Set it to `1` for
Ensembl's public API, or to a base URL for a private VEP instance. It is the operator's
decision because the outbound request is made by the operator's server; it is off per
request because the variant is the client's. Where it is enabled, the API description
says so instead of claiming that no sequence data leaves the machine, and a request for
it where it is not enabled is a `422` rather than a report quietly missing the field.

`ALLELEFORGE_TRAINED_MODELS` follows the same operator-enables / client-chooses split as
`ALLELEFORGE_VEP`, for a structurally identical reason. Each trained model — Rule Set 3,
Lindel, BE-DICT, DeepPrime — is a consent-gated weight download or an external checkout on
the operator's disk, so only the operator can turn one on; which model scores a given run
is the client's choice, made per request with `trained_efficiency`, `trained_outcome`,
`trained_base_outcome` or `trained_prime` (the same names `aforge design` uses as flags).
Set it to a comma-separated list of those names, or `1` for all four. An unrecognized name
does not quietly leave the deployment baseline-only: it is reported on `GET /api/health`
under `source_errors`, and a request for a model it should have enabled is refused by name.
It does not raise, because `create_app()` runs at module scope and a deployment that will
not boot is worse than one that starts and says what is misconfigured. `GET
/api/health` lists what is enabled under `trained_models`, and a request for one that is
not is a `422` — a menu scored by the weight-free baseline and one scored by a trained
model are otherwise indistinguishable, and every number on them differs.

`ALLELEFORGE_OFFTARGET_CACHE` and `ALLELEFORGE_GENOME_INDEX` enable the two ways to stop
recomputing the reference scan: a cross-run store of reference-only reports, and a
persistent memory-mapped FM-index built once at startup. Neither changes a result, and
neither is a request field — both live on the server's disk, so a client asking for one
would be spending the operator's resources on its own request. `GET /api/health` lists
what is enabled under `scan_reuse`, which is a client's only way to know why two
deployments running the same code answer at very different speeds.

A personal genotype
is the one input that stays out — it is the caller's data rather than the operator's, so
server-side configuration is the wrong shape for it.

## Example

```bash
curl -s -X POST localhost:8000/api/design \
  -H 'content-type: application/json' \
  -d '{"variant":"chr2:71:A>C","intent":"install","populations":["afr","eur"]}' | jq .candidates[0]

# render the same design as an interactive HTML report
curl -s -X POST 'localhost:8000/api/design?format=html' \
  -H 'content-type: application/json' \
  -d '{"variant":"chr2:71:A>C","intent":"install"}' > report.html

# the flat per-candidate table a pipeline filters, over HTTP
curl -s -X POST 'localhost:8000/api/design?format=tsv' \
  -H 'content-type: application/json' \
  -d '{"variant":"chr2:71:A>C","intent":"install"}' > menu.tsv
```

### The two flat tables

`?format=tsv` and `?format=parquet` return the same columns in the same order — the
surface a pipeline acts on, which until now could not be obtained over HTTP at all.
Both carry the research-use disclaimer, the reference build and the coordinate
convention the JSON body carries: the TSV in leading `#` comment lines (skip them with
`comment_prefix="#"`), the Parquet in file-level key/value metadata keyed
`note_NN_<name>`, which sort into the order the TSV prints them
(`polars.read_parquet_metadata`). Both also state the variant, the intent and the
ranking weights, without which a table of reagents does not say what it is a table of. A table of specificities and
genomic loci with nothing saying what they are is the state those notes exist to end.

The Parquet writer is the optional `polars` dependency. A deployment without it answers
with a status naming the extra to install rather than a generic server error.

## The frontend

The frontend (`src/alleleforge/web/frontend/`) is intentionally a **served,
build-free single-page app** (vanilla HTML/CSS/JS, no Node toolchain) so it ships
inside the Python wheel and is exercised end to end by the API tests. It
implements the journey — variant entry (all input forms) → ranked candidate menu
with inlined-SVG efficiency intervals and outcome distributions → an
ancestry-stratified off-target view → oligo/report export — by posting to
`/api/design?format=html` and embedding the returned report. Its download buttons offer
PDF, JSON and TSV: the flat table is what a bench scientist opens in a spreadsheet, and
the page previously offered only a printable document and a nested object.

Both tabs carry a *More options* panel with the request fields whose absence changed what
a run could reach rather than how it looked: the cell context that raises the out-of-distribution
flag, the chromatin track (filled from this deployment's own `/api/health`, disabled when
it has none), the cloning vector whose enzyme the oligo hazard screen uses, and the
SpCas9-NG / SpRY fallbacks — without which a locus with no NGG guide returns an empty
menu and the page has no way to ask for the remedy. Ranking weights, chemistry filters,
region scoping and the render cap remain API-only, each recorded with its reason in
`tests/web/test_the_page_can_ask_for_what_the_api_accepts.py`. The cohort panel offers the
same set minus the cloning vector, which has nothing to screen there — the cohort endpoint
returns per-item summaries and builds no oligos. A production
Next.js + JBrowse 2 frontend can replace it behind the same API without backend
changes.
