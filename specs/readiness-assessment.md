# Readiness assessment — AlleleForge for the medical/research community

_Status as of 2026-09-07. Author: engineering audit. This file records the honest
state of the project so context is not lost across sessions. Sections dated
2026-06-23 are kept for the record; the 2026-09-05 update below supersedes their
numbers and the prime-efficiency row, and the 2026-09-07 update supersedes the
2026-09-05 reachability list. The verification numbers just below are re-measured,
not remembered._

## TL;DR

The **engineering** is production-grade. The **headline scientific value proposition
is not yet delivered**: the efficiency/outcome predictions are heuristic placeholders,
not the real published models the README compares against. Build scientific substance
*before* distributing (see [`distribution-plan.md`](distribution-plan.md)).

## What is real and usable today

- **Off-target nomination** (population/haplotype-aware). This is deterministic
  sequence matching + CFD/MIT matrix scoring — no ML weights involved. It runs on
  real genomes now and is the genuinely differentiated, trustworthy part. Promote
  this without caveats.
- **The framework itself**: typed core, honest uncertainty contract, reproducible-
  to-the-byte runs, content-addressed benchmark harness, consent/license/checksum
  model-zoo gate, CLI + web + native Rust parity. All verified green:
  - `ruff` clean; `mypy --strict` clean (**108** source files)
  - the full suite passes, with coverage above the **85%** gate. No absolute test
    count is stated here: it changes with almost every commit, so a number written
    down is a number already wrong, and "the suite passes" is the claim that matters.
    The numbers this section *does* give are the ones a test derives from the
    repository and compares — see
    [`tests/test_the_readiness_numbers_are_derived.py`](../tests/test_the_readiness_numbers_are_derived.py).
  - `mkdocs build --strict` clean; `scripts/figures.py` regenerates the committed
    figures byte-identically; `scripts/reproduce.py` matches golden — and that last
    one is now checked by the test suite, having been false when this line was
    written and true only of a CI job nobody reads locally
  - **4** example notebooks pass; native crate builds, `cargo fmt`/`clippy` clean, and
    CI runs the whole suite against the installed crate rather than only the
    `native`-marked tests — the configuration the docs recommend was otherwise
    exercised nowhere
  - The skips are the real-weight tests, which need `ALLELEFORGE_REAL_WEIGHTS=1`
    (they reach outside the repository). The native-kernel parity tests that used
    to skip here now run: the installed extension was stale, which the version
    handshake could not detect, and a build that lacks a registered kernel is now
    reported rather than skipped.
  - wheel + sdist build, assets bundled and verified *from the wheel* (py.typed, cards,
    splits, frontend)

## UPDATE 2026-06-23 — four real models now wired (one per axis)

The gap below has been substantially closed. Real, opt-in, parity-verified models
are now wired through the model-zoo gate (behind `real_weights`; CI stays weight-free):

| Axis | Real model | Status |
|---|---|---|
| Cas9 efficiency | **Rule Set 3** (`TrainedRuleSet3Scorer`) | bit-parity; **hosted** (auto-download) + usable via `aforge design --trained-efficiency` |
| Prime efficiency | **PRIDICT2.0** (`PridictEngineAdapter`) | sequence-level engine; golden-verified — but **not reachable from a `design()` menu** (see the 2026-09-05 update) |
| Base-edit outcome | **BE-DICT** (`BeDictAdapter`) | golden-verified; position-mapping pinned |
| Cas9 outcome | **Lindel** (`LindelAdapter`) | golden-verified; usable via `aforge design --trained-outcome` |

Remaining stubs are documented optional **cross-checks** (each axis already has a
real model): `XCrispAdapter` (X-CRISP, 2025 PyTorch — feasible), `DeepPrimeAdapter`/
`GenETAdapter` (DeepPrime via the **PyPI** `genet` package — feasible),
`InDelphiAdapter` (2018 TF1/Theano — rot risk), `BeHiveAdapter` (2020 TF1 — rot
risk). See the per-axis specs. Their value is the inter-model **ensemble/agreement**
signal, not new coverage.

## What was NOT real (the original gap, now mostly closed)

Verified in code (pre-2026-06-23):

- `RuleSet3Scorer`, `PridictScorer`, `BaseEditOutcomePredictor` returned
  `UncertaintyMethod.HEURISTIC` with `calibrated=False` — sigmoid stand-ins. The
  baselines remain the weight-free defaults; the **real** models above are now the
  opt-in path.
- The trained adapters `raise NotImplementedError` — now wired for RS3, PRIDICT2,
  BE-DICT, Lindel; the rest remain documented cross-check stubs.
- Benchmark accuracy-vs-published is marked `[pending R1]`; the shipped benchmark
  fixtures are **synthetic** — real validation libraries are non-redistributable.
- Model cards carry `checkpoint_sha256: null` except `rule-set-3`, whose artifact is
  now pinned **and hosted** (R0 closed for that model).

## Reputational guardrail

Incumbents (CRISPOR, CHOPCHOP, Cas-OFFinder) are trusted. The first public claim
must be true and differentiated. **"Population/haplotype-aware off-target with honest
uncertainty" is true today. "Wraps PRIDICT2.0/BE-Hive" is not, yet.** Distributing a
tool that *looks* like it wraps those models but returns heuristics risks credibility.

## Minimum path to genuine scientific usefulness

1. Wire **one** real model end-to-end (chosen: **Rule Set 3** — see
   [`model-integration.md`](model-integration.md)).
2. Validate it (parity with the upstream package; published-Spearman reproduction is
   data-gated and documented as such).
3. Until each scorer is real, **relabel honestly** in README/UI as
   "heuristic baseline (real model pending)". Off-target needs no such caveat.

## Environment facts (this machine, 2026-06-23)

- Network: available (PyPI + GitHub reachable).
- ML stack: torch / transformers / scikit-learn / numpy **not** installed in `.venv`
  (core is deliberately light). Installable on demand.
- No GPU. CPU-only inference is fine for Rule Set 3 (LightGBM) and CPU PRIDICT2.

---

## UPDATE 2026-09-05 — verified state, and one row corrected

**Gate, re-verified on this date:** `ruff` clean; `mypy --strict` clean (95 files);
**1,288 tests pass, 5 skipped, 97.6% coverage** (gate 85%); `mkdocs build --strict`
clean; `scripts/reproduce.py` matches golden; **4** example notebooks pass. (The
2026-06-23 figures — 906 tests, 93 files, 3 notebooks — are superseded.)

### Correction: prime efficiency is *not* usable from the CLI or `design()`

The table above lists three axes as "usable via `aforge design --trained-*`" and the
prime row as "sequence-level engine; golden-verified". The distinction is easy to
read past, so, plainly: **a `design()` menu's prime efficiency is the heuristic
baseline today, whatever weights are installed.** PRIDICT2 designs *and* scores its
own pegRNAs and exposes no "score this externally-supplied pegRNA" entry point, so
`PridictEngineAdapter` is a parallel path, not a `PrimeEfficiencyScorer`. The two
adapters that *do* implement that protocol (`DeepPrimeAdapter`, `GenETAdapter`)
raise `NotImplementedError` by design. `design()` now accepts a
`prime_efficiency_scorer` override, but nothing trained ships to pass it. Closing
this needs the per-pegRNA parity scorer tracked as **(P2)** in
[`pridict2-integration.md`](pridict2-integration.md), and a regression test
(`test_no_shipped_trained_prime_scorer_satisfies_the_override_protocol`) now fails
the moment one lands, so the docs saying "no trained prime scorer" cannot go stale
silently.

### Capability added since 2026-06-23

- **Prime editing designs the whole small-edit repertoire.** The RT template is
  built at variable length, so insertions, deletions, MNVs and delins enumerate
  alongside substitutions — previously the flagship could not design for any indel,
  CFTR ΔF508 included. Bounds: the replaced reference span ≤ `PRIME_MAX_EDIT` (44),
  the written allele ≤ `PRIME_MAX_TEMPLATED_EDIT` (29 = the RTT ceiling less the
  minimum 3' homology), both mirrored in routing.
- **Nuclease + HDR is routed as the explicit last resort** for a precise edit no
  break-free chemistry can reach (e.g. restoring a 41-base deletion), which
  previously returned an empty menu. Such a candidate carries its donor, is flagged
  `outcome-is-nhej-spectrum`, scores 0 on cleanliness (the honest number — the NHEJ
  spectrum contains no intended allele, and no HDR rate is invented), and the donor
  is emitted as an orderable ssODN.
- **The off-target scan is >10x faster** with byte-identical output, which also took
  the project's own test suite from ~299s to ~45s.

### The reputational guardrail, restated

Unchanged and still the governing constraint: **"population/haplotype-aware
off-target with honest uncertainty" is true today; "wraps PRIDICT2.0" is true only
of the parallel sequence-level engine, not of a ranked menu.** Everything the menu
reports for prime efficiency is labeled `HEURISTIC` / `calibrated=False`, and the
scorer now also states on each prediction that it has no edit-size feature.

### UPDATE 2026-09-05 (later the same day) — the CLI can now do what the README claims

A reachability sweep — take `design()`'s parameter list, check each against the CLI and the web API —
found that the project's **headline differentiator was library-only**. `design()` and `search()` have
always accepted a population database; **no CLI command could supply one**. `--populations` existed on all
three commands but names ancestry *labels* to stratify by and carries no alleles, so every command-line
scan was reference-only and returned an empty ancestry breakdown that reads as "no ancestry-specific risk
found". The README's own example even listed `--maf` among the tunable knobs while it filtered alleles
that were never loaded.

Now reachable from `design`, `batch` and `offtarget`: `--gnomad` (population allele frequencies),
`--haplotypes` (phased panel), `--patient-vcf` (personal variants), plus `--cell-context` (which raises the
OOD flag and was previously config-file-only on the CLI and absent from the web API entirely). Requesting
ancestries with no ancestry-bearing source now warns explicitly that the result is *unmeasured*, not clean;
an unreadable source is a data error rather than a silent reference-only fallback.

**Still library-only**, and worth knowing before promoting the CLI: `offtarget_regions` and
`encode_tracks`/`chromatin_track`. **Deliberately not exposed on the web API:** the three file inputs —
a client-supplied filesystem path is a server-side file-read primitive, so that surface needs server-side
configuration like the reference already has.

The guardrail above is unchanged and now actually holds at the command line: "population/haplotype-aware
off-target with honest uncertainty" is true today *and reachable by a user*, which it was not before.

## UPDATE 2026-09-07 — the "still library-only" list above had gone stale

The 2026-09-05 update ends with a list of what a promoter of the CLI should know is
*not* reachable from it. Two days and several rounds later, every entry on it was
wrong:

- **`offtarget_regions` is reachable**: `design`, `batch` and `offtarget` all take
  `--region` (repeatable) and `--regions-bed`.
- **`encode_tracks` / `chromatin_track` are reachable**: `--encode-tracks` with
  `--chromatin-track` to name the track, on `design` and `batch`.
- **The three file inputs are reachable over HTTP**, by the server-side route that
  update said was needed: `ALLELEFORGE_GNOMAD_TSV` and `ALLELEFORGE_HAPLOTYPES` are read
  at app start, so a deployment opts in without a client ever naming a path.

The 2026-09-05 update shipped a regression test for its *other* honesty claim — that
no trained prime scorer satisfies the override protocol — and that claim is still
true today. The unguarded claim in the same document rotted within two days. So this
list is now generated from the code rather than remembered, and
`tests/test_the_readiness_assessment_states_the_real_reachability.py` fails if it
drifts: it binds every `run_design(...)` call in the CLI against `design()`'s
signature and requires the table below to name exactly the parameters left over.

### `design()` parameters no CLI command supplies

| Parameter | Why not, and whether it is a gap |
|---|---|
| `prime_outcome_predictor` | Not a gap today. It is an override for the prime byproduct baseline, and, as with prime *efficiency*, nothing trained ships to pass it. |
| `timestamp` | Not a gap. It exists so tests can pin provenance; `--timestamp` would only let a user forge a run's clock. |

### Addendum — `hgvs` closed, and its excuse described the wrong thing

The row above these lines said `c.`/`p.` inputs were blocked because a projector "is
not a dependency and is not a file a flag could name". Both halves are true and
neither is a reason: this CLI offers every other optional capability behind a boolean
flag and a named `MissingDependencyError` — `--trained-efficiency`, `--trained-prime`,
the Parquet writers, the VCF fast path. `--hgvs` is the same shape, and it targets the
*run's* assembly rather than the `hgvs` library's `GRCh38` default, because a `c.`
expression projected onto GRCh38 and then designed against an hg19 or T2T FASTA is a
wrong locus every later check would take at face value.

### Addendum — `clinvar` and `dbsnp` closed, and the excuse was false

The two rows above these lines said the accession and rsID lookups were `Protocol`s
the project ships with no implementation. `ClinVarDB` and `DbSnpDB` had shipped all
along: package exports, their own tests, and the two Protocol methods signature for
signature. They are *file-backed*, like `--gnomad` — the true half of the sentence was
only that nothing downloads a release. `--clinvar` and `--dbsnp` now supply one on
`resolve`, `design` and `batch`, and the release is pinned by content hash in
provenance and under `resolved_from` on `resolve --json`.

The instructive part is not the flag. A wrong reason for a gap, written into a
guard's allowance list, is stronger than no reason: the guard then reports the area
as decided every time it runs. This one had been checked, and agreed, for many
rounds — while the project's own flagship example, `aforge design VCV000012345`, had
never run.

### Addendum, same day — `effect` closed, and the table's own rule was wrong

Writing the table surfaced `effect` as a real gap: a library caller could annotate a
design with the variant's predicted consequence, and could be cautioned that they
were correcting a variant of modifier impact, while no command-line user could reach
either. `--vep` now closes it on `resolve`, `design` and `batch`. The flag is the
consent, because what the predictor's gate protects is *outbound* disclosure — the
variant, possibly from a patient VCF, going to a third-party public server — so the
help text names the recipient at the prompt, and `aforge resolve` reports
`consequence_checked` beside the consequence so a null cannot be read as "VEP looked
and found nothing".

The underlying reason it was unreachable is worth more than the flag. `design()`
takes `clinvar`, `dbsnp`, `hgvs` and `effect` and forwards them to `resolve()` — but
when it is handed an already-resolved variant, resolution is skipped and all four
went nowhere, silently. The CLI resolves variants itself, so a `--vep` that passed
the predictor to `design()` would have compiled, run, exited 0, and annotated
nothing. `design()` now refuses that call by name rather than dropping it.

The guard for this table also had to be corrected the same day it was written: it
counted only what the CLI passes to `design()`, and so called `--vep` unreachable on
the day it shipped, because the CLI supplies the predictor at its own `resolve()`
call. Both call sites are the same pipeline and both now count. That is the third
time in two rounds that a false positive here meant the rule was stated wrong rather
than needing an exception.

---

## UPDATE 2026-09-10 — a session of forty-two rounds, and what it changed

This file exists "so context is not lost across sessions". The rounds numbered 479–520 in
[`openspec/changes/README.md`](../openspec/changes/README.md) are that context; each one is
recorded there with its evidence. What follows is what a reader of *this* file needs.

**Nothing in the TL;DR changed.** The headline scientific gap is where it was: the
efficiency and outcome predictions are heuristic baselines, the real models are opt-in and
weight-gated, and CRISPR-Bench's shipped fixtures are synthetic. That is data- and
licence-blocked, not effort-blocked, and no round moved it.

**What is materially different:**

- **Assemblies are no longer assumed.** The web API stamped every genome `hg38` whatever
  FASTA was mounted, and resolved every request against that literal;
  `ALLELEFORGE_REFERENCE_BUILD` now says which assembly is served, `/api/health` reports it,
  and a request stating a different one is a 422. `design(build=…)` defaults to the
  reference's own label and refuses a build the reference contradicts. An off-target index
  and a reference are checked against each other by contig length, so an *unlabelled* index
  of the wrong genome is refused too.
- **Three reachability gaps closed.** The model zoo has a shell (`aforge models list/show`,
  `GET /api/models[/{name}]`) — seventeen cards carrying licence, intended use,
  out-of-scope use and known failure modes, previously readable only from Python. The
  licence gate they exist for is settable (`ALLELEFORGE_MODEL_USE`); it defaulted to
  research with no way to say otherwise, so a commercial user loaded a research-only
  checkpoint with no refusal. And a **VCF data line** is an input form on every surface,
  which the served page's own placeholder had been offering, and no surface accepted.
- **The off-target scan is several times faster, and parallel.** On a 2 Mb contig the scan
  went 0.647s → 0.108s profiled (1,996,749 Python calls → 341) across four parity-pinned
  steps, ending with the whole strand scan — anchoring included — inside the Rust kernel.
  A ten-variant cohort issues 58 whole-genome scans where it issued 81, all distinct. And
  the kernels release the GIL, so `--max-workers` delivers 1.75x / 2.92x / 3.98x on two,
  four and eight workers where it delivered 1.6x on four.
- **Provenance says less, and means it.** A model that was refused (licence, missing extra,
  unverifiable checkpoint) is no longer stamped as having scored the run; a run scored
  through a real sequence backbone now names it; a parallel cohort records the genome it
  screened against, which it previously reported as unknown.
- **Both shells publish one document.** A whole single-variant design — JSON, the flat TSV
  with its note block, the rendered HTML — is now diffed between `aforge design` and
  `POST /api/design`, and the off-target payload's *facts* between the two. Doing it found
  the two surfaces publishing a score at two precisions, which is fixed in the library.

**The honest summary is unchanged**: the engineering is production-grade and the scientific
substance is still the gap. What these rounds bought is that fewer of the engineering's own
claims are taken on trust — the parity, the reachability, the assembly labels and the
performance promises each have a check that fails when they stop being true.

## UPDATE 2026-09-10 (later the same day) — rounds 521–544, and one class of defect

The section above covers rounds 479–520. What follows covers 521–544, which were spent on
a single question: **what does this tool do when it is used wrongly?**

**Nothing in the TL;DR changed**, again. The scientific gap is where it was.

**The method, because it is the transferable part.** Almost every finding came from typing
a plausible mistake into a shell rather than reading code: transposing two path arguments,
leaving a shell variable unset, pointing a flag at the file meant for the flag beside it,
handing a command a file for the wrong genome build. The audit-by-reading rounds in the same
stretch found almost nothing. Then each finding was generalized by crossing the command's
own parameter list with a derived list of *ways to be wrong* — which turned one typed
mistake into a hundred cases and found every remaining instance in one pass.

**What is materially different:**

- **A wrong answer is refused where it used to be given.** `aforge lift --chain <not a
  chain file>` reported every locus `UNMAPPED` — indistinguishable, to a reader, from a
  locus that genuinely has no equivalent in the target build. An **empty spacer** returned a
  full off-target report: thousands of sites, specificity 0.000, because every position of a
  genome matches an empty query. Both are refused now.
- **A supplied safety source that cannot be used says so.** The off-target enumerators
  correctly skip a record whose asserted REF is not the base this genome has, and skipped it
  silently — so a gnomAD file or haplotype panel built against another assembly produced a
  report identical to one whose file was fine and had nothing to add. All three sources
  (gnomAD, haplotypes, patient VCF) now count those records, on every surface including the
  cohort table, where the mistake is most expensive and least visible.
- **A flag that was typed cannot be silently ignored.** `--intent ""` — what a shell script
  produces from an unset variable — designed a `correct` edit and said nothing; the same
  hole existed on `--weights`, `--populations`, `--cell-context` and on the web request
  models. Every command refuses it now, while a stray comma inside a list (`afr,,eas`) still
  runs, because those are different mistakes.
- **A PE3 candidate's second spacer is checked.** Pol III quality caveats were applied to
  the pegRNA spacer and never to the nicking guide's, so a nicking guide containing `TTTT`
  is truncated, never nicks, and the candidate behaves as PE2 while the menu says PE3b. The
  project's own canonical reproducibility fixture carried the flag.
- **Failures reach the caller as answers.** A failed VEP annotation raised `requests` at the
  user and answered `500` over HTTP (now `503`/`501`); a failed download left a truncated
  file that every later run reported as *tampering* and never retried (now verify-then-
  publish); a read-only output directory produced a traceback after the whole design (now
  checked before, and handled at the write).
- **One design publishes one precision.** The TSV, HTML and PDF rounded to four places and
  the JSON — the surface a pipeline parses — published float64, of a heuristic whose own
  note reads "coverage not measured".

**What this does not buy.** None of it makes a prediction better. It makes the tool's
*failures* legible, which matters for the same reason the uncertainty machinery does: a
number a user cannot tell apart from a measurement is worse than no number. The scientific
substance remains the gap, and remains data- and licence-blocked.
