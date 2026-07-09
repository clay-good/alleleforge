# Change proposals — bulletproofing & enhancement

These proposals harden and enhance AlleleForge's existing features. Each was derived from
a close reading of the current code (with `file:line` evidence in its `proposal.md`) and
targets a real gap between what a capability *claims* and what it currently *guarantees*.
The recurring theme: the strong mechanisms already exist (checksum verify, calibrated
intervals, seed, provenance) but are not yet fully wired into the real paths. Closing
those wiring gaps — more than adding new machinery — is what makes the tool trustworthy
enough for a bench scientist to adopt.

## Priority order

Ranked by scientific trust impact. Do the top group before any public distribution.

| # | Change | Capabilities | Why it matters |
|---|--------|--------------|----------------|
| ✅ | `harden-uncertainty-honesty` *(shipped — see `archive/`)* | uncertainty-contract, candidate-ranking | The `calibrated`/OOD flags are honor-system and ranking ignores them — the core "honest uncertainty" promise is not enforced end to end. |
| ✅ | `bulletproof-offtarget-nomination` *(shipped — see `archive/`)* | offtarget-nomination, native-kernels | The differentiator can under-state risk (first- not best-alignment) and mis-place indel-derived hits. Correctness here is the whole value proposition. |
| ✅ | `ship-published-cfd-matrix` *(shipped — see `archive/`)* | offtarget-scoring, reporting | The default CFD uses an approximation, not the published matrix — out-of-the-box scores are not the CFD numbers users expect. |
| ✅ | `validate-oligo-alphabet` *(shipped — see `archive/`)* | oligo-output | `revcomp` silently mis-complements non-DNA input, producing a wrong wet-lab reagent. Safety-critical, cheap to fix. |
| ✅ | `verify-artifact-integrity` *(shipped — see `archive/`)* | model-zoo, data-registry, genome-access | Cached checkpoints/datasets are trusted without re-verification and 12/13 cards are unpinned — the checksum gate is bypassed on every cache hit. |
| ✅ | `complete-provenance` *(shipped — see `archive/`)* | provenance-reproducibility, cli | Design provenance under-reports datasets/tools, the seed drives no RNG, and the CLI ignores the config file — "re-derivable from provenance" is only partly true. |
| ✅ | `align-prime-coverage` *(shipped — see `archive/`)* | prime-editor-design, candidate-ranking | Routing advertises prime for edit classes enumeration cannot produce, so the flagship silently under-delivers. |
| ✅ | `harden-web-api` *(shipped — see `archive/`)* | web-api | No auth/rate-limit/size cap and an unbounded, non-durable job store — unsafe to expose beyond localhost. |
| ✅ | `guard-benchmark-integrity` *(shipped — see `archive/`; metric hardening complete)* | benchmark-harness, reporting | Split disjointness is never enforced and results carry no schema version — leaderboard trust rests on invariants that aren't checked. |

## Round 2 — deeper correctness pass (all shipped)

The first round closed the wiring gaps. This round was a full re-audit of the same
capabilities that found gaps *inside* the shipped guarantees — places where a flag is
computed dishonestly, a summary number is optimistic, or a reagent is cloning-lethal but
round-trip-valid. Each finding is grounded in `file:line` evidence in its `proposal.md`
and duplicate-checked against the archive above. Every Round 2 change has now shipped and
been archived; the table is kept for provenance.

| # | Change | Capabilities | Why it matters |
|---|--------|--------------|----------------|
| ✅ | `guard-offtarget-strengthening` *(shipped — see `archive/`)* | offtarget-nomination, offtarget-scoring | The population pass drops a de-novo off-target when a minor allele upgrades a weak PAM (CFD 0.07→0.28) because "strengthened" is edit-count-only — a false negative in the differentiator; the genome-wide aggregate also omits the sub-threshold tail and CFD scores off-length spacers under a "published" label. |
| ✅ | `correct-design-verticals` *(shipped — see `archive/`)* | prime-editor-design, cas9-design, base-editor-design, candidate-ranking | PE3b is measured from the wrong end of the seed (mislabels the flagship's byproduct protection); nuclease/HDR correction is built on the reference not the patient's allele and the donor can be re-cut; the base-editor efficiency axis duplicates cleanliness. **Shipped:** PE3b seed direction, base-editor activity axis, composite-preserving truncation, allele-aware nuclease correction against the carried allele, and a re-cut-blocking HDR donor. |
| ✅ | `compute-honest-uncertainty` *(shipped — see `archive/`)* | uncertainty-contract | The OOD flag is hardcoded `True` in every default scorer (the trained PRIDICT path is *less* honest than its heuristic baseline), OOD widening can't rescue a zero-width interval, trained ≡ heuristic by the flags, and a fixed band asserts a fabricated 80% coverage. **Shipped:** OOD widening floor, trained-vs-heuristic flag, nominal-vs-measured interval note, and computed `in_distribution` with a fail-honest default across every emitting scorer. |
| ✅ | `reconcile-assembly-coordinates` *(shipped — see `archive/`)* | genome-access, variant-resolution, data-registry | Ensembl-named references vs `chr`-named everything-else, insertion left-align erasing the wrong-build signal, liftover that silently resizes across a chain indel, and a source-DB build silently overwritten — the classic silent coordinate errors. **Shipped:** insertion-anchor validation, liftover length/strand fail-closed, contig-naming reconciliation (aliasing + naming-aware overlaps), and source-DB native-assembly recording + reconciliation. |
| ✅ | `harden-benchmark-reproducibility` *(shipped — see `archive/`)* | benchmark-harness, provenance-reproducibility | The result signature bakes in wall-clock time and version so it can't confirm an independent re-derivation, the config snapshot omits `interval_level` (which drives the ranked ECE), the split membership hash isn't bound, and a degenerate scorer scores "perfectly calibrated." |
| ✅ | `guard-cloning-oligos` *(shipped — see `archive/`)* | oligo-output, reporting | The named cloning enzyme's own recognition site is never screened (a cloning-lethal insert ships clean), the U6 5'-G is double-added to G-initial spacers, the PDF leave-behind omits the oligos, and the pegRNA extension overhang is uncited and contradicts its docstring. |

## Round 3 — deep-correctness re-audit (all shipped)

A third full re-audit of the scientific core (scoring, off-target, coordinates, uncertainty,
ranking, benchmark, reporting, cohort). Each finding is a place where a *claimed* guarantee —
in a spec, docstring, or model card — was not upheld by the code, grounded in `file:line`
evidence and duplicate-checked against the archive above. All five shipped as direct `fix(...)`
commits against the existing specs/guarantees (no new capability deltas were required — the
code was brought back into line with specs that already existed).

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(reporting)` | reporting | The report never named the off-target scorer/matrix, so an approximation-scored table looked identical to a published-CFD one — violating the "scorer and matrix provenance are shown" requirement. **Shipped:** `CandidateReport` carries `offtarget_scorer`/`offtarget_matrix`; HTML/PDF print a "scoring basis" line; JSON export lossless again. |
| `fix(coordinates)` | variant-resolution, genome-access | `_working_interval` gated its clamp on raw `chrom in contigs`, skipping it on the common `chr`-named-variant-vs-Ensembl-reference path and leaking an off-contig end. **Shipped:** clamp via the naming-reconciling `contig_length`. |
| `fix(offtarget)` | offtarget-nomination | The Cas-OFFinder cross-check compared mismatched anchors on the minus strand (protospacer-start vs whole-match leftmost), off by `pam_len` — a spurious disagreement on every minus-strand site. **Shipped:** `reference_loci` shifts minus-strand loci by `pam_len`. |
| `fix(cas9)` | cas9-design, model-zoo | The default efficiency ensemble's heads are an unfitted pseudo-random scaffold, yet it emitted `method=ENSEMBLE` (trained) over a real backbone and the card claimed trained first-party weights. **Shipped:** label stays `HEURISTIC` until heads are fitted; card/docstrings describe the scaffold honestly. |
| `fix(cohort)` | (cohort batch design) | The parallel path used the eager `ThreadPoolExecutor.map`, draining the whole VCF stream and holding O(n) futures — breaking the bounded-memory guarantee. **Shipped:** bounded in-flight window (O(max_workers)). |

## Round 4 — re-audit of the periphery (all shipped)

Round 3 covered the scientific core; Round 4 swept the subsystems it had not read closely
(web-api/CLI, data loaders, FM-index, visualization). The FM-index was empirically
parity-checked against brute force (400 texts + 300 `pam_sites` cases, 0 failures) and the
web-API hardening held up — both cleared. Three genuine guarantee-not-upheld bugs shipped as
direct `fix(...)` commits:

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(cli)` | cli | `_load_config` whitelisted seven run-param keys (so no typo warning) but `design`/`batch` only read four; `max_per_chemistry`, `no_offtarget`/`run_offtarget`, `trained_*`, and `cell_context` were silently ignored — contradicting the "config file is honored" spec. **Shipped:** both commands honor every run-param they expose from config (CLI still overrides). |
| `fix(viz)` | visualization | `bar_chart` escaped every text node except the per-bar `value_suffix`, so markup in it produced malformed SVG — the "escape all text nodes" requirement is unconditional. **Shipped:** `_esc(value_suffix)`. |
| `fix(data)` | data-registry, variant-resolution | `ClinVarDB.get` claimed `VCV`/`RCV`/`SCV` resolution, but the VCF carries only VariationID so records index by `VCV` alone; an `RCV`/`SCV` gave a bare "no record" miss. **Shipped:** docstring narrowed to `VCV`; `RCV`/`SCV` raises an actionable message. |

## Round 5 — enumeration, effect, and config (all shipped)

The last un-audited modules: candidate enumeration, HGVS/effect, and model-zoo/config. The
genomic-HGVS parser and the model-zoo license/consent/checksum gates cleared. Three genuine
guarantee-not-upheld bugs shipped as direct `fix(...)` commits:

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(prime)` | prime-editor-design | The PE3b nicking-guide spacer was reverse-complemented from the *unedited* allele, so the "nicks only the edited strand" guarantee was inverted — it nicked the original molecule and failed on the edited product. The prior round fixed PE3b *detection*; this fixes the emitted spacer. **Shipped:** seed-disrupting branch templates the spacer from `edited`. |
| `fix(effect)` | variant-resolution | `parse_vep_response` picked the reported consequence with `max(key=impact_of)` — a coarse 4-bucket tier — so same-tier ties fell to VEP's unsorted term order (frameshift over splice_donor mis-routes chemistry). **Shipped:** total SO severity rank from the severity-ordered `Consequence` enum. |
| `fix(config)` | (infrastructure) | `Settings.load` passed the config file as init kwargs, which outrank env vars in pydantic-settings — inverting the documented `env > file` (reached `seed` and `allow_network`). **Shipped:** a file value yields to a matching `ALLELEFORGE_*` env var and to explicit overrides. |

## Round 6 — type layer + remaining benchmark internals (clean; no fixes shipped)

The last un-audited surface: the core type validators (`types/*.py`) and the benchmark modules
not covered in Round 3 (`baseline`, `tasks`, `_canon`, splits, datasets). **This round shipped
no fixes** — the signal that the deep-correctness sweep has reached diminishing returns:

- **Types:** one finding (`Variant.variant_class` labels a normalized anchored indel `INDEL`
  rather than `INSERTION`/`DELETION`) was **declined** — it is intentional, documented, and
  pinned by tests (`test_variant.py`: "anchored form classifies as indel; the pure form
  classifies as ins/del"), and `INDEL` is a correct umbrella label. Not a correctness bug.
- **Benchmark internals:** no genuine bug — baseline quantities, split disjointness/holdout,
  and canonicalization determinism all verified end-to-end. Only cosmetic docstring nits
  remain (e.g. a stale `offtarget-class` name), not correctness issues.

Rounds 3–5 shipped 11 real fixes; Round 6 came back clean on both fronts. The scientific and
infrastructure core has now been swept module-by-module.

Each change folder contains `proposal.md` (Why / What Changes / Impact), `tasks.md` (an
ordered checklist), and `specs/<capability>/spec.md` (the ADDED/MODIFIED requirement
deltas). When a change ships, fold its deltas into `specs/` and archive the folder.
