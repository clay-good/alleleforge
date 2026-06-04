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
| `GET /api/health` | Liveness + whether a reference is loaded + the disclaimer. |
| `POST /api/resolve` | Normalize any input form to a canonical variant. |
| `POST /api/design` | Variant → ranked menu; `?format=json\|html\|pdf`. |
| `POST /api/jobs/design` | Submit an async design job (`202`, returns a job id). |
| `GET /api/jobs/{id}` | Poll an async job's state, progress, and result. |
| `POST /api/offtarget` | Standalone population-aware off-target search. |
| `GET /api/data` / `GET /api/data/{name}` | Inspect the dataset registry. |
| `GET /api/bench` | CRISPR-Bench (`501` until Phase 14). |
| `GET /` | The served single-page frontend. |

A reference genome is supplied by the deployment (`create_app(reference=...)` or
`ALLELEFORGE_REFERENCE_FASTA`); endpoints that need it return `503` until one is
configured, so the service starts cleanly without it.

## Example

```bash
curl -s -X POST localhost:8000/api/design \
  -H 'content-type: application/json' \
  -d '{"variant":"chr2:71:A>C","intent":"install","populations":["afr","eur"]}' | jq .candidates[0]

# render the same design as an interactive HTML report
curl -s -X POST 'localhost:8000/api/design?format=html' \
  -H 'content-type: application/json' \
  -d '{"variant":"chr2:71:A>C","intent":"install"}' > report.html
```

## The frontend

The frontend (`src/alleleforge/web/frontend/`) is intentionally a **served,
build-free single-page app** (vanilla HTML/CSS/JS, no Node toolchain) so it ships
inside the Python wheel and is exercised end to end by the API tests. It
implements the journey — variant entry (all input forms) → ranked candidate menu
with interactive Plotly efficiency intervals and outcome distributions → an
ancestry-stratified off-target view → oligo/report export — by posting to
`/api/design?format=html` and embedding the returned report. A production
Next.js + JBrowse 2 frontend can replace it behind the same API without backend
changes.
