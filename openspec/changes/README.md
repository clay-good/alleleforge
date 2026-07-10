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

## Round 7 — parallel deep re-audit of the scientific core (7 fixes shipped)

Round 6 was clean, but the memory rule holds: *empty backlog ≠ done — audit before declaring
clean.* Round 7 ran a fresh five-way parallel audit (off-target, design/enumeration,
scoring/uncertainty, genome/variant/data, output/report) plus an independent read of the
previously un-audited glue (model-zoo gate, content-addressed caches, cohort streaming — all
clean). Every candidate was reproduced and pinned by a regression test before the fix shipped;
each is a place a *claimed* guarantee was not upheld, grounded in `file:line` evidence and
duplicate-checked against Rounds 1–6.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(variant)` | variant-resolution | The reference-base accessor for an HGVS resolve was defined before a `c.`/`p.` expression was projected to genomic, so its default-arg closure froze `chrom=None` and **crashed every coding deletion/dup/delins** whose projector omits the ref bases (the biocommons `c_to_g` norm). **Shipped:** resolve the contig first, then build the accessor. |
| `fix(provenance)` | provenance-reproducibility, candidate-ranking | `design()`'s trained-scorer overrides (Rule Set 3 / Lindel / BE-DICT) scored the candidates, but provenance stamped the **default** scorers' cards — a re-run from the stamped provenance reproduces different numbers. **Shipped:** record each override's own card. |
| `fix(offtarget)` | offtarget-scoring | A **DNA bulge** collapses the target but leaves both strings 20 nt, so it slipped the length-only CFD fallback and was scored *and labeled* published CFD off-register. **Shipped:** thread the hit's bulge status into the fallback decision. |
| `fix(oligos)` | oligo-output, reporting | The Type IIS enzyme screen ran on the bare insert, not the assembled `overhang+insert`, so a recognition site **straddling the overhang/insert junction** shipped as clean — a cloning-lethal re-cut (the default BsmBI/lentiGuide `CACC`+`GTCTC…` case). **Shipped:** screen the assembled strand. *(safety-critical)* |
| `fix(base-editor)` | uncertainty-contract | The base-edit probability interval clamped its lower bound but not its upper, so a near-certain edit reported an interval upper bound `> 1.0`. **Shipped:** clamp the probability band to `[0, 1]` (the count-valued burden stays unclamped). |
| `fix(coordinates)` | genome-access, variant-resolution | The T2T ambiguous-region recommendation gated on a raw `== "hg38"`, dropping it for the equivalent `GRCh38` spelling. **Shipped:** gate via `assembly_matches`. |
| `fix(data/cli)` | data-registry, cli | `ClinVarDB.in_region` compared contigs by raw string (mixed-naming miss); `bench run` crashed formatting a `None` ECE; the batch TSV didn't escape tab/newline. **Shipped:** `canonical_contig` reconciliation, an `n/a` ECE guard, per-cell delimiter neutralization, and three code-matching docstring corrections. |

**Deferred (not fixed):** the VEP live-REST GRCh37 host/species (opt-in, `# pragma: no cover`,
untestable in CI — flagged for verification against the live API, not blind-edited); the
off-target ancestry bar-chart drawing a "not evaluated" ancestry at 0.0 (informational, uniform
in practice). Round 7 shipped 7 fixes across the same core Rounds 3–6 already swept — the
recurring lesson that a fresh close read still finds real, test-pinned guarantee gaps.

## Round 8 — integration-seam re-audit + native-kernel parity (3 fixes shipped)

Round 8 targeted the two angles Round 7's decomposition covered lightest: the native Rust
kernels (vs their Python fallbacks) and the *cross-subsystem seams* where two passes meet.
The native kernels came back **clean** — empirically parity-checked at ~240,000 randomized +
pathological cases (haplotype / k-mer / FM-index count-locate all 0 divergences) and confirmed
by a close read of the Rust + PyO3 (only a LOW cosmetic error-message divergence on
unreachable malformed input, documented not fixed). The seams yielded **three genuine bugs** —
one of them a regression from Round 7's own DNA-bulge fix, exactly the class a single-function
audit misses:

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(offtarget)` nomination | offtarget-nomination, offtarget-scoring | Round 7 added a `bulged` flag to `CfdScorer.score`, but the population/haplotype **nomination** path (`_reference_best`/`_strengthens`) still called `score()` without it — so nomination scored a DNA-bulge hit with the published matrix while reporting used the approximation. `_strengthens` could then drop a population hit's **POPULATION origin + ancestry attribution** by a score the report never shows. **Shipped:** pass `bulged=` in both helpers, matching `engine._scores`. |
| `fix(offtarget)` region-scope | offtarget-nomination | An explicit `regions=` scope bounded only the reference + population passes; the **haplotype and patient** passes consumed whole (chromosome-wide) panels with no region argument, leaking out-of-scope hits. **Shipped:** filter nominated hits to the requested regions (no-op when `regions` is None). |
| `fix(offtarget)` index-guard | genome-access | `search(…, genome_index=)` never checked the index was built from the **same assembly** as `reference`; a mismatch anchors PAMs over the index's sequence while reading coordinates from the reference — silently wrong hits. **Shipped:** fail closed when both builds are known and disagree. |

Rounds 3–5 = 11 fixes, Round 6 clean, Round 7 = 7, Round 8 = 3 (yield 5/3/3/0/7/3). The native
kernels are now empirically + statically confirmed at parity. **The lesson keeps proving out:
each fresh audit with a *different decomposition* still surfaces real, test-pinned guarantee
gaps — and a fix in one round can open a seam in the next, so re-audit after fixing.**

## Round 9 — invariant-oriented re-audit (7 fixes shipped)

Rounds 3–8 decomposed by module (3–6), by subsystem in parallel (7), and by integration seam +
native kernel (8). Round 9 used the one angle not yet tried: **cross-cutting scientific
invariants** that don't respect module boundaries — a five-lens parallel sweep for (1) numeric
range/clamp, (2) strand/orientation, (3) label/provenance honesty, (4) ordering/tie-break
determinism, (5) coordinate/indexing — plus an independent close read of the scoring/uncertainty/
ranking/benchmark-metric core (which came back clean). Every finding was reproduced and pinned by
a regression test before the fix shipped. The strand lens came back **clean** (eight prior rounds
hardened those paths); the other four each surfaced real guarantee gaps.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(uncertainty)` | uncertainty-contract, cas9-design | The wired-default `EnsembleEfficiencyScorer` built its interval as `mean ± z·std` (OOD-widened) through `ensemble_prediction`→`to_prediction`, neither of which clamped — so ~14% of contexts emitted an efficiency interval bound `>1.0` or `<0.0`. It was the lone unclamped efficiency emitter (the invariant was pinned for the base-outcome sibling, not here). **Shipped:** opt-in `bounds` clamp threaded through, `bounds=(0,1)` at the scorer. |
| `fix(prime)` | prime-editor-design, reporting, offtarget-scoring | Every PE3/PE3b two-nick `_merge_offtarget` rebuilt the report dropping `scorer`/`score_matrix` (→ no "scoring basis" line on the flagship, defeating the Round 3 guarantee) and `subthreshold_score_sum` (→ overstated specificity, defeating the Round 2 tail guarantee). **Shipped:** carry peg's scorer/matrix and sum both nicks' tails. |
| `fix(offtarget)` contig-naming | offtarget-nomination, data-registry | Three sibling sites compared contigs by raw string, so a panel/DB named in the other style ("1" vs "chr1") silently matched nothing — gnomAD population augmentation and every haplotype/variant hit went empty (the reference-bias blind spot the module exists to catch). Same class as the Round 3/7 `_working_interval`/`in_region` fixes, three sites they missed. **Shipped:** reconcile via `canonical_contig`, rebind to the reference's naming. |
| `fix(cas9-outcome)` | candidate-ranking, provenance-reproducibility | `ensemble_outcome` merged the distribution as a dict over a `set` of allele names, so the dict/summation/tie order followed `PYTHONHASHSEED` — the merged order, `total`, and `most_likely` varied run-to-run, breaking byte-determinism (fails 5/6 seeds pre-fix). **Shipped:** sorted allele set + total sort key. |
| `fix(provenance)` | provenance-reproducibility, model-zoo | The three default heuristic scorers reported the *trained* model's card, so a default run stamped a trained checkpoint (HEK293T/K562 training, "Trained on…" failure modes) into provenance for numbers a never-trained heuristic produced — a re-run reproduces different numbers. The cas9-efficiency default already had a bespoke honest card; the other three didn't. **Shipped:** three `*-baseline` cards + honest `model_card()`/name mapping; trained adapters keep the trained cards. |
| `fix(offtarget)` variant-span | offtarget-nomination | `_touches` attributed a population/haplotype hit by the variant's **anchor** `pos` only, so a multi-base deletion/MNV whose *other* changed bases reached the protospacer+PAM window (anchor just outside) was dropped — a false negative in the safety-critical path. **Shipped:** half-open span overlap (reduces to the point test for SNVs). |
| `fix(reporting)` | reporting, offtarget-scoring | The report's "scoring basis" line used the *nominal* configured matrix, so an all-bulge/off-length table read "published CFD" while every displayed score was the approximation (the per-site effective matrix from Round 7/8 was present but unused). **Shipped:** `OffTargetReport.effective_matrix()` reconciles the per-site truth. |

Rounds 3–5 = 11, Round 6 = 0, Round 7 = 7, Round 8 = 3, Round 9 = 7 (yield 5/3/3/0/7/3/7). An
invariant-oriented decomposition — properties that cut across modules — was the most productive
angle since Round 7, precisely because the earlier module- and subsystem-scoped audits were blind
to a guarantee that lives in the *seam between* a scorer, its label, and its report. The lesson
holds and sharpens: **change the decomposition and the audit keeps finding real, test-pinned
gaps.**

## Round 10 — adversarial-input / unhappy-path / end-to-end decomposition (3 fixes shipped)

Rounds 3–9 decomposed by module, subsystem, seam+kernel, and cross-cutting invariant. Round 10
used the angle none of those took: **what the code does on the paths a happy-path read skips** —
five parallel lenses for (1) boundary/degenerate genomic inputs, (2) error/unhappy paths and
fail-open-vs-closed, (3) end-to-end numeric correctness on real pathogenic variants, (4)
off-target safety edge cases, (5) aggregation on degenerate collections. The boundary-input and
end-to-end-numeric lenses came back **clean** (coordinate/allele/strand math verified end-to-end,
including minus-strand pegRNA mapping, and cross-export reconciliation). Every finding was
reproduced by a regression test that fails at HEAD before the fix shipped.

The headline is a bug nine prior off-target-focused rounds missed because no test drove the real
design pipeline with off-target search on: the guide's **own on-target** was counted as an
off-target, silently zeroing the ranking safety axis for *every* candidate.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(offtarget)` on-target | offtarget-scoring, candidate-ranking, cas9/prime/base-editor-design | The reference always contains the guide's own protospacer, so the genome-wide scan nominated it as a perfect (CFD 1.0) "off-target" at the guide's exact placement — pegging every candidate's `worst_score` at 1.0 (the ranking safety axis `1 − worst` inert at 0.0 for all) and capping `specificity_score` at 0.5 for even a clean guide, though the spec promises the CRISPOR/Hsu aggregate (which excludes the on-target). Uncaught because design tests use `run_offtarget=False` and ranking tests build synthetic reports. **Shipped:** opt-in `search(on_target=…)` drops the single site at exactly that locus (naming-aware, exact — a paralogous perfect match elsewhere is retained) from sites and the sub-threshold tail; all three verticals pass each guide's placement; spec records the requirement. |
| `fix(haplotypes)` contig-naming | offtarget-nomination, data-registry | `HaplotypePanel` indexed `_by_chrom` by the raw contig and looked it up by the raw query contig, so a bare-named ("1") 1000G/HGDP panel queried with a chr-named ("chr1") hg38 interval missed its bucket and returned no haplotypes — the haplotype-aware off-target pass silently contributed zero sites (the reference-bias fail-open the module exists to catch). Same class as the Round 3/9 reconciliations, the one sibling they missed (the bucket `.get()` runs before the naming-aware `overlaps`). **Shipped:** canonicalize both the index key and the query via `canonical_contig`. |
| `fix(benchmark)` KL-determinism | benchmark-harness, provenance-reproducibility | `kl_divergence` summed `pk·log(pk/qk)` over a bare `set(p) | set(q)`, whose `PYTHONHASHSEED`-dependent order made the non-associative float sum (and the `_normalize` totals) vary run-to-run — perturbing the un-rounded metric in the signed `BenchmarkResult`, defeating the module's "bit-stable across machines" contract. The Round 9 sibling (`ensemble_outcome`) was fixed; this one was left. Cross-platform digest survived only by 6-decimal rounding absorbing the ~1e-15 noise. **Shipped:** `keys = sorted(set(p) | set(q))`, fixing both the summation order and the normalization totals. |

Rounds 3–5 = 11, R6 = 0, R7 = 7, R8 = 3, R9 = 7, R10 = 3 (yield 5/3/3/0/7/3/7/3). The
unhappy-path/end-to-end decomposition surfaced the single highest-impact off-target bug of all ten
rounds — one that lived not in any single function but in the **untested seam** between a general
search primitive (correctly returns the on-target) and its design-time consumer (must not count
it). The lesson holds once more: **a decomposition the prior rounds didn't take — here, driving
the real pipeline end-to-end rather than reading functions — still finds real, test-pinned gaps.**

## Round 11 — guarantee-coverage + metamorphic invariants (2 fixes shipped)

Round 11 sharpened Round 10's lesson into its decomposition: hunt the *class* of bug R10 exposed —
a guarantee with no test driving its real consumed path — plus **metamorphic invariants** (permute
input order, reverse-complement the reference, scale a score; assert the relation that must hold).
Five parallel lenses: (1) features tested only with the feature off / via synthetic stand-ins, (2)
input-order/permutation determinism, (3) reverse-complement strand symmetry, (4) spec-`SHALL` →
test-existence gaps, (5) monotonicity/scaling. The **revcomp** (200+ fuzz cases across
scan/scoring/engine/population) and **spec→test** lenses came back clean — credible negatives. The
headline finding was reached **independently by two different lenses** (feature-off coverage and
monotonicity), the strongest signal yet that it is real.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(ranking)` patient-safety | candidate-ranking, offtarget-scoring | Patient off-targets were dropped from the ranking safety axis. `_safety` keys off `worst_ancestry()`, but `ancestry_stratification` credited only REFERENCE sites to every ancestry — a PATIENT site (certain in this genome, no ancestry frequency) landed in no stratum. So any benign ancestry-tagged population site coexisting made `worst_ancestry` return the benign score and the dangerous patient hit vanished: a CFD-0.9 patient off-target reported safety 0.70 not 0.05, and *adding* a benign site *raised* safety (monotonicity violation). Reachable in any `design(gnomad=…, patient_vcf=…)` run; uncaught because design tests use `run_offtarget=False` and ranking tests never mixed a patient site with an ancestry one. Found independently by two lenses. **Shipped:** `ancestry_stratification` credits a *certain* site (reference OR `frequency is None`) to every ancestry — the discriminator `expected_burden` already uses — so `worst_ancestry` equals the genome-wide worst; one source of truth, no `_safety` change. |
| `fix(ranking)` total-order | candidate-ranking | `rank_candidates` documented a "total and deterministic" order, but two distinct candidates with an identical objective vector fell to input-pool order (the four-key sort exhausts on a full tie). The spec sanctioned relying on deterministic *enumeration* order, so this was latent, not live — but the stronger, self-contained guarantee is cheap. **Shipped:** a final stable reagent-identity (spacer) tiebreak makes the order independent of how the pool was assembled; docstring + spec strengthened. |

Rounds 3–5 = 11, R6 = 0, R7 = 7, R8 = 3, R9 = 7, R10 = 3, R11 = 2 (yield 5/3/3/0/7/3/7/3/2). The
metamorphic + coverage decomposition proved out twice over: the same guarantee-vs-test-coverage
gap R10 exposed recurred in a sibling axis (patient sites on the safety term), and it was found
*independently by two lenses* — while the revcomp and spec→test lenses returned rigorous clean
bills. **The lesson stands after eleven rounds: pick a decomposition the prior rounds didn't, and a
close, reproduce-first read still finds real, test-pinned guarantee gaps — especially where a
feature's real consumed path is only ever tested with the feature effectively off.**

## Round 12 — the never-audited surfaces: concurrency, round-trip, numerics, adversarial input (4 fixes)

Rounds 3–11 swept the scientific + infra core many ways; Round 12 turned to four surfaces **no
prior round targeted**: (1) concurrency/thread-safety, (2) serialize↔deserialize round-trip &
idempotency, (3) numerical precision / degenerate math, (4) adversarial input to the web API and
report/leaderboard rendering. Each lens reproduced at least one real gap; four shipped as fixes,
two are honestly deferred (below).

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(benchmark)` NaN-guard | benchmark-harness | The metrics docstring promises "degenerate inputs return 0.0 rather than NaN so results stay JSON-serializable," but the guards test `<= 0` / `==` / emptiness — none of which a NaN satisfies (all NaN comparisons are False). A NaN flowed through: `spearman`/`pr_auc` scored corrupt input as a **perfect 1.0** (a NaN-emitting model tops the leaderboard), `pearson` returned non-JSON NaN, ECE crashed. Reachable via a NaN label. **Shipped:** a `_has_nan` guard at each entry → 0.0 (corr/AUC) / None (ECE), per each function's contract. |
| `fix(leaderboard)` md-escape | benchmark-harness, reporting | The reporting spec requires the leaderboard Markdown render to "escape all submitter-supplied cell content," and `_md_cell` promises "a cell can only ever be data" — but it escaped only `\|` and newlines, leaving `<img onerror=…>` and `[x](javascript:…)` intact on the shareable Markdown board (active content under any HTML-passing renderer). The HTML board was already safe. **Shipped:** HTML-escape angle brackets + backslash-escape every Markdown inline metacharacter; ordinary names stay readable. |
| `fix(reporting)` script-boundary | reporting, visualization | `_figure_script` inlines the Plotly figure JSON in `<script>` and escaped only `</`. A figure x-value is a user-supplied ancestry label; `<!--<script>` puts the HTML tokenizer into script-data-double-escaped state so the report's own `</script>` no longer closes the element — a crafted label defaces the whole report. **Shipped:** the standard safe transform (`<`,`>`,`&` → unicode escapes) the client parser restores; no raw `<` survives. |
| `fix(cohort)` atomic-output | (cohort batch design) | `_safe_name` mapped every non-`[alnum-._]` char to `_`, so two distinct items differing only in such chars (`chr1:100:A:T` vs `chr1:100:A/T`) shared a filename and silently overwrote each other — a torn write when two collided in flight on the parallel path (a plain non-atomic `write_text`). **Shipped:** append a SHA-1 digest of the raw id (injective) and write via temp-file + `os.replace` (atomic); resume is unaffected (keys on the manifest). |

**Deferred, documented (not blind-fixed):** (a) `Prediction.calibrated=True` is dropped on a JSON
round-trip and mutated in place when a calibrated prediction is nested into a frozen report — a real
violation of "JSON is the lossless form" and of frozen immutability, but **fully latent** (the
`ConformalCalibrator` that mints `calibrated=True` is not wired into `design()`), and a correct fix
requires a deliberate trust-model decision — whether deserialization of trusted local JSON should
re-honor the token-authorized calibration flag — that trades against the R1 tamper-resistance
guarantee. Flagged for a design pass, not rushed. (b) The web-API `harden-web-api` proposal named a
per-request **size cap**; only a variant-*count* cap shipped, so individual `spacer`/`variant`
strings and `populations` lists are unbounded (an amplifier for a shared, non-loopback deployment).
A cheap `max_length` hardening, deferred to avoid arbitrary limits without a deployment profile.

Rounds 3–5 = 11, R6 = 0, R7 = 7, R8 = 3, R9 = 7, R10 = 3, R11 = 2, R12 = 4 (yield
5/3/3/0/7/3/7/3/2/4). Twelve rounds, twelve decompositions; the never-audited surfaces
(concurrency/round-trip/numerics/adversarial) each still held a real gap. **The lesson is now a
method: the audit is never "done" — each genuinely new decomposition finds real, reproduce-first,
test-pinned guarantee gaps, and honest deferral of a latent, design-sensitive finding beats a rushed
edit to a load-bearing honesty mechanism.**

## Round 13 — property fuzzing, liftover round-trip, encoding/locale, native adversarial parity (4 fixes)

Round 13 ran four fresh lenses: (1) `hypothesis`-style property fuzzing of the scoring / normalize /
coordinate / revcomp cores, (2) liftover A→B→A round-trip + coordinate-system conversions, (3)
encoding / timezone / locale portability, (4) native Rust kernel vs Python fallback under
**adversarial** (not random) inputs. Two lenses returned rigorous clean bills — property fuzzing
(~22,000 cases; one LOW error-clarity edge) and native parity (**~76 million** comparisons across
homopolymers/repeats/max-budget-bulges/empty/`N`-laden inputs, 0 reachable divergence, native crate
confirmed built). The liftover and encoding lenses each surfaced real gaps.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(coordinates)` liftover | genome-access, variant-resolution | `lift_interval` fails closed on an interval a chain indel "silently resized" so the lifted coordinates "no longer describe the same bases" (its guarantee) — but it checked only the two endpoints + the span length. A **balanced** chain gap (equal-size source deletion + target insertion) keeps both endpoints mapped and the span length unchanged while the interior bases map to nothing, so it passed and emitted a scrambled interval (divergent bases in a cross-build lift). **Shipped:** lift every base of the short interval and fail closed on any unmapped base or contig/strand split; also guarded `to_one_based` on an empty interval (LOW, from the property lens). |
| `fix(io)` utf-8/BOM | data-registry, cli, (cohort) | `open_text` and the CLI/cohort file writes were left at the platform-default encoding while the content is UTF-8 (`model_dump_json` preserves non-ASCII; VCF/TSV can carry a BOM). A BOM rode on the first field so `'﻿#…'.startswith('#')` was False — ClinVar header detection and source-assembly auto-detection broke; and the "lossless" export crashed under a non-UTF-8 locale / wrote mojibake under Windows cp1252. **Shipped:** `open_text` decodes `utf-8-sig` (strips BOM); the cohort/CLI writes pass `encoding="utf-8"`. |
| `fix(reporting)` pdf-cp1252 | reporting | The PDF declares its font `/WinAnsiEncoding` (CP1252) but `_escape` encoded Latin-1, silently turning ordinary punctuation the font renders — a curly apostrophe, en/em dashes, the euro sign — into `?`: data loss on the printable leave-behind. **Shipped:** encode CP1252 to match the declared font; only truly unrenderable scripts still fall back to `?`. |

**Native kernels re-confirmed:** with the crate built, FM-index / k-mer / haplotype are byte-for-byte
identical to the Python fallbacks and brute force across every adversarial/pathological class (the
one k-mer UTF-8 divergence is unreachable — the scan sanitizes to `ACGTN` before any kernel).

**R12 defer resolved:** the web-API per-field **size cap** deferred in Round 12 shipped here as
`fix(web-api)` — generous per-field caps (spacer 512, variant 8192, populations 64, …, all far above
any legitimate input) reject an oversized field with 422 before any scan, closing the flood/O(work)
amplifier the `harden-web-api` "request-size cap" guarantee named. The remaining R12 defer
(`Prediction.calibrated` round-trip) stays deferred by design — a latent, trust-model-sensitive change.

Rounds 3–5 = 11, R6 = 0, R7 = 7, R8 = 3, R9 = 7, R10 = 3, R11 = 2, R12 = 4, R13 = 4 (yield
5/3/3/0/7/3/7/3/2/4/4). Thirteen rounds; two R13 lenses (property fuzzing, native adversarial parity)
came back genuinely clean while the portability and coordinate-faithfulness lenses each still held a
real gap. **The pattern holds and refines: as decompositions accumulate, some lenses converge to
clean (the R6-style signal) while a newly-chosen angle still finds real, test-pinned gaps — audit
breadth, not depth on one axis, is what keeps surfacing them.**

## Round 14 — cross-surface consistency, algorithmic complexity, uncertainty math, weight validation, I/O trust (5 fixes)

Round 14 first confirmed the whole CI job set is green locally (not just pytest — lint, format,
mypy `--strict`, reproduce-golden, nbmake, mkdocs `--strict`, native parity, cargo fmt/clippy), then
ran three fresh parallel lenses no prior round had taken as a dedicated pass, plus two finds from an
independent read. Each lens returned exactly one real, reproduced, test-pinned gap; the rest of each
lens's surface came back a credible clean bill.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(ranking)` non-finite weights | candidate-ranking, cli | `RankingWeights` validated weights non-negative + not-all-zero, but a bare `weight < 0.0` check lets `nan`/`inf` through (both compare False). The CLI `--weights`, a config file, and the Python API parse via `float()`, so `--weights 1,1,1,nan` built weights whose `normalized()` is `nan` for every objective — every candidate's composite becomes `nan` and the order scrambles; `inf` collapses the finite weights to 0. **Shipped:** reject any non-finite weight in `__post_init__`; `_parse_weights` now builds `RankingWeights` inside its try/except so a bad weight is a clean USAGE error, not an uncaught traceback. |
| `fix(uncertainty)` OOD widens | uncertainty-contract | `ConformalCalibrator.calibrate` computes `new_half = scale * half_width`; when the fitted scale is `< 1` (an over-covering scorer), an OOD input carrying the `OOD_MIN_HALF_WIDTH` floor came out **narrower** than the floor — an out-of-distribution prediction presenting a narrow, confident `method=conformal` interval, the opposite of "OOD widens, never narrows." Latent because the only caller exercises `calibrate` on in-distribution data. **Shipped:** the OOD branch floors the multiplicative scale at 1, so recalibration can only widen. |
| `fix(offtarget)` effective matrix on standalone surfaces | offtarget-scoring, cli, web-api | The design report reconciles an all-approximation off-target table via `effective_matrix()`, but the `aforge offtarget` CLI and `/api/offtarget` surfaced only the **nominal** `score_matrix` (the CLI per-site dicts omitted the matrix entirely), so a client read `doench-2016-cfd` for an all-approximation table — the same computation labeled honestly on one surface, dishonestly on another. **Shipped:** `effective_matrix` on `OffTargetResponse` + the CLI payload (top-level and per-site), and an "effective …" note on the CLI human line. Additive. |
| `fix(genome)` O(n) fallback suffix array | native-kernels, genome-access | The pure-Python FM-index fallback built the SA with `sorted(range(n), key=lambda i: data[i:])`, materializing every suffix as a sort key — **O(n²) memory**, O(n² log n) time on repeats. The off-target engine auto-selects the FM path for any region ≥ 1 Mb, extrapolating to ~500 GB peak (far below the 50 Mb warning) — an OOM on native-less installs, the documented norm. **Shipped:** prefix doubling (Manber–Myers), O(n log² n) time / O(n) memory, byte-identical SA (verified vs the direct sort + 400 fuzz cases; 129.7 MB → 4.0 MB at n=16k). |
| `fix(cache)` fail closed on missing sidecar | (integrity primitive) | A `verify=True` `ContentAddressedCache` re-checked a payload against its `.sum` sidecar only *when the sidecar existed* — a missing one served the unverifiable bytes, so `rm *.sum` silently defeated the tamper-detection gate the docstring promises. Latent (production callers use the `verify=False` default) but `verify=True` is a public option. **Shipped:** `get_bytes` raises `CacheIntegrityError` on a missing sidecar under `verify=True`. Found by the file-path / I-O trust-safety lens (whose broader sweep — cohort names, split loader, `--out` paths, cache dirs, web job ids — came back clean). |

**Coverage hardening (same session):** a spec-SHALL → enforcing-test sweep returned a correctness
clean bill but found three guarantees pinned only by a flag / metadata / unit helper, where a
regression on the real consumed path would stay green. Added non-vacuous guards (each verified to
fail under a simulated regression) + fixed one stale comment: base-editor efficiency-vs-cleanliness
axis distinctness (its test carried a stale comment describing the pre-fix conflation), HDR-donor
re-cut safety on the *emitted donor sequence* (not just the `recut_blocked` flag), and pegRNA
3'-extension enzyme screening through the real `pegrna_oligos` path (not only the unit helper).

**Infra hardening (same session):** the `lint` CI job executed the example notebooks but never
style-checked them, so `examples/` had drifted out of ruff compliance — extended `ruff check` /
`ruff format --check` to cover `examples`, exempted teaching cells from docstring rules, and
reformatted the notebooks (`ci(lint)`, the same *ungated-surface-rots-silently* class the reproduce
and format-check pins closed in R14's CI-gate work).

**Honest defer:** `ConformalCalibrator.calibrate` takes no `bounds` and can emit an efficiency
interval outside `[0,1]` on the calibrated path when the fitted scale is `> 1`. Genuinely latent —
the only caller is the benchmark calibration demo; it is not wired into `design()`. A correct fix
threads a `bounds` argument through `calibrate`, which nothing yet needs, so shipping it now would be
speculative machinery; deferred with documentation rather than rushed.

Yield 5/3/3/0/7/3/7/3/2/4/4/5. **Lesson holds: a fresh decomposition still finds one real gap per
lens even after the core is empirically clean under fuzzing + native parity — the productive angles
now are the seams a scientist cares about (the same number labeled two ways on two surfaces) and the
cost model of the fallback paths (quadratic memory the native kernel hides), not the numeric core.**

## Round 15 — cross-interface parity + adversarial output rendering (3 fixes)

Two fresh lenses: (1) **cross-interface result parity** — does the same input produce the same
scientific result and provenance via the Python API, the `aforge` CLI, and the web API? (2)
**adversarial output rendering** — can a user-influenced string smuggle a break/injection into a
rendered artifact (PDF, HTML, TSV, leaderboard, provenance)? The rendering lens returned a clean bill
on HTML/PDF/SVG/leaderboard/provenance (each user string already escaped) apart from one TSV gap; the
parity lens found two provenance/config divergences.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(cohort)` batch seed provenance | provenance-reproducibility, cli, web-api | `design_many` stamped the run-level provenance seed from `get_settings().seed` (the process singleton), while the seed that governs the run is the one threaded into every per-item `design()` via `settings=`. So `af batch --seed 999888` recorded a run seed of `20240501` while every per-item menu used `999888` — the run header contradicted its own items and disagreed with `af design`. The seed is the anchor `aforge verify` reads. Test-invisible because the suite only used the default seed. **Shipped:** stamp `(design_kwargs.get("settings") or get_settings()).seed`. |
| `fix(reporting)` TSV carriage returns | reporting | `report_to_tsv`'s `_cell` neutralized `\t` and `\n` but not `\r`, while the sibling `_batch_tsv._cell` handled all three. A `\r` in a user-influenced cell (a `worst_ancestry` label, a candidate flag) broke one logical row into several physical lines and crashed `csv.reader` (Excel / `splitlines()` / `csv` treat a bare `\r` as a row break). The pinning test shared the blind spot. **Shipped:** `.replace("\r", " ")`; strengthened the test + a direct `_cell` delimiter guard. |
| `fix(web-api)` config file honored | provenance-reproducibility, web-api | The spec requires all interfaces to resolve settings through `Settings.load()` so the config file applies to web too, but the module-level `create_app()` default used a bare `Settings()` — reads env, silently skips `~/.config/alleleforge/config.toml`. A machine config governed the CLI/library but not the web server. **Shipped:** `create_app()` defaults to `Settings.load()`; docstring corrected. |

**Honest scoping note (not shipped):** neither TSV emitter guards against CSV/spreadsheet *formula*
injection (a leading `=`/`+`/`-`/`@`) — but no spec or docstring claims formula-injection safety (the
stated contract is delimiter neutralization, which the `\r` bug genuinely violated), so prefixing such
cells is flagged as a possible defense-in-depth follow-up rather than a violated guarantee. The web
`DesignRequest` also omits `cell_context` / trained-scorer opt-ins the CLI exposes — a missing feature,
not a same-input divergence (for the unset request the surfaces agree).

Yield 5/3/3/0/7/3/7/3/2/4/4/5/3. **Lesson: once the single-surface science is clean, the remaining
gaps live at the INTERFACE seams — the same run recorded differently on two surfaces (a batch seed,
a config source) and a delimiter one emitter strips but its sibling doesn't. Parity across surfaces is
its own audit axis.**

## Round 16 — trust-contract completeness, benchmark science, driven concurrency (4 fixes)

Three lenses (two driven by subagents, one an independent read of the `af verify` reproducibility
command): (1) the `af verify` contract vs its spec; (2) benchmark metric correctness on edge inputs;
(3) concurrency driven under *real* contention (threads + `setswitchinterval`, thousands of
iterations), not just read. The concurrency lens gave three surfaces rigorous **driven** clean bills
(cohort parallel: 120 runs, 0 determinism mismatches; JobManager: cap never exceeded, 0 drops;
ReferenceGenome: 72k concurrent fetches, 0 wrong bytes) and found the cache races; the benchmark lens
verified pr_auc/roc_auc/spearman/pearson/ECE/KL/splits/leaderboard/generalization correct apart from
the `inf` guard.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(cli)` verify re-hashes datasets | provenance-reproducibility, data-registry | The spec's tamper contract covers a "checkpoint *or dataset*" whose bytes no longer match its hash, but `af verify` re-hashed only `provenance.models`, never `provenance.datasets`. Reachable: the vendored Doench-2016 CFD matrix is a registry dataset with a real pinned `sha256`, so a tampered CFD matrix (the heart of off-target scoring) passed verification silently. **Shipped:** a symmetric dataset re-hash loop; `--cache-dir` covers both artifact kinds. |
| `fix(benchmark)` ±inf is degenerate | benchmark-harness | The NaN guard (`v != v`) missed `±inf`, a finite-ordering value that sorts largest and passes every `<= 0` / `==` check. An `inf` score made spearman/roc_auc/pr_auc score corrupt input as a **perfect** 1.0, made pearson return non-JSON `NaN`, and *crashed* ECE on `int(inf*n_bins)`. Reachable: `Prediction` admits `value=inf`. **Shipped:** broaden the shared guard to `not math.isfinite`. |
| `fix(cache)` put_bytes concurrency | provenance-reproducibility | (1) verify=True wrote the sidecar *after* the payload, so a concurrent reader saw a payload with no sidecar and the fail-closed check (added earlier this session) raised on valid data (16 threads → 15 spurious errors). (2) `id(data)` temp names collided for two threads sharing a bytes object → `FileNotFoundError`. **Shipped:** publish the sidecar before the payload; per-write `uuid` temp token. |
| `fix(benchmark)` reject signed non-finite | benchmark-harness | The leaderboard sorts on `primary_value`; a `NaN` there loses every comparison, so a single externally-signed submission carrying `NaN` would make the whole board's ranking non-deterministic. The computed path is finite (the metrics guard above), but a *signed* value is a claim deserialized from JSON. **Shipped:** `BenchmarkResult` validates `primary_value` + metric values finite on construction/deserialization and raises otherwise. |

**Note:** the concurrency defect (1) was an interaction with this session's own earlier
`fix(cache)` fail-closed-on-missing-sidecar change — a fix in one round opened a seam in the next (the
R8 meta-lesson), caught here because the concurrency lens *drove* the write/read race rather than
reading the method. The benchmark lens's flagged follow-up (a self-signed non-finite `primary_value`
scrambling the sort) was then shipped as the fourth fix, completing the finiteness theme — the metrics
*compute* finite and ingestion *rejects* non-finite claims.

Yield 5/3/3/0/7/3/7/3/2/4/4/5/3/4. **Lesson: the trust-contract commands (`af verify`) and the
fallback/concurrency cost model are where gaps now live — and driving contention (not reading it)
is what surfaced a race that a fresh same-session fix had just opened.**

## Round 17 — non-finite at the source (1 fix; scoring-overflow lens clean)

A scoring-layer overflow audit drove every `log`/`exp`/`sigmoid`/`sqrt`/division/normalization in
`scoring/` and `offtarget/` against degenerate-but-legal inputs and returned a rigorous clean bill —
every one is guarded (sigmoids clamp output, CFD/MIT factors are range-checked, outcome divisors have
`or 0.01` floors, conformal `fit` rejects non-positive-width intervals). It confirmed that no scorer
*produces* a non-finite value, but that the `Prediction` contract still *admits* one.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(uncertainty)` Prediction rejects non-finite | uncertainty-contract | `_check_interval` validated ordering/level/containment but not finiteness. A `NaN` value was caught only incidentally (fails containment); `±inf` slipped through entirely (`value=inf` with `(0, inf)` satisfies `low <= value <= high`, and a finite value with an `(lo, inf)` bound passed). No scorer produces one, but a `Prediction` is **deserializable**, so a non-finite one from JSON would scramble the ranking composite sort or break a report's JSON — the same class the metrics/leaderboard guards closed on the benchmark side. **Shipped:** reject a non-finite bound or numeric value at construction/deserialization. |

This is the **source-level completion of the finiteness theme** that ran across R16–R17: scorers
*compute* finite (clean bill), the `Prediction` contract *rejects* non-finite on construction/load,
the benchmark metrics *degrade* a non-finite input to the degenerate result, and benchmark ingestion
*rejects* a non-finite signed claim. Four complementary layers, each closing the class at a different
seam. Yield ...5/3/4/1.

## Round 18 — variant-resolution edge cases + prime-editor flagship (1 fix; prime clean)

Two correctness lenses on the hardest verticals. The prime-editing lens built an **independent
biological reconstruction** (rebuild the edited genome from only the emitted `strand`/`pbs`/`rtt`/
`nick_site`, never the enumerator internals) and verified **800,420** pegRNAs across all intents and
both strands reconstruct the intended edit, PBS complementarity on both strands, PE3/PE3b nicking over
**493,590** ngRNAs (including the never-tested minus-frame PE3b seed path), oligo round-trip, and
edit-class coverage — a rigorous **clean bill** for the supported SNV class. The variant lens found one
severe bug.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(variant)` delins not rolled | variant-resolution | `_left_align` ran its pure-indel "roll left through a repeat" loop for any `len(ref) != len(alt)`, but a true **delins** (both alleles non-empty after trimming) whose alt's last base equals the preceding reference base rolled `ref` to `""` — discarding the deleted bases and relocating the variant. `chr2:6:AC>T` against a `TTTTT…` lead-in resolved to `pos=0, ref='', alt='T'` (an insertion at the wrong locus) instead of `pos=5, ref='AC', alt='T'`; the empty `ref` then made `_validate_ref` return early, so it was accepted silently. Common near homopolymers/repeats (a frequent ClinVar pattern); corrupts interval/effect/guide design. **Shipped:** a still-both-non-empty variant after trimming is a genuine delins with no anchor to roll — return the parsimonious form instead of rolling. |

Yield ...5/3/4/1/1. **Lesson: the multi-modality *design verticals* (prime/base/cas9) are now
empirically clean under large-scale independent reconstruction, but the *upstream* normalization that
feeds them still held a severe silent-corruption bug — the input pipeline (resolve/normalize/liftover)
deserves as much scrutiny as the scorers, because a mis-normalized variant mis-designs every modality.**

## Round 19 — input-seam re-audit (0 code fixes; 2 clean bills — diminishing returns on this axis)

After R18's delins fix flagged the input pipeline as under-audited, two lenses re-swept it and both
returned rigorous **clean bills** — the credible-negative signal that this axis is now well-covered:
- **resolve→design handoff**: reproduced end-to-end the working-interval math (MNV/delins full span,
  contig-end clamp via the naming-reconciling `contig_length`, pos-0 boundary), the carried-allele
  overlay actually changing enumeration (an alt-created PAM found by CORRECT, not by reference-based
  KNOCK_OUT — consistent across cas9/base/prime), minus-strand coordinate math in all three modalities,
  and liftover fail-closed off the design path. No defect.
- **effect prediction + chemistry routing**: matched **48/48** intent×substitution combinations against
  an independent ABE/CBE transition oracle (transversions correctly excluded from base editing on both
  edit directions), confirmed intent→allele consistent across all four enumerator siblings, and the SO
  severity ranking correct with no coarse-tier sibling. No defect.

The only finding was a documentation error (`docs(enumerate)`): the cas9 module docstring claimed the
genome carries the *alternate* allele for INSTALL — backwards (it carries the reference; the code was
correct, only the prose wrong). Fixed.

**Signal:** two independent rigorous lenses on the same axis returning credible clean bills — with the
one real gap (the R18 delins) already closed — is the R6/R13-style diminishing-returns marker for the
input seam. The productive next angles are axes not yet swept this session (e.g. the data-loader →
Variant ingestion path, or a documentation-vs-behavior sweep), not more depth on resolve/route.

## Round 20 — data-loader ingestion + documentation accuracy (2 code fixes + 4 doc fixes)

Took R19's own suggested next angles. The data-loader lens verified all eight loaders' coordinate
conversion, indel anchoring, INFO parsing, per-ancestry alignment, and ClinVar identifier semantics
correct — and found two real defects. The documentation lens verified the scoring modules, all 17
model cards, the README (LGTM), and the CHANGELOG accurate — and found four factual doc contradictions.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(data)` dbSNP contig naming | data-registry | dbSNP was the one loader never given the contig-naming reconciliation its siblings have. A bare `MT` rsID → `chrMT` (hg38 uses `chrM`), so a mito variant resolved via `dbsnp.locus` carried a contig absent from the reference — silent miss; and `rsids_at` keyed `_by_chrom` raw, so a bare `2` interval returned `[]` while `chr2` returned records. **Shipped:** key on `canonical_contig` (index + query), map `MT`/`M` → `chrM`. The recurring reference-vs-source naming class, in its last un-reconciled loader. |
| `fix(data)` symbolic-ALT skip | data-registry | ClinVar's filter skipped only `ALT` in `.`/empty, so a spanning-deletion `*` or symbolic `<DEL>` (real releases contain them) reached the allele validator, raised, and aborted the *entire* `from_vcf` — losing every valid record after it. dbSNP shared it; gnomAD silently stored garbage. **Shipped:** a shared `is_sequence_allele` guard in all three loaders skips a non-`ACGTN` row and continues. |

**Documentation (`docs:`, all doc-only — no code bugs):** population.md said CFD *defaults* to the
seed-tolerance approximation (backwards — it defaults to the published Doench matrix; the approximation
is opt-in) with a "400-value" matrix (it has 240); data.md gave the contig-normalization direction as
UCSC-ward (it reconciles via the bare canonical form); the index.md uncertainty snippet passed
`calibrated=True` without noting it is coerced to `False`; and `gc_content`'s docstring said
"unambiguous" while the code counts the strong code `S`. All four verified by running the code and
corrected. The population.md one was honesty-relevant — it claimed the default scorer is an
approximation when it is the published matrix.

Yield ...1/1/2. **Lesson: the *ingestion* seam (external record → Variant/frequency) is a distinct,
productive axis from the *resolution* seam — dbSNP had missed a naming reconciliation every sibling
received, and one malformed VCF row could silently discard a whole release. And a documentation-vs-code
sweep is worth running periodically: docs drift as behavior changes (the CFD default flipped from
approximation to published matrix on 2026-07-08, but population.md still described the old default).**

Each change folder contains `proposal.md` (Why / What Changes / Impact), `tasks.md` (an
ordered checklist), and `specs/<capability>/spec.md` (the ADDED/MODIFIED requirement
deltas). When a change ships, fold its deltas into `specs/` and archive the folder.
