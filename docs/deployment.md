# Deployment guide

AlleleForge runs three ways over the same core: as a **library**, as the **`aforge`
CLI**, and as a **local web service**. This guide covers installing it, supplying a
reference genome, and running the web API in the default single-user local mode and
in a container.

!!! danger "Research use only"
    AlleleForge generates rigorously *uncertain hypotheses*. It is not a medical
    device and provides no medical advice; every off-target nomination requires
    experimental validation. See [Scope & responsible use](scope.md).

## Install

| Use | Command |
|---|---|
| Library (core, light) | `pip install alleleforge` |
| CLI | `pip install "alleleforge[cli]"` |
| Web service | `pip install "alleleforge[web]"` |
| Genome access | add `"pyfaidx>=0.8" "pyliftover>=0.4"` (heavier: `alleleforge[genome]`) |
| Real ML backbones | `pip install "alleleforge[ml]"` |

The core install is deliberately minimal (pydantic types, config, model-card
parsing) so it imports fast and stays reliable. Heavy scientific, ML, genome, and
web stacks live in optional groups, pulled in only where needed.

## Supplying a reference genome

Every command that touches sequence needs a reference FASTA. AlleleForge never
ships genomes; point it at one you control.

```bash
# CLI: pass the FASTA per invocation
aforge design 'chr2:71:A>C' --reference-fasta /data/hg38.fa --intent install

# Web: supply it once via env var (or create_app(reference=...))
export ALLELEFORGE_REFERENCE_FASTA=/data/hg38.fa
    # Which assembly that FASTA is. Only a label — and the label goes into every
    # report's provenance and decides which requests are answered, since a client
    # stating a different build gets a 422 rather than an answer under this one.
    # `GET /api/health` reports it as `reference_build`.
    export ALLELEFORGE_REFERENCE_BUILD=hg38
    # Optional, and the difference between a population-aware deployment and a
    # reference-only one: without it a request's `populations` is accepted and the
    # ancestry breakdown comes back empty. `GET /api/health` reports `gnomad_loaded`.
    export ALLELEFORGE_GNOMAD_TSV=/data/gnomad-sites.tsv
    # Also optional: the phased-haplotype panel, for sites that exist only on a
    # co-inherited combination of alleles. `gnomad_loaded` / `haplotypes_loaded`
    # on /api/health report which of the two this deployment has.
    export ALLELEFORGE_HAPLOTYPES=/data/haplotypes.tsv
```

!!! warning "The `.fai` index is required on a read-only mount"
    Opening a reference writes `<fasta>.fai` beside it when none exists. The bundled
    `docker-compose.yml` mounts the reference read-only — which is the right default —
    so the container cannot create one. Build it once on the host:

    ```bash
    samtools faidx ./data/reference.fa
    ```

    Without it the service still starts and every design request answers `503` naming
    the missing index and this remedy, rather than the process dying at import.


The genome layer auto-recommends T2T-CHM13 for segmentally-duplicated, centromeric,
or otherwise hg38-difficult loci; mm39 is the mouse baseline. Builds are
consent-gated and checksum-verified on download — an unverifiable artifact is
refused.

## Running the web service

```bash
# Direct — local, single user. Loopback only: an open API must not be reachable.
pip install "alleleforge[web]"
ALLELEFORGE_REFERENCE_FASTA=/data/hg38.fa \
    uvicorn alleleforge.web.api.app:app --host 127.0.0.1 --port 8000
# → http://localhost:8000  ·  OpenAPI at /docs
```

To reach the service from anywhere else, set a token. Every `/api/*` request
(except `/api/health`) then needs a matching `X-API-Token` header:

```bash
export ALLELEFORGE_API_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
ALLELEFORGE_REFERENCE_FASTA=/data/hg38.fa \
    uvicorn alleleforge.web.api.app:app --host 0.0.0.0 --port 8000
```

`alleleforge.web.api.serve()` additionally *refuses* a non-loopback bind without a
token. Running `uvicorn` against the module-level `app`, as above, binds the socket
itself and cannot consult that guard — so on that path the token is the control, and
setting it is on you.

The served page works against a gated deployment: `GET /api/health` — the one endpoint
the gate lets through — reports `auth_required`, and the page then shows a token field
and sends what you paste as the `X-API-Token` header on every call. The token is held in
`sessionStorage`, so it lasts for that browser tab and not for the browser profile, and it
is never sent anywhere but this deployment. Health never carries the token itself, only
the fact that one is required.

```bash
# Container (one-command local deploy; mount the reference at ./data/reference.fa)
docker compose up --build
```

Endpoints that need the reference return `503` until one is configured; `GET
/api/health` reports liveness and reference status. Long design runs go through an
**in-process async job queue** (`POST /api/jobs/design` → `GET /api/jobs/{id}`),
so the default deployment needs no broker or separate worker container. A
multi-user deployment can swap a real broker behind the same `JobManager`
interface and replace the served vanilla-JS frontend with a production Next.js +
JBrowse 2 frontend behind the unchanged API.

!!! important "Local, private, no egress"
    By default all compute is local and user-controlled: the app makes **no outbound
    network call** and transmits **no sequence data externally** — a guarantee enforced
    by a test that fails if any socket connects during a design request. The served
    frontend loads no third-party scripts. The one exception is **consequence annotation**, doubly opt-in: the operator
    enables it (`ALLELEFORGE_VEP`) because their server makes the request, and the
    client asks per request (`annotate_consequence`) because the variant is theirs; a
    deployment with it on says so in its OpenAPI description, in `GET /api/health`
    (`vep_enabled`), and on the page's banner. A **trained model** the deployment has
    enabled is the other path off the machine: an uncached checkpoint is fetched,
    pinned and hash-verified, carrying no sequence data.

## Concurrency & scaling

The design/off-target/batch endpoints are CPU-bound, so they are **synchronous**
handlers — Starlette runs them in a worker threadpool, which means a single
uvicorn process serves concurrent requests on multiple threads. Two properties
matter for an operator:

- **A shared reference is safe under concurrency.** All requests in a process
  share one `ReferenceGenome`; its `pyfaidx` handle keeps a single file position,
  so each read is guarded by a per-instance lock (the lock covers only the read,
  not the CPU-bound design that follows). Concurrent requests therefore get
  correct sequence — but genome reads serialize, and CPU work shares the GIL, so
  a single process does not give linear throughput on many parallel designs.
- **The async job queue is per-process.** `POST /api/jobs/design` schedules an
  in-process `asyncio` task; a job submitted to one process is only visible to
  that process. This is exactly right for the default single-process deployment.
- **A finished job's result is held in memory until it is evicted**, so it can be
  re-rendered in any format without designing again — which is what the served page
  relies on to make one click of *Design edits* one run. The store is bounded twice:
  by record count (1000) and by the bytes those results hold (256 MiB), evicting
  oldest-finished-first and never an in-flight job. Both bounds matter because a
  finished design keeps the ranked menu *and* its report — 1.25 MiB of JSON for a
  200-candidate menu — so a count alone permits well over a gigabyte. Size them with
  `create_app(jobs=JobManager(max_jobs=…, max_result_bytes=…))` for a deployment whose
  menus are larger or whose memory is tighter.

To scale out, run multiple `uvicorn --workers N` (or replicas): each is a separate
process with **its own reference** (memory scales with N × genome size — size the
host accordingly) and **its own job queue** (so route a job's submit and its
status polls to the same worker via session affinity, or swap `JobManager` for a
shared broker behind its unchanged interface). For CPU parallelism specifically,
prefer more processes over threads — the GIL bounds intra-process speedup.

## Configuration & reproducibility

Settings resolve in this order (later wins): field defaults →
`~/.config/alleleforge/config.toml` → `ALLELEFORGE_*` environment variables →
explicit constructor / CLI arguments. The global **seed** (`20240501` by default)
is threaded through every stochastic step and recorded in the provenance block of
every result, so a run is re-derivable from its config plus seed. The CLI writes a
`<output>.provenance.json` sidecar next to any file output.

Every `ALLELEFORGE_*` variable below is the `Settings` field name under the
`ALLELEFORGE_` prefix, and a check keeps this table honest: a name documented here
that nothing reads fails the suite, because an ignored setting is silent — and a variable the code
reads that appears in no table fails it too, because an undocumented setting is one nobody can use.
The last two are how the *trained* models are enabled: the CLI's `--trained-*` flags refuse with a
message naming them, and until they were listed here that message pointed at nothing a reader could
look up.

| Setting | Env var | Default |
|---|---|---|
| Reference build | `ALLELEFORGE_REFERENCE` | `hg38` |
| Reference FASTA (web) | `ALLELEFORGE_REFERENCE_FASTA` | _none (503 until set)_ |
| Assembly that FASTA is (web) | `ALLELEFORGE_REFERENCE_BUILD` | `hg38` |
| Population sites TSV (web) | `ALLELEFORGE_GNOMAD_TSV` | _none (every scan reference-only)_ |
| Haplotype panel TSV (web) | `ALLELEFORGE_HAPLOTYPES` | _none (no haplotype-aware pass)_ |
| Accessibility tracks (web) | `ALLELEFORGE_ENCODE_TRACKS` | _none (no chromatin adjustment)_ |
| Consequence annotation (web) | `ALLELEFORGE_VEP` | _none (requests asking for it get a 422)_ |
| Trained models offered (web) | `ALLELEFORGE_TRAINED_MODELS` | _none (requests asking for one get a 422)_ |
| Reuse off-target scans (web) | `ALLELEFORGE_OFFTARGET_CACHE` | _none (every scan recomputed)_ |
| Persistent genome index (web) | `ALLELEFORGE_GENOME_INDEX` | _none (index rebuilt in memory)_ |
| Licence use these runs are for (`research` / `commercial`) | `ALLELEFORGE_MODEL_USE` | `research` |
| Global seed | `ALLELEFORGE_SEED` | `20240501` |
| Predictive-interval level | `ALLELEFORGE_INTERVAL_LEVEL` | `0.80` |
| Off-target MAF threshold | `ALLELEFORGE_MAF_THRESHOLD` | `0.001` |
| Allow network access | `ALLELEFORGE_ALLOW_NETWORK` | `false` |
| Cache directory | `ALLELEFORGE_CACHE_DIR`, else `XDG_CACHE_HOME` | `~/.cache/alleleforge` |
| Config-file directory | `XDG_CONFIG_HOME` | `~/.config` (so `~/.config/alleleforge/config.toml`) |
| Lindel checkout (opt-in trained Cas9 outcome) | `ALLELEFORGE_LINDEL_REPO` | _none — the heuristic baseline is used_ |
| BE-DICT checkout (opt-in trained base-edit outcome) | `ALLELEFORGE_BEDICT_REPO` | _none — the heuristic baseline is used_ |

## Optional native acceleration

The off-target FM-index has a correct pure-Python fallback, so the library runs
without any compiled code. For genome-scale searches, build the PyO3 crate:

```bash
make native      # builds aforge_native (BWT / k-mer / haplotype kernels) and checks it
```

The library detects and uses it automatically when present and falls back
transparently when it is not.
