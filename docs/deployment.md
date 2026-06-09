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
aforge design chr2:71:A>C --reference-fasta /data/hg38.fa --intent install

# Web: supply it once via env var (or create_app(reference=...))
export ALLELEFORGE_REFERENCE_FASTA=/data/hg38.fa
```

The genome layer auto-recommends T2T-CHM13 for segmentally-duplicated, centromeric,
or otherwise hg38-difficult loci; mm39 is the mouse baseline. Builds are
consent-gated and checksum-verified on download — an unverifiable artifact is
refused.

## Running the web service

```bash
# Direct
pip install "alleleforge[web]"
ALLELEFORGE_REFERENCE_FASTA=/data/hg38.fa \
    uvicorn alleleforge.web.api.app:app --host 0.0.0.0 --port 8000
# → http://localhost:8000  ·  OpenAPI at /docs
```

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
    All compute is local and user-controlled. The app makes **no outbound network
    call** and transmits **no sequence data externally** — a guarantee enforced by
    a test that fails if any socket connects during a design request. The served
    frontend loads no third-party scripts.

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

| Setting | Env var | Default |
|---|---|---|
| Reference build | `ALLELEFORGE_REFERENCE_BUILD` | `hg38` |
| Reference FASTA (web) | `ALLELEFORGE_REFERENCE_FASTA` | _none (503 until set)_ |
| Global seed | `ALLELEFORGE_SEED` | `20240501` |
| Predictive-interval level | `ALLELEFORGE_INTERVAL_LEVEL` | `0.80` |
| Off-target MAF threshold | `ALLELEFORGE_MAF_THRESHOLD` | `0.001` |
| Cache directory | `XDG_CACHE_HOME` | `~/.cache/alleleforge` |

## Optional native acceleration

The off-target FM-index has a correct pure-Python fallback, so the library runs
without any compiled code. For genome-scale searches, build the PyO3 crate:

```bash
cd rust && maturin develop      # builds aforge_native (BWT / k-mer / haplotype kernels)
```

The library detects and uses it automatically when present and falls back
transparently when it is not.
