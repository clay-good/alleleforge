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

## Round 21 — the OUTPUT surfaces: cloning oligos + report rendering (3 fixes)

Two lenses on what the researcher actually *takes away* — the ordered oligos and the rendered report.
Both found real defects on hardened surfaces (each verified clean elsewhere: U6-G/reconstruct/revcomp/
scaffold on the oligo side; rank order, worst-ancestry selection, and cross-surface efficiency/interval/
specificity agreement on the report side).

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(oligos)` 3' junction screen | oligo-output | The Type IIS enzyme screen covered the 5' overhang/insert junction (a prior fix) but screened only `top` (= `top_overhang + insert`), which stops at the insert's 3' end. In the ligated plasmid the top strand runs `top_overhang + insert + revcomp(bottom_overhang)`, so a site straddling the 3' seam shipped clean — on the **default** BsmBI scheme a spacer ending `GAGAC` + the `AAAC` bottom overhang reconstitutes `CGTCTC` on the antisense oligo (a silent Golden-Gate failure). **Shipped:** screen `top + revcomp(bottom_overhang)` for sgRNA and pegRNA — both junctions, both strands, one pass. |
| `fix(reporting)` chart safety-honesty | reporting | The off-target-by-ancestry figure plotted an *unsearched* candidate (`n_offtarget_sites is None`) as `0.0` in every ancestry — the lowest/safest bar — while the text body showed nothing; the chart could flip a visual ranking toward the least-evidenced guide (the "safety unknown as safety-clean" class). **Shipped:** skip unsearched candidates; a searched zero-site candidate still plots `0.0`. |
| `fix(reporting)` PDF rationale | reporting | The PDF renderer dropped each candidate's ranking `rationale`, though HTML and JSON render it and the report spec lists it — the printable leave-behind omitted *why* a candidate ranks where it does. **Shipped:** emit it in `_candidate_lines`. |

Yield ...1/2/3. **Lesson: the OUTPUT surfaces (oligos, report renders) are a productive axis of their
own — the science can be right while the artifact the researcher orders/prints is cloning-lethal or
paints "unknown risk" as "safest." Audit what leaves the tool, not only what it computes; and a
"safety unknown rendered as safety-clean" bug recurs across axes (ranking R10/R11, now the chart).**

## Round 22 — genome-access reference layer + CLI end-to-end (2 fixes)

Two lenses, each clearing its primary surface and finding one real defect. The genome lens verified
reference fetch edges (boundary/empty/over-run padding), N-runs/soft-masking (upper-cased), coordinate
math, and liftover fail-closed all correct. The CLI lens verified exit codes, `--weights`, config
precedence, batch, and verify all correct.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(data)` annotations contig naming | data-registry, genome-access | `GeneModels` and `EncodeTracks` keyed/queried `_by_chrom`/`_segments` by the *raw* contig, so a bare-named (`11`) query against a chr-named (`chr11`) GTF/bedGraph returned `[]` genes / `0.0` signal — the `.get()` missed before the naming-aware `overlaps` ran. Feeds transcript selection (resolver) and prime-editing efficiency, so a naming mismatch silently designed on an empty result. **Shipped:** key on `canonical_contig` (construction + lookup), merging spellings — the last two un-reconciled loaders in the recurring naming class. |
| `fix(cli)` --cache-dir honored | cli | The global `--cache-dir` was declared and stored but read nowhere: `design`/`batch` forwarded only the seed, and the cache root is consumed process-wide via the `get_settings()` singleton the CLI never configured. A user redirecting the cache (CI, sandbox, read-only home) was silently sent to `~/.cache/alleleforge`. **Shipped:** the root callback exports `ALLELEFORGE_CACHE_DIR`, redirecting every consumer at once (env > file > default), safe because the singleton loads lazily after the callback. |

Yield ...2/3/2. **Lesson: the recurring contig-naming class had TWO more instances (GeneModels,
EncodeTracks) even after the dbSNP fix a round earlier — when a bug class recurs, grep EVERY sibling
(`_by_chrom`/`.get(...chrom)`) in one pass rather than fixing instances as lenses surface them. And a
parsed-but-unconsumed CLI flag (`--cache-dir`) is the "flag honored?" class on the config axis.**

## Round 23 — web-API lifecycle + model-zoo gates + fail-open-gate sweep (3 fixes)

Two lenses on the remaining fresh surfaces; both agents crashed mid-run (stream watchdog / API error)
but each had already reproduced its finding, verified and shipped here. The web lens otherwise cleared
the job state machine, result fidelity, error paths, and endpoint contracts; the model-zoo lens cleared
the license and consent gates and the download-path checksum gate.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(web-api)` invalid weights → 422 | web-api | `/api/design` and `/api/batch` build `RankingWeights` from the request without catching its `ValueError`, so a well-typed but invalid weights vector (negative / all-zero / non-finite) leaked an unhandled **500** instead of a **422** — the web sibling of the CLI `--weights` hardening. **Shipped:** `_design_options` catches the validation error and raises `HTTPException(422)`. |
| `fix(model-zoo)` cached-unpinned fails closed | model-zoo | `ModelRegistry.checkpoint` refuses to *download* an unpinned checkpoint, but the **cached** branch only re-verified when the card *pinned* a hash (`elif checkpoint_sha256 is not None`), so a file at the cache path for an unpinned card (all cards but `rule-set-3`) was returned **unverified** — a fail-open bypass of "a pinned hash is required to load," contradicting the method's own docstring. **Shipped:** the cached branch fails closed on an unpinned card, exactly like the download path. The sibling of the R16 content-addressed-cache fail-closed fix. |
| `fix(data)` cached-unpinned dataset fails closed | data-registry | **Found by a proactive sweep** for the same class immediately after the model-zoo fix: `DatasetRegistry.resolve` had the identical structure — download-branch refuses an unpinned dataset, cached branch (`elif desc.sha256 is not None`) returned an unpinned cached file **unverified**. **Shipped:** the cached branch fails closed, matching the download path, the docstring, and the `test_resolve_without_checksum_refuses` intent; the user-provides-file workflow is unaffected (it uses the loaders' explicit-path API, not this gated fetch). |

Yield ...3/2/3. **Lesson: a **fail-open trust gate that only fires on one branch** recurs across the
codebase — content-addressed cache (R16: missing sidecar), model checkpoint gate, and dataset resolve
(both this round: cached vs download). When a gate has two entry paths (download/cache, top/bottom
junction, 5'/3' overhang), verify BOTH fail closed — and after finding one, GREP THE CLASS: the
proactive sweep for `sha256 is not None` verify branches turned up the third gate immediately, closing
it before a lens had to. Two agents crashing mid-run still delivered — a reproduced finding in an
agent's last message is actionable even when the agent doesn't finish.**

## Round 24 — five parallel lenses on the compute core: offtarget/ranking/benchmark/uncertainty (3 fixes, 2 clean bills)

Five independent lenses, each a fresh reconstruction of one under-audited compute surface. Three found
real, test-pinned defects; two returned rigorous clean bills with strong credible-negatives. Every one
of the three defects is an instance of a class this method has hit before — an output-changing input
that a cache key forgot, a non-finite value that a `max()` launders into a perfect score, and a real
danger rendered safe because its attribution was unknown.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(offtarget)` on-target keys the cache | offtarget-scoring, offtarget-nomination | The cross-run reference cache keyed on `regions` but **not** on `on_target` — the locus the engine drops as the guide's own self-match. Two `search()` calls that differ *only* in `on_target` collided on one key, so the second was served the first's report: a bare scan served an on-target-excluding report **silently hides a perfect-score (1.0) off-target**, and the reverse **counts the self-match** and understates specificity. Its sibling filter `regions` was already in the key — `on_target`, equally output-changing, was forgotten. **Shipped:** fold `on_target` into `search_signature` (naming-aware, exactly as `_is_on_target` matches), so an `on_target` change is a cache miss. The "cache key omits an output-changing input" class. |
| `fix(types)` distribution masses must be finite | uncertainty-contract, benchmark-harness | `Prediction._check_interval` checked point-estimate finiteness only for a **scalar** `value`; a **distribution**-valued prediction (outcome→mass mapping) had its masses unchecked. An `inf` mass then makes `kl_divergence` normalize to `nan`, and `max(0.0, nan)` collapses to a **perfect `0.0`** on that lower-is-better metric — a broken distribution scorer tops the `cas9-outcome`/`be-outcome` leaderboards with a finite `0.0` headline that sails past the finite-`primary_value` validator. **Shipped:** give the Mapping case the same finiteness guard the scalar branch has (rejects a corrupt `Prediction` at construction/deserialization), plus defense-in-depth in `kl_divergence` — a non-finite mass returns `+inf` (the *worst*, direction-aware), not `0.0`. The "NaN/inf laundered into a perfect score" class, on the metric where the degenerate value's *direction* was itself the trap. |
| `fix(offtarget)` unattributed off-target floors every stratum | offtarget-scoring, candidate-ranking | `ancestry_stratification` routed a site into every ancestry's worst case only when it was a reference or patient (`frequency is None`) site. A **population** site with a known frequency but an **empty per-ancestry breakdown** (a report built from a global AF with no stratum split) was neither — so it vanished from every stratum, while `expected_burden` still counted it as a real hit. Once any benign ancestry-tagged site made `worst_ancestry()` non-`None`, the ranking safety axis switched to the stratified path that never saw the danger: a CFD-0.9 hit rendered as safety 0.8 instead of 0.1. **Shipped:** a site whose per-ancestry attribution is unavailable (reference, patient, **or** known-frequency-but-empty-breakdown) contributes to every stratum, restoring consistency with `expected_burden`. The R11 patient-masking fix, generalized to its last un-covered site shape — the recurring "safety-unknown rendered as safety-clean" class. |

**Clean bills (2):** the **off-target scoring** lens cross-checked `cfd_score` against an independent
CRISPOR `calc_cfd` reconstruction over 20,000 random 20-nt/0–5-mismatch cases (max abs diff **5.55e-17**)
and `mit_score` against `calcHitScore` over 50,000 cases (**bit-identical**), and cleared the seed-and-extend
superset, the aggregate, the fallback relabeling, and the weight-range gate — one honestly-deferred `N`-base
edge flagged for a future nomination round. The **uncertainty-contract** lens confirmed the long-deferred
`Prediction.calibrated` round-trip finding is now **closed** (the gate acts on the raw input mapping; nesting
never downgrades a built prediction), and cleared calibration/interval/coverage math and the OOD width floor.

Yield ...3/2/3/3. **Lesson: the three live compute-core defects were the same three classes this method
keeps surfacing, wearing new clothes — (1) a cache/trust key that omits an output-changing input (`on_target`,
like R23's cache branches and R22's `--cache-dir`), (2) a non-finite value a reduction launders into a perfect
score (here the trap was *direction*: `0.0` is worst for correlation but perfect for a divergence), and (3) a
real danger rendered safe because its attribution was unknown (R10/R11 safety-unknown-as-safe, now the empty
ancestry breakdown). When a bug class recurs, the productive move is to ask where else the same shape hides:
`on_target` was the forgotten sibling of an already-keyed `regions`; the Mapping value was the forgotten sibling
of an already-guarded scalar; the empty-breakdown population site was the forgotten sibling of the already-fixed
patient site. Fresh parallel reconstruction plus a strong CFD/MIT cross-check clean bill is the R6/R13/R19
diminishing-returns signal that the *scoring math itself* is empirically solid — the remaining defects live at
the seams (cache keys, contract edges, attribution gaps), not in the formulas.**

## Round 25 — the output/provenance/native seams: viz, provenance, native-kernel parity (1 hardening, 2.5 clean bills)

Three lenses on surfaces this session hadn't touched: the visualization output, the provenance/
reproducibility contract, and native-vs-Python kernel parity. **No new reachable production defect** —
a strong diminishing-returns marker (the R6/R13/R19 signal) that these seams are empirically solid.
The round shipped one proportionate defense-in-depth hardening and re-confirmed the one known-deferred
item is still contained and already pinned where it lives.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(viz)` validate color attributes | visualization | The SVG renderer rigorously escapes every **text node** (title, labels, series names, rationale — pinned by `test_text_is_escaped`), but `Series.color`/`ReferenceLine.color` are interpolated straight into `fill=`/`stroke=` **attributes**, which the text-node escaper does not cover. A color carrying `"`/`<`/`>` would break out into a `<script>` — the exact R12 injection class, on the one caller-controlled value that reaches an attribute. **Not exploitable today** (every color is a `PALETTE`/`_INK` hex constant; no untrusted→color data flow exists), so this is a latent asymmetry, not a live vuln — but text-is-escaped-while-color-is-trusted is precisely the kind of seam that bites a future caller who wires a theme/user color. **Shipped:** validate `color` to a hex code or bare CSS name at `Series`/`ReferenceLine` construction (a color with markup is never legitimate, so reject rather than escape), with a test mirroring `test_text_is_escaped`. |

**Clean bills (2, plus one re-confirmed deferral):**
- **native-kernel parity** — differential fuzzed the three native/Python kernel pairs (k-mer seed, haplotype
  materialize, FM-index count/locate) over **400,000+** randomized cases including the boundaries the suite
  skips (empty seq, pure-insertion `ref`, seq shorter than seed): **zero result-level divergences** on every
  reachable (ACGTN-validated) input. The only reachable native-vs-Python difference is the FM-build error
  *message* text (native reports the first bad byte, Python the full sorted set) — both fail closed with a
  `ValueError` naming `ACGTN`; cosmetic, would churn the Rust crate to align, deferred. Two further divergences
  (negative `k`, non-ASCII bytes) are provably unreachable behind the caller's `k>=5` gate and the `^[ACGTN]*$`
  input validation.
- **visualization text/HTML escaping** — the R12-class text-injection defense holds end-to-end: `report/html.py`
  routes every user string through `html.escape(quote=True)` and JSON-neutralizes the Plotly-in-`<script>` path
  (the documented R12 fix), and `svg.py` escapes every text node. Only the color-attribute asymmetry above was open.
- **provenance/reproducibility** *(re-confirmed deferral, not a new hit)* — every `Provenance` field round-trips;
  the benchmark digest/signature and design-menu hash are byte-stable across `PYTHONHASHSEED` variation; the R24
  cache-key fix is present. The one round-trip asymmetry is the **known, deliberately-deferred**
  `Prediction.calibrated` gate: a plain (untrusted) reload of a calibrated prediction coerces `calibrated=False`
  (anti-forgery), and only a trusted-context reload preserves it. This is by design and **already pinned at the
  Prediction level in both directions** (`test_serialized_output_reports_true_and_round_trips_under_trust`,
  `test_untrusted_deserialization_cannot_forge_calibration`); the default `af design` pipeline emits no calibrated
  prediction and the CLI's own reload threads the token. Per the standing judgment that honest deferral beats
  rushing this load-bearing honesty mechanism, the gate is left untouched.

Yield ...3/2/3/3/1. **Lesson: after the R24 sweep of the compute core, a fresh sweep of the output/provenance/
native seams turned up no new *reachable* production bug — three empirically-clean surfaces and one latent
attribute-escaping asymmetry worth closing proactively (text-escaped-but-attribute-trusted is the injection
class one seam over). The productive signal here is a *negative*: 400k+ differential-fuzz cases with zero
kernel divergence, byte-stable digests under hash-seed variation, and a re-confirmed-contained deferral are the
diminishing-returns marker that the seams are sound. When the reachable defects dry up, the honest move is to
harden the latent asymmetry, pin the deferral where it lives, and say so — not to manufacture a marginal find.**

## Round 26 — the efficiency-scoring engine internals (2 clean bills; diminishing-returns confirmed)

Two lenses on the numeric heart not directly swept this session: the prime/PRIDICT efficiency engine and
the cas9/base-editor efficiency + outcome engines. **Both returned rigorous clean bills** — no code change.
This is the conclusive R6/R13/R19 diminishing-returns marker for the scoring math: after R24's three
compute-core fixes, the last two rounds (R25 output/provenance/native, R26 scoring engines) are dominated by
credible negatives, not defects.

- **prime/PRIDICT efficiency** (`prime_efficiency.py`, `pridict_engine.py`, `backbone.py`) — actively
  *disproved* three candidate defects with evidence rather than manufacturing a finding: the `_nick_to_edit`
  recovery matches the enumerator's own geometry exactly for every reachable SNV pegRNA (rtt∈{7,20,34},
  homology∈{5,6,7,13}); every feature direction is correct (PBS length peaks at the published ~13 nt optimum
  and falls both sides, nick-to-edit strictly decreasing, epegRNA motif +logit); and no value/interval escapes
  `[0,1]` (`_sigmoid` clamps, logit analytically bounded, empty-`_gc` guarded). The fixed ±0.15 band on the
  heuristic scorers is intentional and honestly labeled (`NOMINAL_INTERVAL_NOTE`), consistent across all three
  fixed-band scorers — the OOD-widening contract binds the *ensemble* path.
- **cas9/base-editor efficiency + outcome** (`cas9_efficiency.py`, `cas9_outcome.py`, `base_outcome.py`) — all
  seven hunted classes negative: every outcome distribution normalizes to 1.0 (±1e-12) including degenerate
  contexts; the base-editing window index (`spacer[position-2]` 5' neighbor, `by_basepos.get(p-1)` 1↔0-based
  bridge) is correct; efficiency (`p_target_edited`) and cleanliness (`p_intended_exact`) stay distinct; no
  `[0,1]` escape or NaN laundering; and `ensemble_outcome` is byte-identical across `PYTHONHASHSEED` ∈ {0,1,42,
  12345} on a tie-prone input (the R9 determinism class stays closed).

**Two honest non-defect observations (documented, not fixed — maintainer/spec territory):** (1) the ePRIDICT
open-chromatin adjustment is implemented and unit-tested on `PridictScorer.score` but **not wired into the
default `design_prime` path** (the `PrimeEfficiencyScorer` Protocol omits the `chromatin` param), so it is only
reachable by calling the scorer directly — an integration gap, not a scoring-math bug, and not required by the
prime-editor-design spec; wiring a new feature param through the design layer is speculative machinery absent a
spec requirement (the R14 "honest defer to avoid speculative machinery" discipline). (2) the cell-context string
convention differs between the baseline (`HEK293T`) and the engine (`HEK`); they never compare against each other
so there is no live bug, but a user passing `cell_context="HEK"` to the default baseline path would get a spurious
OOD flag — cosmetic/ergonomic.

Yield ...3/3/1/0. **Lesson: three rounds this session rotated compute-core → output/provenance/native →
scoring-engines; R24 found three real defects, R25/R26 returned to credible negatives (400k+ kernel fuzz, CFD
5.55e-17 / MIT bit-identical cross-checks, all-classes-negative scoring-engine probes, multi-seed determinism).
That convergence to clean across independent fresh decompositions is the signal that the empirical core is sound
and the remaining gaps are maintainer/spec-driven wiring choices (chromatin) or externally-blocked (real-weights
forward pass) — not autonomously-shippable bugs. The discipline holds: audit, reproduce, ship what's real, and
name the clean bills and honest deferrals rather than manufacturing a marginal find.**

## Feature — wire the ePRIDICT open-chromatin adjustment into the design path (1 change, spec-driven)

Unlike the audit rounds above, this is a **spec-driven feature**: R26 flagged that the ePRIDICT
open-chromatin efficiency adjustment was implemented on `PridictScorer.score` but **unreachable
through `design_prime`** (the `PrimeEfficiencyScorer` Protocol did not expose the `chromatin`
parameter, and no spec covered it). Rather than autonomously wire a feature with no spec behind
it, R26 documented it as a maintainer/spec decision. This change authors that spec and implements
it (proposal + tasks + a new `prime-editor-design` requirement, folded in and archived under
`archive/wire-chromatin-efficiency`).

| Change | Capabilities | What shipped |
|--------|--------------|--------------|
| `feat(prime)` chromatin-aware efficiency | prime-editor-design | Expose `chromatin` on the `PrimeEfficiencyScorer` protocol and thread optional `encode_tracks` / `chromatin_track` through `design_prime`: each pegRNA is scored with the ENCODE accessibility signal at its own edit locus, so a variant in open chromatin is predicted to edit better. **Opt-in and honesty-preserving:** no tracks → the pure pegRNA-geometry baseline, byte-identical to before (an existing-caller regression test pins this); the adjustment only scales the point estimate and **never flips the OOD flag** (an OOD context stays OOD after a boost); an uncovered locus (signal 0) is a **no-op**, never a penalty for missing data; a mis-named track **fails closed** (raises) rather than silently returning an unadjusted efficiency labeled chromatin-aware; and a chromatin-adjusted candidate **records the adjustment in its rationale** so a researcher can tell it from a pure-geometry one. Six scenarios pinned in `tests/design/test_prime.py`. |

**Note:** this closes the primary spec-able deferral surfaced this session. The sibling observation —
the cell-context string convention differing between the baseline (`HEK293T`) and the engine (`HEK`) —
was deliberately **not** changed: treating the ambiguous `"HEK"` as in-distribution would *weaken* the
honesty flag (falsely asserting training-context confidence for a non-training cell line), so the
current spurious-OOD-on-`"HEK"` behavior is the safe, honest direction and is left as-is.

## Round 27 — four parallel lenses on the least-swept surfaces: data-ingestion, variant-resolution, cohort/population, report-render (4 fixes, strong clean bills)

After R24–R26 converged to clean on the compute core, this round rotated to the surfaces *not*
dedicated-swept this session and deliberately away from the scoring math: the external-record ingestion
seam, HGVS resolution, the cohort/haplotype path (never given its own round), and the human-facing
renders. Four independent lenses each cleared its primary surface with credible negatives and found one
real, test-pinned defect. Every one is an instance of a class this method has hit before.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(data)` ClinVar combined-assertion CLNSIG | data-registry | ClinVar joins the primary clinical class with a secondary assertion in one comma-separated `CLNSIG` token (`Pathogenic,_risk_factor`, `Likely_pathogenic,_low_penetrance`) — the form carried by HFE C282Y, Factor V Leiden, prothrombin G20210A. `_normalize_significance` exact-matched a single-token map and defaulted every combined form to `OTHER`, silently dropping the pathogenic signal a `{PATHOGENIC, LIKELY_PATHOGENIC}` filter keys on. **Shipped:** classify by the primary assertion (token before the first comma), preserving verbatim `raw_significance`. The recurring "real annotation rendered inert on its own axis, green suite" class. |
| `fix(variant)` HGVS dup/delins stated-base validation | variant-resolution | A `dup`/`del`/`delins` may state its bases (legal HGVS). `to_variant` short-circuited the reference read on any stated bases, so a `dup` produced `ref=""` and the resolver's `_validate_ref` early-returned — the reference was never consulted. `chr2:g.6_7dupCC` against a reference reading `AC` fabricated an insertion of the un-checked `CC` while the identical `del` failed closed; a stated-base `del` also discarded the span length (`g.6_8delAC` → a 2-base deletion). **Shipped:** validate stated `dup`/`del`/`delins` bases against `reference[start:end)` (identity + length) when a reference is present. The "fail-closed gate with a hole on one branch" class, in the resolver's wrong-build guarantee. |
| `fix(offtarget)` haplotype KeyError at maf=0 | offtarget-nomination | `enumerate_haplotype_sites` filtered carrying populations with `frequencies.get(p, 0.0) >= min_freq`; at `min_freq <= 0` an unrecorded population passed (`0.0 >= 0.0`) and then `KeyError`'d at `frequencies[p]`, aborting the whole search. CLI-reachable via `off-target --maf 0 --populations AFR,EUR,…`, and a haplotype carrying only a subset of super-populations is the norm. **Shipped:** require the population to be *recorded* in `frequencies` (no known frequency → does not carry), matching the population-variant path's robust behavior. |
| `fix(reporting)` uncalibrated interval marked nominal | reporting, uncertainty-contract | Every default scorer emits `calibrated=False` (a nominal ±0.15 band, per `NOMINAL_INTERVAL_NOTE`), yet HTML/PDF surfaced only `in_distribution` and printed `@ 80%` — indistinguishable from a measured 80%-coverage band — and the TSV/Parquet export had no `calibrated` column at all. The `Prediction` contract says a consumer thresholding on `interval_level` should see the caveat "in the notes"; the report dropped it. **Shipped:** append `(nominal — coverage not measured)` to an uncalibrated efficiency/bystander line (mirroring the OOD qualifier), and add a `calibrated` export column (schema 1 → 2). Reads only the already-correct in-memory flag; does not touch the deferred `Prediction.calibrated` serialization round-trip. The R21 "safety-unknown rendered as safety-clean" class, on the calibration axis. |

**Clean bills (strong credible-negatives):** the data lens cleared gnomAD AF selection (overall∪population max, no multi-allelic index misalignment), dbSNP `chrM` mapping, symbolic/spanning-`*` skipping, and both registry fail-closed gates. The variant lens cleared 0/1-based conversions, left-alignment through repeats, insertion anchoring, VCF multi-allelic/symbolic handling, and liftover fail-closed. The cohort lens cleared the de-novo/strengthen nomination gate (a "same-placement, equal-score, fewer-edits" mask is not constructible with any position-sensitive scorer), the indel coordinate lift (byte-exact vs a brute-force map on the untested deletion+downstream-substitution combination), minus-strand PAM creation, and cohort key injectivity. The report lens cleared HTML/SVG/PDF injection, off-target chart arithmetic/ordering, and TSV column order.

Yield ...3/3/1/0/4. **Lesson: rotating to the least-swept surfaces — ingestion, resolution, cohort, render — after the compute core converged clean yielded four real defects in one round, each a known class recurring on a fresh surface: an annotation inert on its own axis (ClinVar), a fail-closed gate with a hole (HGVS dup), a degenerate-input crash reachable from the CLI (haplotype maf=0), and safety-context dropped at the render (calibration). The compute math is empirically solid; the productive defects now live at the seams where an external record enters or a computed honesty flag leaves.**

## Round 28 — three lenses on the last un-swept compute/routing/index surfaces (0 fixes; 3 clean bills — diminishing-returns confirmed)

After R27's four fresh-seam fixes, this round swept the surfaces not yet dedicated-audited this session:
variant effect/consequence prediction + config/cache precedence, design routing + ranking composite +
designer orchestration, and the FM-index/suffix-array build + sequence-embedding backbone. **All three
returned rigorous clean bills** — no code change — the R6/R13/R19/R26 diminishing-returns marker on these
surfaces.

- **variant effect + config + cache** — every defect class disproved against a concrete input: the SO
  severity ranking is strictly monotone (frameshift never below missense, stop-gain never missed),
  transcript selection applies exact→MANE→canonical→first in separate passes (a merely-canonical block
  can't beat MANE), config precedence holds default < file < env < override across all four combinations,
  and the VEP cache key carries every output-determining input (variant, assembly, transcript) with no
  missing axis or spurious collision. Two honest latent non-bugs noted (the unreachable pure-insertion VEP
  region convention on the never-exercised live GET path; a safe-directional impact from an unmodeled SO
  term) — neither test-pinnable.
- **routing + ranking + designer** — routing gates on the *same* `installs()`/SNV predicates enumeration
  uses (no chemistry advertised that can't be delivered); the base-editor efficiency vs cleanliness axes
  stay distinct (`p_target_edited` vs `p_intended`); `_dominates` is correct and the Pareto front is
  post-cap-aligned by design; the safety axis folds every unattributed site (reference/patient/empty-
  breakdown) into every stratum so `worst_ancestry() ≥ worst_score()` always holds (R11 class robust); and
  the OOD-discounted efficiency feeds composite and Pareto consistently. The only residual tie-break case
  is the already-fixed same-spacer full-vector tie.
- **genome index + backbone** — the pure-Python suffix array is byte-identical to a naive sort over
  thousands of strings; `locate`/`count` matched `str.find` over **~612,000** queries across
  checkpoint/sampling rates (0 mismatches, mmap and in-memory); `pam_sites` matched a brute-force scanner
  over **18,000** degenerate-PAM/N-laden cases; contig-alias reconciliation (`chr1↔1`, `chrM↔MT↔M`) does
  not over-match (`chr1` never resolves to `chr11`); and the backbone's hash/tokenizer embedding is
  deterministic (no one-hot/positional encoding lives here, so that defect class does not apply).

Yield ...3/3/1/0/4/0. **Lesson: R27 found four defects at the ingress/egress seams; one round later, three
independent rigorous lenses on the adjacent compute/routing/index surfaces all return clean — the same
convergence signal seen at R6/R13/R19/R26. The productive vein is the *seams* (external record in, honesty
flag out, CLI-reachable degenerate input), not the numeric/routing/index core, which is now empirically
clean across many independent fresh decompositions. Record the clean bills honestly rather than manufacture
a marginal find.**

## Round 29 — three lenses on the deferred/fresh seams: VEP live-REST, cross-interface parity, doc-vs-behavior (2 fixes, 1 clean bill)

Prompted by R28's own "rotate to a seam not yet swept" note, this round took the three fresh seams the
audit log had flagged: the VEP live-REST path (deliberately deferred in prior rounds as opt-in / `#
pragma: no cover`), a cross-interface parity re-sweep (Python API vs CLI vs web), and a doc-vs-behavior
sweep of the Round 27 changes. Two lenses found a real, test-pinned defect; the doc sweep confirmed the
R27 docs are accurate.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(variant)` VEP insertion region convention | variant-resolution | `VepRestPredictor.request_url` computed the region end as `start + max(len(ref), 1) - 1`. For an insertion (`ref=""`, which `normalized()` produces with no anchor base) the `max(..., 1)` clamp emitted a 1-base region (`17:101-101/ACGT`) that VEP reads as a substitution consuming the base at that position — a consequence for the wrong span. VEP's convention for an insertion is a zero-width region (`start = end + 1`). **Shipped:** `end = start + len(ref) - 1`, correct for every class (SNV/deletion/MNV unchanged; insertion → `start - 1`). The "green suite, wrong answer" class on a path that was tested only with SNVs. |
| `fix(cli)` batch honors chemistry/cell_context config | cli | `chemistry` and `cell_context` are whitelisted config keys (no typo warning), and `design`/web `/api/batch`/`design_many` all honor them — but CLI `batch` read neither, so a `config.toml` restricting chemistry or setting cell_context was silently dropped for a whole cohort (menus carried every chemistry, provenance `cell_context = None`), diverging from the same run on every other interface with no user signal. **Shipped:** `batch` reads both keys and forwards them to `design_many`. The R22 "flag parsed/whitelisted but not consumed" class, now on the `batch`-vs-everything-else parity axis. |

**Clean bill:** the doc-vs-behavior lens verified all five Round 27 changes against the docs and found no drift — the export schema-2 `calibrated` column, the `(nominal — coverage not measured)` interval qualifier, the ClinVar primary-token classification, the HGVS stated-base validation, and the `--maf 0` haplotype behavior are each either accurately documented or not described (nothing to contradict); it also re-confirmed the R20-fixed CFD-default passage, the dataset versions, and the off-target thresholds still match the code. The VEP lens noted one honest deferral (the assembly→host/species routing places the build in the species path rather than the `grch37.rest.ensembl.org` host — network-only, `# pragma: no cover`, and pinned as intended by an existing test), left as-is.

Yield ...3/3/1/0/4/0/2. **Lesson: R28's diminishing-returns marker on the compute/routing/index core did NOT mean the audit was exhausted — rotating to the seams the log itself had flagged (a deferred opt-in path, cross-interface parity, doc drift) still yielded two real defects: a wrong VEP region for the one variant class its tests never exercised, and a whitelisted-but-unread config key that made `batch` diverge from every other interface. The productive vein remains the seams — a deferred path tested on the happy class only, and a run recorded differently on two surfaces — exactly as R15/R22 found. Keep a running list of un-swept seams; when the core converges clean, that list is the backlog.**

## Round 30 — three lenses on the un-swept seams the log listed: off-target adapter, data/bench CLI, benchmark loaders (1 fix, 2 clean bills)

Took the "still-un-swept seams" the R29 log named. Two returned rigorous clean bills; the `data`/`bench`
CLI lens found one real defect — the seed-provenance class, recurring on a new interface.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(benchmark)` bench-run seed provenance consistency | benchmark-harness, provenance-reproducibility | `run_benchmark` captured `provenance.seed` from its `seed` argument but `config_snapshot` from the `get_settings()` singleton, which the CLI never updates with `--seed`. `aforge --seed 777 bench run <task>` recorded `provenance.seed = 777` while `config_snapshot["seed"] = 20240501` (default) — a self-contradictory, non-re-derivable provenance block on a *signed* result (the signature verifies the contradictory body, so tamper-detection stays silent). **Shipped:** apply the run's seed to the resolved settings before snapshotting, so `provenance.seed == config_snapshot["seed"]` for every caller — the design path's invariant. The R15 batch-seed-provenance class, on the `bench run` interface. |

**Clean bills:** the **off-target-adapter** lens verified the cas-offinder parser's coordinate/strand/mismatch conventions (the minus-strand `pam_len` shift reconciles exactly against the internal scan's own convention), the format discriminator (6- vs 8-column) cannot misclassify, and the off-target cache key folds in every result-affecting input while the excluded ones are provably inert under `cache_eligible` — and confirmed the adapter feeds only the standalone `disagreements` cross-check, never merged into a report, so there is no merge seam. The **benchmark-loader** lens verified prediction↔label alignment is bulletproof by construction (a single shared `examples` list feeds both sides, `zip(strict=True)` everywhere), split load order is deterministic, metric argument order/KL direction are correct, and split disjointness/leakage is enforced — one honest latent non-bug noted (an intra-fold duplicate id would double-weight, but requires an adversarially hand-crafted hash-consistent split, absent from all shipped data).

Yield ...4/0/2/1. **Lesson: the running list of un-swept seams keeps paying out — the `bench run` seed-provenance divergence is the exact R15 batch-seed class on a new interface, confirming that once a class is found it should be swept across EVERY interface that stamps provenance (design ✓ R15, batch ✓ R15, bench ✗ until now). The two clean bills (external-tool adapter, benchmark loaders) are credible negatives that further narrow the un-swept surface. A signature that verifies a self-contradictory body is not integrity — internal consistency of the signed content is its own audit axis.**

## Round 31 — two lenses on the aggregation/leaderboard surfaces (0 code fixes; 1 doc fix; 2 clean bills — diminishing returns)

Two lenses on the last un-swept report/benchmark surfaces: the report-builder aggregation (menu → DesignReport
flattening) and the leaderboard submission-validation + board rendering. Both returned rigorous clean bills;
the only finding was a factual docstring error.

- **report-builder aggregation** — every aggregate is a faithful delegation: no min/max inversion
  (`outcome_top` and `offtarget_by_ancestry` both sort worst/best-first correctly, `offtarget_specificity`
  uses `specificity_score()` not `worst_score()`), no ancestry mis-attribution or dropped stratum (traced
  through a two-population adversarial case), flags copied verbatim, every field read from the single source
  candidate, and Pareto-front indices aligned to the preserved menu order. Clean.
- **leaderboard** — the ranking direction is correct for every metric (`kl` ascending/lower-wins, everything
  else descending; the rendered arrow matches the sort), the admission gate enforces card completeness +
  per-result signature verification + model-name match + within-submission task uniqueness, tie-breaks are
  pure-data (no PYTHONHASHSEED dependence), and no cross-wiring of a cell to the wrong model. The two residual
  gaps (no `primary_value == metrics[primary]` cross-check, no canonical-metric restriction) are the
  explicitly-accepted self-signed threat model, not defects. Clean.

**Doc fix (`docs(report)`):** `build_report`'s docstring claimed the `variant` argument "falls back to
provenance if absent," but the code passes it verbatim (only `intent` has a fallback) and the config snapshot
carries no variant field, so the claimed fallback is impossible — an unbackable doc-vs-code contradiction (the
R19/R20 doc-drift class). Corrected to state the variant is recorded verbatim with no fallback.

Yield ...2/1/0. **Lesson: after R30's bench-seed fix, the two remaining benchmark/report surfaces
(aggregation, leaderboard) both return clean under adversarial tracing — the R6/R13/R19/R26/R28 convergence
signal, now covering essentially every seam this session enumerated. Across R27–R31 the seams yielded
4/2/1(+doc)/… on a clearly declining curve, and the one finding this round is a docstring, not a defect. That
is the honest diminishing-returns marker for the currently-reachable surface: the ingress/egress seams, the
compute/routing/index core, the CLI interfaces, and the report/benchmark output are all now swept clean or
fixed. A future session should either drive a genuinely new modality (concurrency-under-contention re-sweep,
property-fuzzing the R27–31 code paths) or await new feature code to audit — not re-sweep converged surfaces.**

## Round 32 — regression-hardening: adversarially fuzz this session's own changes (clean bill)

A closing pass that turns the audit lens on the session's own work (Rounds 27–31) rather than a new surface —
the discipline of proving a fix set robust before declaring done. Every change was driven with adversarial
inputs; all held.

- **ClinVar CLNSIG primary-token split** — empty primary (`,_risk_factor` → `other`), comma-only (`,` →
  `other`), multi-comma, slash-form-with-comma (→ `pathogenic`), whitespace/case, unknown primary: no crash,
  no misclassification (ClinVar class names never contain commas, only slashes, so the primary token is always
  the true class — the split only reclassifies strings that previously fell to `OTHER`).
- **HGVS stated-base validation** — length mismatch, `N`-vs-base, wrong bases, lowercase, a contig-end
  `ref_lookup` returning a short string, and `ref_lookup=None` (trusted, as documented): no valid variant
  wrongly rejected, no invalid one accepted.
- **haplotype pops filter** — negative `min_freq`, a recorded `0.0` frequency, empty/duplicate populations, a
  frequency exactly at threshold, an absent population at `min_freq <= 0`: no `KeyError`, correct inclusion.
- **VEP `request_url`** — deletion/SNV at pos 0, MNV/long-ref, insertion at contig start (`1-0`): no malformed
  region; the insertion's `end < start` is VEP's intended zero-width convention.
- **export `calibrated` column (schema 2)** — `efficiency=None` → blank cell (no crash), a genuine calibrated
  prediction preserved through nesting and round-trip, untrusted JSON downgraded: every row splits to exactly
  16 columns.
- **CLI batch chemistry/cell_context** — an invalid chemistry name → clean usage error (exit 2, no traceback);
  an empty list ignored; a malformed value degrades per-item under `design_many`'s failure isolation, no
  run-aborting traceback.
- **Fresh micro-surface — `report/oligos.py` Type IIS screen** — ~700,000 randomized spacer/RTT/PBS/motif
  combinations compared against a ground-truth scan of the full 76 nt constant scaffold context (BsaI +
  BsmBI): the module's 4-base-overhang junction model missed **zero** variable-touching enzyme sites; the only
  window it omits (a 5-scaffold-base straddle) can never complete a recognition sequence. The R21 3'-junction
  fix plus the scaffold context leave no uncovered cloning-lethal site.

**Session close (Rounds 27–32).** 7 code fixes + 2 doc fixes + 1 CI-gate fix (a `ruff format --check` gate that
had been red on `main` since the prior commit) + 9 clean bills, all pushed. The yield curve (4 / 0 / 2 / 1 / 0 /
0) is a sustained, evidence-backed diminishing-returns marker across every enumerated seam — ingestion,
resolution, cohort, render, effect/config/cache, routing/ranking/index, VEP, cross-interface parity, docs,
off-target adapter, data/bench CLI, benchmark loaders, report-builder, leaderboard — with the session's own
changes fuzzed clean. The remaining known gaps are externally-blocked (real model weights) or
maintainer/design-call (VEP GRCh37 host routing, the self-signed leaderboard threat model), not
autonomously-shippable defects. A future session should drive a genuinely new modality (a concurrency-under-
contention re-sweep, property-fuzzing) or await new feature code — not re-sweep converged surfaces.

## Round 33 — the new modality R32 called for: property-based fuzzing + concurrency-under-contention (1 fix, 5 clean bills)

R32 closed with an explicit instruction: the enumerated seams are swept, so a future session should "drive a
genuinely new modality (a concurrency-under-contention re-sweep, property-fuzzing) or await new feature code —
not re-sweep converged surfaces." This round did exactly that. Five invariant-rich surfaces that had unit tests
but **no property-based coverage** were fuzzed with `hypothesis` (the `types/` layer already had property tests;
the scientific transformation core did not), plus a concurrency stress of the parallel cohort path. The
variant/coordinate lens found one real, test-pinned defect — the recurring headline class — and the other five
surfaces returned credible clean bills under tens of thousands of examples each.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(variant)` full asserted-ref span validated before trimming | variant-resolution | Reference validation ran *after* parsimonious `normalized()` (called eagerly in the coordinate-family input adapters), so a wrong-build base sitting in a shared prefix/suffix — a position where `ref == alt`, which trimming removes — was discarded before `_validate_ref` saw it. `chr2:6 AT>GT` against a reference reading `AC` (the unchanged `T` disagrees) trimmed to `A>G`, whose retained `A` matches, so the resolver **accepted a wrong build and silently changed the caller's edit** (applying `A>G` → `GC`, not the asserted `GT`). The exact "safety input inert on its consumed axis with a green suite" class: the fail-closed check existed but its input was destroyed upstream. **Shipped:** the coordinate adapters (`VcfRecord.to_variant`, the `chrom:pos:ref>alt` parser, the raw-`Variant` branch) defer `normalized()` to `resolve`, which now validates the full un-normalized asserted span before `_left_align` trims it. RawTarget (validates against its embedded sequence) and HGVS (validates stated bases) were already safe. Regression tests (suffix-trim, prefix-trim, all three input forms) fail@HEAD → pass. |

**Clean bills (property-based, `hypothesis` 6.155.1):**
- **uncertainty & calibration math** (`scoring/uncertainty.py`) — 22 invariants held across ~800 examples each: `_pav` non-decreasing / idempotent / sum-preserving / bounded; isotonic monotone + bounded + deterministic; conformal `scale` finite and non-narrowing under OOD; OOD interval widening monotone with a strictly-positive floor on a zero-width interval (prior fix holds); quantile interpolation monotone and bracket-repaired; ECE ∈ [0,1] and 0 when confidence≡outcome. The one anomaly was a 1-ULP floating-point boundary tie in conformal self-coverage — not a defect (the documented guarantee is marginal-on-fresh-data, not deterministic self-coverage), verified over 400,000 targeted iterations.
- **off-target scoring / aggregation / cache key** — CFD & Cas12a scores ∈ [0,1], perfect match = 1.0, superset-monotone degradation; `specificity_score` non-increasing and `worst_score` non-decreasing as sites are added; the unattributed-off-target floors every ancestry stratum (prior fix holds); `search_signature` distinguishes every result-affecting field, folds inert ones (case, region order), and is byte-identical across `PYTHONHASHSEED ∈ {0,1,12345,99999}`; the scorer-identity omission from the key is proven safe by the engine's `scorer is None` cache gate; strengthened-detection regression stays fixed.
- **candidate ranking / oligo output** — composite bounded and monotone in each "higher-is-better" axis; Pareto front non-dominated and menu-aligned; OOD-discounted efficiency feeds composite *and* Pareto identically; deterministic across 5 hash seeds (incl. 40 identical-vector candidates forcing the identity tiebreak); composite-preserving truncation is a per-chemistry-capped subsequence; `revcomp` involutive and rejects non-DNA; the Type IIS (BsaI/BsmBI/BbsI) screen matched a brute-force both-strand scan on every fuzzed ligated-insert incl. the spacer/scaffold junctions; U6 5'-G added exactly once.
- **benchmark metrics core** (`benchmark/metrics.py`) — `pearson`/`spearman` ∈ [−1,1], `roc_auc`/`pr_auc` ∈ [0,1], `kl_divergence` ≥ 0, ECE ∈ [0,1], all held across ~800 examples each (already NaN/inf-hardened at R12).
- **content-addressed cache** (`cache.py`) — canonical sorted-key JSON digests stable across processes, atomic temp+rename with a per-call UUID for concurrent same-key writers, fail-closed verify on a missing/mismatched checksum sidecar; the `default=str` fallback is a documented caller contract.
- **cohort parallel path** (`design/cohort.py`) — a 16-worker contention stress produced no torn writes (every per-item JSON parsed), no duplicate or missing manifest rows, and the correct file count; manifest appends are main-thread-serialized and per-item output filenames are injective by construction (`_safe_name` digest).

Yield ...2/1/0/1. **Lesson: R32's diminishing-returns marker was scoped to the *modalities already run* (adversarial example-based lenses on the enumerated seams), not to the code itself — switching to property-based invariant fuzzing, a modality never applied to the scientific transformation core, immediately surfaced the same recurring headline class (a wrong-build safety signal laundered by an upstream transform, green suite) on the most-audited surface in the repo. The five clean bills are credible negatives precisely because property fuzzing explores the input space a hand-written example cannot. The productive vein is now the *modality*, not the surface: when example-based audits converge, a new proof technique (invariant fuzzing, concurrency contention, and next: metamorphic/differential testing against a reference implementation) is the backlog.**

## Round 34 — property-based fuzzing of the surfaces R33 did NOT cover: enumeration/design, scoring engines, effect/HGVS (4 fixes)

R33 fuzzed uncertainty, off-target, variant-coordinate, and ranking/oligo. This round pointed the same new
modality at the surfaces those four agents left untouched — the guide/edit **enumeration + design verticals**,
the **scoring engines** (efficiency/outcome predictors), and **effect/HGVS parsing**. Every enumerated reagent
was fetched back against the reference (metamorphic verification). Four real defects surfaced, one CONFIRMED
correctness bug in the prime flagship and three fail-open robustness gaps — each a recurring class on a
not-yet-fuzzed surface.

| Change | Capabilities | What was wrong / shipped |
|--------|--------------|--------------------------|
| `fix(prime)` RTT N-guard | prime-editor-design | The cas9/base-editor enumerators skip any emitted span covering a reference `N` (assembly gap); the prime enumerator N-guarded the spacer and ngRNA protospacer but **omitted the RTT window** — so a pegRNA whose RT template reached a downstream `N` was emitted as a valid but unsynthesizable design that would template an ambiguous base into the genome at the gap. `DNASequence` admits IUPAC `N` (for degenerate PAMs), so `PegRNA` construction never caught it. **Shipped:** N-guard the RTT window before templating, mirroring the sibling enumerators. fail@HEAD (10/80 pegRNAs carry an N in the RTT) → pass (0). The recurring wet-lab-relevant-defect-under-a-green-suite class, in the flagship. |
| `fix(types)` base-edit window position validation | base-editor-design | `BaseEditWindow._check_window` validated the `window` bounds but not `target_positions`/`bystander_positions`, so an out-of-range position was admitted at construction; the outcome predictor's `spacer[position - 2]` then raised an opaque `IndexError` (motif editors) or silently returned a garbage-but-finite score (non-motif editors). Unreachable via the enumerate pipeline, reachable via a hand-built/deserialized window. **Shipped:** reject any position outside `1..len(spacer)`. The R17 type-contract-completeness class (a model admitting a value its consumers can't handle). |
| `fix(scoring)` PRIDICT2 non-finite score | uncertainty-contract | `PridictEngineAdapter._efficiency` clamped with `min(1.0, max(0.0, score/100))`, so a `NaN` cell in the PRIDICT2 output CSV became a confident "won't edit" `0.0` (`max(0.0, nan) == 0.0`), indistinguishable from a real low score, and `inf` a perfect `1.0`. **Shipped:** raise on a non-finite score; finite out-of-range values still clamp. Extends the finiteness theme (R12/R16/R17/R24) onto the trained PRIDICT2 path. |
| `fix(variant)` reversed-range HGVS | variant-resolution | `parse_genomic_hgvs` had no `end >= start` guard, so a reversed range (`g.5_3delinsAC`, `g.2_0del`) made `ref_lookup` read a backwards empty slice — the deleted/duplicated bases vanished and a `delins` collapsed into a pure insertion, a phantom variant accepted with no error (masked precisely when a real reference is supplied). **Shipped:** raise on `end < start`, allowing `end == start`. The R18/R27/R33 malformed-variant-input fail-closed class. |

**Clean bills:** the enumeration lens verified (~3,900 metamorphic examples) that every cas9/base-editor
protospacer+PAM+cut-site fetches back exactly on its reported strand with carried-allele overlay, base-edit
target/bystander bases and transition class match the editor chemistry, prime PBS/RTT/spacer reconstruct the
intended edit, PE3/PE3b nicking matches its predicate, the HDR donor genuinely blocks re-cut, and routing never
advertises a chemistry the enumerator can't produce — all clean but the RTT N-gap. The scoring lens verified
(~2,600 examples, 4 PYTHONHASHSEED values) every efficiency/probability and interval bound finite and in `[0,1]`,
outcome distributions normalized and non-negative, determinism (content-keyed sorts, no hash-order dependence),
documented monotonicity (scaffold, epegRNA), and OOD-honesty (no engine self-declares `calibrated=True`) — clean
but the two robustness gaps above. The effect/HGVS lens verified substitution/deletion/insertion/dup/delins
coordinate round-trips, severity/impact monotonicity (exhaustive 19×19), and VEP most-severe selection — clean
but the reversed-range gap.

Yield ...1/0/1/4. **Lesson: R33 proved the *modality* is the productive axis; R34 confirms it by exhausting the
same modality across the surfaces R33's four agents didn't reach — and it paid out four more, including a
CONFIRMED correctness bug in the most safety-critical vertical (an unsynthesizable pegRNA templating an ambiguous
base into the genome). Three of the four are the same fail-open-on-out-of-contract-input class the repo has
closed a dozen times (finiteness, malformed HGVS, an admitted-but-unhandleable type value) — when a new lens
opens a surface, the FIRST things it finds are the old classes that example-based tests never generated. Next
modality (per R33's note): metamorphic/differential testing against a reference implementation (bcftools norm,
a real HGVS library) — the enumeration lens already showed metamorphic fetch-back is the sharpest check here.**

## Round 35 — the third modality: differential/metamorphic testing vs an independent oracle (0 fixes; clean bill + a new permanent property test)

Ran the next modality R34's note flagged: differential testing against an independent oracle. No external
reference tools (`bcftools`, a real `hgvs` library) are installed, so the oracle is a naive-but-obviously-correct
in-test implementation. The highest-value target not yet covered this way is variant normalization/left-alignment,
whose core correctness property — *resolving a variant must never change the edit the caller asked for* — is the
single most safety-critical invariant of the whole pipeline (a changed edit is a wrong reagent).

- **Edit-preservation differential (CLEAN):** an independent splice-in oracle (`genome[:pos] + alt +
  genome[pos+len(ref):]`) computed the edited genome implied by each resolved (normalized, left-aligned) variant
  and compared it to the edit implied by the caller's original assertion. Over **4,136** fuzzed valid variants
  (SNV/MNV/ins/del/delins across six repeat- and homopolymer-rich references), **0 mismatches** — normalization
  provably preserves the edit. This is strictly stronger than the R33 idempotence check and would have caught the
  R18 delins-corruption and R33 wrong-build-laundering defects. **Promoted to a permanent property test**
  (`tests/variant/test_normalization_property.py`), the pipeline's first differential guard on this invariant.
- **Left-alignment leftmost-canonical (oracle discarded, code confirmed correct):** an attempted "resolved indel
  is the leftmost equivalent representation" oracle flagged 2,454/3,166 cases — but every one was the *oracle*
  being wrong, not the code: it conflated "same edited genome" with "same indel identity," admitting
  representations that change the indel's bases (e.g. it claimed a `T` insertion in a poly-A run could roll to
  position 0, which would insert a different base). Spot-checked: the resolved forms are correctly left-aligned by
  the VCF/bcftools definition (roll only through exact repeats of the indel unit). No finding — recorded honestly
  rather than shipped as a false positive. The existing suite (`test_deletion_left_aligns_to_repeat_start` et al.)
  plus R18/R33 already pin left-alignment canonicalization.

Yield ...0/1/4/0. **Lesson: the third independent modality (differential vs an oracle) on the most safety-critical
transform returns clean — after R33 (property fuzzing) + R34 (property fuzzing of the remaining surfaces) closed
five real defects, the variant pipeline's edit-preserving core is now validated by three orthogonal techniques
(example-based, property-based invariant, differential-oracle) and holds. That convergence across *modalities* —
not just decompositions — is a credible done-marker for the reachable surface, the same signal R31 reached within
the example-based modality. Equally important: a differential oracle is only as trustworthy as its own
correctness — the discarded leftmost oracle is the reminder that a failing differential test must first be checked
against the code's actual (correct) contract before it's called a bug. A future session's genuinely-new leverage
is an *external* oracle (install bcftools / a real HGVS library and cross-check) or new feature code — not another
in-house oracle over the same converged transforms.**

## Round 36 — the external gold-standard differential: AlleleForge left-alignment vs `bcftools norm` (clean bill)

Took R35's own recommendation immediately: install a real external oracle. `pysam 0.24.0` (which bundles
`bcftools`) installs cleanly in the venv, so this round cross-checks AlleleForge's indel normalization against
`bcftools norm` — the field-standard reference implementation the whole community trusts — rather than an
in-house oracle. (`hgvs` was tried first but needs a Postgres/UTA database; `pysam` is the viable one.)

- **5,000 fuzzed pure indels** (insertions and deletions of 1–4 bp, in four repeat/homopolymer/tandem-rich
  references) were each written as an anchored VCF record, normalized by `bcftools norm -f`, and compared to
  AlleleForge's `resolve()`:
  - **Edited-genome parity: 0 mismatches / 5,000.** The definitive check — splice each side's normalized
    variant back into the reference — is byte-identical for every case, boundary included. AlleleForge and
    bcftools apply the same edit.
  - **Left-alignment position parity: 0 mismatches / 4,710 non-boundary cases.** Where the comparison is
    representation-independent (the indel does not roll to the contig's first base), AlleleForge left-aligns to
    the *exact same coordinate and alleles* as bcftools.
  - **290 contig-start-boundary cases** diverge only in representation: VCF mandates a left anchor base, so
    bcftools anchors a start-of-contig indel on position 1 and deletes/inserts to its right, while AlleleForge
    uses its internal anchorless form (`pos=0, ref="T", alt=""`). Both yield the identical edited genome (counted
    in the 0/5,000 above); the difference is a VCF-format convention, not a normalization disagreement, and the
    locus (a variant at the very first base of a chromosome) is not one any real design targets.

The in-house edit-preservation property test added in R35 remains the permanent, dependency-free CI guard; this
bcftools cross-check is a one-time external validation (adding a `pysam`-gated test would pull a heavy native
dependency into a suite the project deliberately keeps dependency-free — see `variant/vcf.py`'s injectable-reader
design).

Yield ...1/4/0/0. **Lesson: the FOURTH modality — and the first *external* one — agrees with the field-standard
tool exactly. The variant pipeline's normalization/left-alignment is now validated by example-based tests,
property-based invariants, an in-house differential oracle, AND `bcftools norm` itself, all clean or fixed. When
the strongest available external oracle reproduces your output bit-for-bit across thousands of adversarial repeat
contexts, that is the most credible done-marker a re-audit can produce for a transform. The remaining genuinely-new
leverage is now unambiguously *new feature code* (or a new external oracle for a different transform — e.g. a CFD
reference set, though R24 already cross-checked CFD to 5.55e-17), not another pass over this one. Session R33–36:
5 fixes + 6 clean bills (2 of them external/differential) + 1 permanent property test, all pushed.**

## Round 37 — external differential of the VCF ingestion path vs pysam's real parser (clean bill)

The complement to R36: R36 externally validated *normalization*; this validates *ingestion*. `iter_vcf` (the
multiallelic-split + PASS-filter + concrete-allele adapter) has only ever been tested with a **fake cyvcf2-shaped
reader** — the repo avoids the native VCF dependency in CI on purpose (`variant/vcf.py`'s injectable-reader
design). With `pysam` now available, its **real VCF parser** is the external oracle: 600 fuzzed multi-record VCFs
(**2,127 rows** — multiallelic `G,T`, symbolic `<DEL>`, spanning `*`, `N`-bearing and mixed `AT,*,G` alleles,
`PASS`/`.`/`q10` filters) were parsed by `pysam.VariantFile`, adapted to the cyvcf2 shape, and run through
`iter_vcf`; its output was compared to an independent expansion of `iter_vcf`'s documented rules over the same
pysam records. **0 mismatches.** `iter_vcf`'s split/filter/skip logic behaves identically on a real parser's
tokenization as on the fake reader — the same symbolic/spanning alleles are skipped, the same multiallelic rows
split, the same soft-filtered rows dropped. No test added (same dependency-free-suite rationale as R36); the
existing fake-reader unit tests remain the permanent guard, this is a one-time external cross-check.

Yield ...0/0/0. **Lesson: with R36 (normalization vs bcftools) and R37 (ingestion vs pysam), the *entire variant
input pipeline* — VCF row → concrete allele → resolved, normalized, left-aligned variant — is now validated
end-to-end against the two field-standard external tools, both clean. Four modalities (example-based,
property-based, in-house differential, external differential) converge across the whole input surface. This is the
honest terminus for the current codebase: the audit-as-method needs new *code* to bite on, not another lens.
Session R33–37: 5 fixes + 7 clean bills (3 external/differential) + 1 permanent property test, all pushed to main.**

## Round 38 — the audit's own conclusion, taken: new feature code (`enumerate-variable-rtt`)

R37 closed the audit-as-method with an explicit verdict — four modalities converge, two of
them external gold standards, and *"the audit-as-method needs new **code** to bite on, not
another lens."* This round takes that at its word and builds the largest self-flagged gap in
the codebase.

**The gap.** Prime editing's whole claim is that it writes an *arbitrary* small edit.
`enumerate_prime` returned `[]` for anything but a single-base substitution, and R7's
`align-prime-coverage` had (correctly) taught routing to decline the rest rather than
under-deliver silently — an honest guardrail in front of a real hole. Most of the monogenic
disease prime editing exists for is an indel; the CFTR ΔF508 3 bp deletion is the textbook
case, and AlleleForge could not design a pegRNA for a single one of them.

**Shipped.** A **variable-length RT template** — 5' homology + the whole desired allele +
3' homology — so substitution, MNV, insertion, deletion, and delins all enumerate through
one path. A deleted span consumes no template length (a 44 bp deletion is as cheap to write
as a 1 bp one); a written one costs a base each. Three consequences had to be got right, and
each is where the interesting bugs would have lived:

| Surface | What the SNV-only path could assume | What variable-length forced |
|---|---|---|
| RTT length | `distance + 1 + homology` | `distance + len(desired) + homology`, with a second budget — `PRIME_MAX_TEMPLATED_EDIT` (29 = `RTT_RANGE` ceiling − minimum 3' homology) — mirrored in routing so it never advertises an allele no RT template can carry |
| Placement | the start genome *is* the reference, so coordinates coincide | a `_Frame` mapping every span to the **reference footprint its bases derive from** (wider across a deletion, narrower across an insertion), and *no placement at all* for a protospacer lying wholly inside carried bases the reference does not contain |
| PE3b | one base differs at `edit_local` | a **seed-window** comparison, confined to the prefix the start and edited genomes share — past a length-changing edit the two strings shift apart and the old single-index test reads misaligned windows |

**Verification (the R33–R37 discipline, applied to new code rather than old).** The permanent
guard is metamorphic, not example-based: `tests/enumerate/test_prime_variable_rtt.py` fetches
every emitted pegRNA back and proves, with an oracle that shares no arithmetic with the
enumerator, that (1) the reverse-transcribed product is a *unique* locus of the edited
genome, (2) its PBS half anneals at that same locus in the *start* genome, (3) the
protospacer reads off the start genome ending 3 nt past the nick behind a real NGG PAM, and
(4) the template spans the edit with the minimum 3' homology — over six edit classes × two
intents × both strands, plus the fail-closed edges (no-op, over-span, un-templatable) and
the placement-footprint contract. 24 tests, and the three tests that pinned the old
limitation were replaced by tests of the new one.

Gate: `ruff` + `mypy --strict` + 1,231 tests (97% coverage) + `mkdocs --strict` + `reproduce`
all green; the canonical golden digest is unchanged (it is an SNV run, and the SNV path is
byte-identical).

**Lesson: R37's terminus was real, and the right response to it was to stop auditing and
start building. The gap worth building was not a new idea — it was the one the code had been
honestly *documenting* for thirty rounds (`routing.py`: "widen it when the variable-length
RTT path lands"). A codebase that annotates its own limitations in the predicate that
enforces them hands the next session its backlog for free; the discipline that produced
those annotations (never advertise what you cannot produce) is what made this change a
contained, verifiable one rather than an archaeology project.**

## Round 39 — the first thing the new code broke was the old assumption downstream of it (1 fix)

The immediate follow-up to R38, and a direct instance of the repo's most-repeated lesson: *when a new
surface opens, the first thing it exposes is an old class the example-based tests never generated.*

- **`fix(scoring)` nick-to-edit inflated by the templated allele.** `_nick_to_edit`
  (`prime_efficiency.py`) derived the distance as `len(rtt) - rtt_homology_3prime - 1`. That trailing `- 1`
  *is* the templated allele's length, and it was correct for exactly as long as the enumerator could only
  write one base. R38 made it wrong for every insertion, deletion, MNV, and delins the day it landed: a
  5 bp insertion reads as 4 nt farther from its nick than it is. The mis-read is constant across one
  variant's candidates, so it is invisible in a within-variant ranking and shows up precisely where it
  matters — the composite score that puts prime on one footing with the other chemistries in a single
  menu, and any cross-variant comparison (cohort, benchmark). **Shipped:** `PegRNA` records
  `rtt_homology_5prime` alongside the 3' arm it already carried (validated so the arms cannot outrun the
  template, with `templated_edit_length` recoverable from the pair); the enumerator sets it, the scorer
  reads it. Fails@HEAD -> passes; the canonical golden is unchanged because for an SNV the recorded arm
  equals the derived one.

**Lesson: shipping a feature is not the end of the feature. A derived quantity is a hidden assumption, and
the assumption's expiry date is the day the thing it derives from becomes variable. The productive move
after landing new code is not to audit the new code — its own tests are freshest — but to grep every
consumer of the invariant the change just relaxed. One hardcoded `- 1`, in a module that was never
touched, was the whole of R38's downstream blast radius.**

## Round 40 — the safety axis under the new geometry (clean bill + a permanent, mutation-checked guard)

R39 found the one wrong *derived* value R38's change left behind. This round asks the harder question about
the same change: did the new coordinate mapping quietly disarm a **safety** mechanism? That is this repo's
single most-repeated defect class — a real safety input gone inert on its consumed axis with a green suite
(R10 on-target-as-off-target, R11 patient off-targets masked, R24 an unattributed hit flooring every
stratum).

The mechanism at risk is **on-target exclusion**. The reference always contains a guide's own protospacer,
so a genome-wide scan nominates it as a perfect 1.0 hit; the *placement* is the only thing that tells the
engine to drop it, matched exactly on `(chrom, start, end, strand)`. R38 changed how prime placements are
computed. A placement drifting by the indel's size would still be a valid interval, still serialize, still
render — and would simply stop matching, pegging every prime guide's worst-case score at 1.0 and capping
its specificity at 0.5, with nothing red anywhere.

- **Clean bill.** Across SNV / deletion-install / deletion-correct / insertion-correct, on both strands,
  every pegRNA whose protospacer does not cross the edit has a perfect reference hit at its placement and
  that hit is excluded — 0 leaks. The spacers that *do* cross a length-changing edit have no perfect
  reference hit to exclude, which is correct: those bases do not exist in the reference.
- **Promoted to a permanent guard**, written so it cannot pass vacuously: it first asserts the unguarded
  scan *does* report the locus (otherwise the case is skipped as edit-spanning), and then requires that
  **both strands** contribute at least one genuinely-excluded locus. That second clause is the load-bearing
  one — a length change shifts coordinates only *downstream* of itself, which is exactly where the
  minus-strand pegRNAs sit.
- **Mutation-checked.** Deleting the drift correction from `_Frame._reference` (`return offset + index`)
  fails the new guard on both length-changing cases plus the footprint test. An earlier draft that sampled
  the first 20 pegRNAs by nick site — all plus-strand, all upstream of the edit — passed the mutant
  happily; the per-strand requirement is what made it bite.

**Lesson: a guard that can go quiet is not a guard. The first draft of this test asserted "the on-target is
not reported," which a broken placement satisfies trivially — the locus stops being reported because it
stops being *found*. Any test whose subject is an exclusion must first prove the thing being excluded was
there. And when the defect being guarded against is directional (a coordinate drift lives only downstream
of the edit), the sample must be stratified along that direction, or the mutation slips through the half
of the population that was never at risk.**

## Round 41 — a runnable proof of the new capability (`examples/04_indel_prime_correction.ipynb`)

R38 shipped variable-length RTT templating, R39 fixed what it broke downstream, R40 proved it had not
disarmed the safety axis. All three are internal. This round closes the loop on the user-facing side: the
README now *claims* the capability and the specs *pin* it, but nothing a reader could run *showed* it.

The new notebook designs the correcting pegRNA for a ΔF508-shaped in-frame 3 bp deletion — the canonical
case for why prime editing exists — and makes the mechanism legible rather than asserted: routing admits
prime and only prime with its rationale printed; the RT template is reverse-complemented and read apart
into *5' homology + restored allele + 3' homology*, with an `assert` that the restored bases are exactly
the reference allele; and the same variant run in the opposite direction (`INSTALL`, which writes the
deletion) shows the RTT collapsing from 17 nt to 14 — the deleted span costing nothing. The locus is a
fixed-seed random contig rather than a planted one, so the PAMs it uses are genuinely there. It executes
under `--nbmake` in CI alongside the other three.

**Lesson: documentation that a reader can execute is a different artifact from documentation that asserts.
The three prior rounds produced a correct feature, a correct scorer, and a mutation-checked safety guard —
none of which a prospective user can see. The cheapest remaining unit of trust after a feature lands is
the smallest runnable thing that makes its mechanism visible, and the discipline that makes it worth
trusting is the same one the tests use: put an `assert` in the demo, and let CI run it.**

## Round 42 — the same assumption, one enumerator over (2 fixes; a spec the code was quietly violating)

R38–R41 taught the prime enumerator to handle a length-changing allele. This round asks the obvious
follow-on: *who else assumed the allele's length never changes?* The cas9 enumerator did — and unlike
prime, it had a written requirement saying it must not.

- **`fix(cas9)` correction-intent guides enumerated on the reference, not the patient.** `cas9-design`
  has always SHALLed that a precise intent enumerate against the carried sequence: "a PAM the alternate
  allele destroys SHALL NOT be emitted; a PAM the alternate allele creates SHALL be found."
  `_overlay_allele` honored it only for equal-length alleles — `if len(allele) != len(ref): return
  sequence` — so a correcting design against a genome carrying an indel was enumerated on the reference.
  It could propose a guide whose PAM the patient's own deletion has removed (a reagent that cannot cut)
  and miss the junction PAM the deletion creates. **Shipped:** the overlay applies at any length, and
  `EditFrame` (promoted out of `enumerate/prime.py` into a shared `enumerate/_frame.py`) maps every
  placement and cut site back to its reference footprint, dropping a guide with no reference locus.
- **`fix(cas9)` `guide_context` frame-shifted by a length-changing overlay.** It fetched a reference
  window by arithmetic on the placement, then applied the overlay — so an indel inside the flank returned
  a shifted context *of the wrong length* to the efficiency model, Rule Set 3's 30-mer included.
  **Shipped:** anchor the window on the guide's own protospacer+PAM by content (exact under any drift),
  and raise when the guide is absent from the sequence being scored rather than scoring something else.

Both fixes are pinned by three tests built on AT-only contigs — the only PAMs in play are the ones each
test plants — and all three fail under the restored `len(allele) != len(ref)` guard.

**Lesson: the most valuable thing an audit can find is not a missing requirement but a written one the
code stopped honoring at a boundary nobody re-checked. The `!= len(ref)` early-return was not an
oversight; it was a *documented* choice ("the prime/base enumerators bail entirely"), correct on the day
it was written and quietly false from the moment R38 landed — the comment justifying it was still there,
still cited, still wrong. When a capability is widened in one module, its own docstrings are not the
blast radius: every *other* module's justification for opting out is.**

## Round 43 — what the model cannot see, said out loud (1 honesty gap; 1 stale docstring)

R42's sweep for stale opt-out justifications turned up one more docstring
(`design_prime`'s "resolved: The resolved variant (single-position edit)") and, behind it, a subtler
question: the enumerator can now write a 29 nt insertion — *can the scorer tell?*

It cannot. The default `PridictScorer` is a geometry prior whose own model card enumerates its features:
PBS/RTT length, nick-to-edit distance, PBS GC, the epegRNA motif. There is no edit-size or edit-class
term. Two pegRNAs with identical geometry score identically whether they install one base or
twenty-nine. That was invisible while only SNVs were reachable and became a live honesty gap the moment
R38 landed — a number that looks like an efficiency prediction for *this* edit but is really an
efficiency prediction for this *geometry*.

The tempting fix is a size penalty. That would be fabrication: the heuristic was never fitted on anything,
so any coefficient would be invented and would then be laundered through a `Prediction` that already
reports `calibrated=False`. **Shipped instead:** state the blindness in the three places a user reads —
an explicit note on the prediction whenever it scores a non-single-base edit, a `known_failure_modes`
entry on the card (pointing at the trained `pridict2` for size-aware numbers), and a
`templated-edit:<n>nt` flag on the candidate so a menu shows what each design writes. Also fixed the
stale `design_prime` docstring.

The reproducibility golden moved — and only because of the model-card line. Diffing the canonical run's
body before and after confirmed the numbers are byte-identical; the digest catching a *card* edit is the
provenance machinery doing precisely its job, so the golden was regenerated rather than worked around.

**Lesson: when a feature widens the input space, the honest question is not only "does the code handle
it" but "does the model *know* about it." A heuristic with no feature for the thing that just became
variable is not wrong — it is silent, which is worse, because its output is shaped exactly like an
answer. The repo's own line ("no scorer returns a bare float") extends here: a prediction should carry
what it did not look at. And the fix for an un-modeled axis is documentation plus a flag, never an
invented coefficient — a fabricated number inside a calibrated-looking interval is the one failure mode
this project cannot afford.**

## Round 44 — the page a bench scientist actually reads (1 fix)

R43 made the *prediction* honest about the edit size. This round asks the same question one layer out:
does the artifact a human reads say what the reagent does?

It did not. The report's one-line reagent summary was `pegRNA spacer …; PBS 13 nt / RTT 12 nt;
tevopreQ1 motif; PE3` — five fields, every one a dimension. A pegRNA correcting a ΔF508-style 3 bp
deletion and one installing a point substitution differ in none of them, and the line is the string that
leads the HTML card and every export. **Shipped:** the reagent summary states the templated length
(`RTT 12 nt writing 4 nt`) and the design rationale does the same (`4 nt written, +5 homology`). The
`templated-edit:<n>nt` flag from R43 already reaches the HTML through the generic flag rendering, so the
gap was exactly this line. The reproducibility golden is unchanged — verified by diffing the canonical
run's canonicalized body before and after, which is byte-identical (its top candidate is an ABE and its
prime rule enumerates nothing at that locus).

**Lesson: three rounds of internal correctness do not reach the reader. A value that is right in the
type, right in the prediction's notes, and right in the candidate's flags can still be absent from the
one sentence that gets printed — and the reagent line is the highest-leverage string in the product,
because it is the one someone orders oligos from. Trace a new capability all the way to the last
rendered character, not to the last correct field.**

## Round 45 — the outermost guard, and one honest non-finding

R38–R44 fixed seven layers. Each has its own unit test; none of them owns the *seam*. This round adds the
end-to-end guard and probes the surfaces the new input class reaches but no round had exercised.

- **Acceptance test, variant to rendered page.** A ΔF508-shaped 3 bp deletion runs through `design()` →
  ranking → `build_report` → `render_html`, asserting prime is the only chemistry that delivers, the top
  candidate writes 4 nt and flags it, the efficiency prediction admits its edit-size blindness, and both
  the reagent line and the flag survive into the HTML. Every one of those layers assumed a single-base
  edit before R38; this is the first test that would notice if any single one of them regressed.
- **Probed and clean:** the cohort path (`design_many`), pegRNA cloning-oligo generation, and the HTML
  renderer all carry an indel design without incident.
- **An honest non-finding.** The first probe locus returned a menu with **zero** candidates, which looked
  exactly like the bug this round was hunting. It was not: a direct scan of the locus found the nearest
  `NGG` at position 306 — 3' of the edit, so its nick is unusable — and no `CCN` within 50 nt either side.
  A genuine PAM desert, and the menu said so precisely ("prime: eligible but no actionable candidate
  enumerated"), which is the spec's required behavior rather than a silent empty. Recorded as a non-finding
  rather than chased, and the permanent test uses a locus verified to have reachable PAMs.

**Lesson: an empty result is the most expensive thing to misread in either direction. Assuming it is a bug
burns a round; assuming it is benign ships one. The cheap discriminator is to reproduce the constraint by
hand — thirty lines that scan the locus for the PAM the enumerator needs — before touching the enumerator.
The same scan also produced the locus the permanent test now uses, so the diagnostic was not wasted work:
verify the fixture, not just the code.**

## Round 46 — the hottest function in the safety engine was quadratic (1 optimization; 1 retracted claim)

R45's duration report showed one test at 142s, nearly half the suite. Chasing it led somewhere better than
a slow test.

- **`perf(offtarget)` the innermost alignment was `O(n²)` with `n` string allocations per call.**
  `_best_with_removed_base` prices every single-base-removal alignment of a bulged window and runs *twice for
  every PAM-positive anchor in the search space*. It rebuilt the reduced string and fully re-compared it once
  per removal. A profile put **85% of a 150 kb scan inside it** (31.7M generator iterations, 1.6M string
  allocations). Removing base `r` leaves the first `r` comparisons untouched and shifts every later one by
  one, so the count splits into a prefix and a suffix sum — two linear passes, and the reduced string built
  once for the winner. **Measured with the query held fixed, three repeats, two independent workloads:
  4.6x and 4.2x on the full scan, output identical.** The whole test suite went from 299s to **59s**.
  Equivalence is pinned by a differential test whose oracle is the naive implementation kept verbatim,
  including the tie rule (earliest removal position wins) — that position determines the *reported
  alignment*, not just the score.
- **A claim written and then retracted.** Mid-round the FM-index anchor enumeration measured consistently
  slower than the linear scan (8.4s vs 4.2s at 300 kb), and a structural argument for why — a dense `NGG`
  occurs every ~8 bp, so a `locate()` per occurrence cannot beat a linear step — was already written into the
  benchmark script as fact. The very next run, at 1 Mb, came out **2.44x the other way**. The ratio depends
  on how many in-budget hits the particular query has, not on contig length, and nothing measured supports a
  general statement. The script now records the comparison as a measurement to track and says explicitly not
  to quote a speedup from one run. No conclusion shipped.

**Lesson: two opposite failures of measurement discipline in one round, and the second is the one worth
remembering. Finding the quadratic function was easy — a profiler pointed straight at it. The trap was the
*second* finding, where a plausible mechanism ("a locate cannot beat a linear step for a dense PAM") arrived
already dressed as an explanation for the numbers, and the explanation is what made it feel established. It
survived exactly one more data point. A performance claim needs the query held fixed, repeats, and more than
one workload before it is written down — and when a mechanism explains a result that then fails to replicate,
the mechanism was rationalization, however sound it sounds.**

## Round 47 — two more exact prunes, and the noise trap R46 warned about, caught

R46's profile left 1.44s on a 200 kb scan. Re-profiling the *optimized* code showed the remaining time had
moved: the bulge alignment was still 38%, and `PAM.matches` — invisible before — was now 28%, called ~400,000
times per 200 kb contig.

- **`perf(offtarget)` bail out of each alignment pass at the budget.** The prefix and suffix mismatch counts
  are each monotone in their own direction, so once either exceeds `max_mm` no further removal position on
  that side can qualify; if the two feasible ranges do not overlap, the answer is `None` with no more work.
  A random 20-mer at the default budget is now decided in ~a dozen comparisons instead of forty.
- **`perf(offtarget)` memoize the per-window PAM test within a scan.** Windows come from the sanitized
  `ACGTN` alphabet, so the distinct ones are few (`5**pam_len`) while the anchors are many. Each distinct
  window is decided once instead of re-walking IUPAC codes with a `str.upper()` per anchor.

**The trap, and it caught me.** The first measurement of the finished round read **3.88s** — worse than the
0.72s R46 had recorded for the *previous* code on the same benchmark. Taken at face value that is a serious
regression, and the tempting move is to go hunt it. Instead, A/B: same process conditions, alternating
implementations, two interleaved passes. Result: original ≈6s, R46 ≈1.2s, R47 ≈0.3-0.5s. The 3.88s was
machine drift — this box varies by a factor of two between runs — and R46's own recorded 0.72s is equally
un-comparable across sessions. Nothing was wrong.

A third correction, made after the round was already pushed: the changelog claimed the committed
differential test runs 400,000 inputs. It ran 4,000 — the 400,000 was a one-off development sweep, and the
two got conflated in the write-up. The committed test now runs 25,000 (still under a second) and the
wording distinguishes the two.

**Lesson: R46 ended by warning that a performance number needs the query fixed, repeats, and more than one
workload. R47 shows the same rule has a second half: a number is only comparable to another number measured
*in the same conditions*. A prior session's recorded timing is not a baseline — it is a different
experiment. The cheap discipline is to never compare across runs at all: keep both implementations
available, alternate them in one session, and quote only the ratio. That habit turns a would-be
regression-hunt into a thirty-second answer, and it is the only way the cumulative ">10x" here is
defensible.**

## Round 48 — the optimization invalidated a benchmark two modules away (1 corrected claim)

A question R47 raised and did not answer: `MIN_SELECTIVE_K = 5` is a threshold *calibrated against the cost
structure R46 and R47 just rewrote. Is it still right?*

It is still a reasonable threshold; the number attached to it is not. The constant's docstring said "k>=5
gives a ~2-4x speedup," and the README's R2 note repeated "measured **~2–4x** there." Re-measured across six
mismatch/bulge configurations with five repeats each: **0.94–1.12x — neutral within noise, hit sets
identical in every configuration.** Nothing about the prefilter changed. What changed is that the work it
prunes got ~50x cheaper, so its own `O(n)` cost — seed positions plus the covered-index prefix sum — now
cancels the saving. The kernel's *own* lookup is still ~5-7x native-over-Python; that is a different
measurement and it survives.

**Shipped:** both claims corrected, in the constant's docstring and in the README's R2 note, each stating
what was measured, when it changed, and why. The prefilter and the threshold stay: seeding at `k>=5` is
exact and costs nothing measurable, and the route to making it pay again is the prefix-sum construction, not
the constant. Removing an R2 deliverable on the strength of one synthetic 200 kb benchmark would be the
wrong trade, and saying so is part of the finding.

**Lesson: a performance number is not a fact about a function, it is a fact about a *system at a moment*,
and it decays silently when anything else in the system improves. Nothing failed here — no test, no gate, no
review would have caught it, because a stale speedup claim is still a green build. The only thing that
catches it is asking, after every optimization, which previously-measured numbers the change just
invalidated. Two modules away, in a constant nobody edited, was a README-facing figure that a user could
plan capacity around.**

## Round 49 — a report you can actually open (1 product fix)

Noticed while probing the indel path end to end in R45: `design()` on one variant produced **720
candidates** and `render_html` turned them into a **2.3 MB** "self-contained" page. Not a bug — every PBS x
RTT-homology x PAM combination genuinely is a distinct pegRNA, and the library returning all of them is
right. But the *report* is the human artifact, and a 2.3 MB page of near-identical entries is not one.

**Shipped:** `render_html(report, max_candidates=50)`, taking the same report from 2.3 MB to **181 KB**.
Capping is a presentation decision that carries two obligations, and both are tested:
- **Say so.** The page states how many candidates exist, how many are shown, and that the remainder are in
  the lossless JSON/CSV export — which the cap does not touch.
- **Never cap away the Pareto front.** Every front member renders whatever its rank. This is the part worth
  getting right: the front is the report's entire answer to *"I weight the objectives differently from your
  defaults."* A candidate that is optimal on safety but 200th on the composite score is precisely what such
  a reader opened the report for, and a naive `candidates[:50]` would silently delete it. The test
  constructs a 300-candidate report with front members at ranks 200 and 297 and asserts both survive.

**Follow-through (same round):** the PDF render had the identical problem — 1.1 MB for the same report — so
the selection was factored into one shared helper (`report.builder.visible_candidates`) that both renders
call, rather than implemented twice. A guarantee stated in two places is a guarantee that will eventually
hold in only one. PDF: 1.1 MB → **74 KB**.

**Lesson: a truncation is a claim about what does not matter, and it is wrong exactly where the product's
value is concentrated. The naive cap here would have been correct for 718 of 720 candidates and would have
destroyed the two the whole Pareto-front feature exists to surface. When adding any "show the top N", ask
what the tail is *for* — if some other feature's promise lives there, the cap must be defined in terms of
that promise, not in terms of N.**

## Round 50 — the cap that only the library could lift

*Entry reconstructed in R146 from commit `d0a0510`; the original was never written, and later rounds cite
this number (see "the render cap added in R49/R50 was library-only"). Content is from the commit message,
not from recall.*

R49's Pareto-aware render cap was library-only: `render_html` and `render_pdf` took `max_candidates` and
neither the CLI nor the web API exposed it — so a user who wanted the full 720-candidate page had no way to
ask for it, only the JSON/TSV exports, which are a different artifact.

`aforge design --render-candidates N` and the API's `render_candidates` field now set it, with `0` spelling
"draw them all" (a command line has no natural way to write `None`, and a zero-candidate render is not
something anyone wants). Tests on both surfaces pin that the cap changes the rendered page and never the
lossless export — the property a display cap must not violate.

Both shells in one change, deliberately: the off-target labeling fix reached the CLI five rounds before the
web API and was only found still-wrong there by driving it. The two are thin shells over one library, so a
gap in how one exposes a capability almost always exists in the other.

## Round 51 — driving the actual CLI found the hole (2 fixes; 1 gap declared, not hidden)

Ran the real `aforge design` on the ΔF508-shaped deletion — the whole session's work visible end to end
(`templated-edit:4nt`, "writing 4 nt", 720 rows of lossless TSV). Then asked the next question: what
happens to a precise edit *larger* than prime can template?

**Nothing happens.** Correcting a 40 bp deletion routes to no chemistry at all — the edit exceeds prime's
RT template budget, base editors cannot make an indel, and the nuclease is knock-out only. The user gets an
empty menu whose entire explanation is `prime=no, cas9_nuclease=no`.

- **`fix(design)` the outcome predictor got the right sequence with the break in the wrong place.**
  `_cut_outcome` skipped its carried-allele overlay for a length-changing allele — the *same*
  `len(allele) == len(ref)` restriction R42 removed one function over, sitting in a second place nobody
  looked. Removing it exposed the real half of the bug: a length change shifts everything 3' of itself,
  **the cut site included**, so overlaying the sequence while leaving the cut index alone hands the
  predictor a plausible indel spectrum computed for a different locus. Fixed both halves; pinned by a
  recording predictor that captures exactly what it was asked to score.
- **`fix(design)` an empty menu now says why.** It states that no chemistry can make the edit and gives
  each rule's own reason — those rationales already existed, they were just never surfaced when they
  mattered most.
- **The gap is declared, not quietly left.** Nuclease-plus-HDR *is* the right tool for this edit, and the
  pieces exist: `hdr_donor` handles any-length alleles, and R42 made `enumerate_cas9` correct against an
  indel-carrying genome. What is missing is the vertical — `design_cas9` never attaches a donor, and
  `DesignCandidate` has no field for one, so routing cas9 for a precise intent today would advertise a bare
  double-strand break as a "correction", which is a knockout. Rather than half-build it, the nuclease
  rationale now names the route and says plainly that the designer does not yet offer it. **That is the
  next feature.**

**Lesson: the fastest way to find the hole was to stop reading the code and run the product. Two rounds of
targeted auditing over these same modules found nothing here, because the defect is not in any function —
it is the absence of a path, and absence has no line number. Driving one realistic input to the end
surfaced it in a minute. Second: `len(allele) == len(ref)` appeared in two places, and R42 fixed one. A
sweep for the *pattern* rather than the *symptom* would have caught both; grep for the condition you just
deleted, not the function you just fixed.**

## Round 52 — half a reagent, and ten schemas nobody was watching (1 feature step; 1 silent drift)

R51 declared the gap: nuclease-plus-HDR is the right tool for a precise edit beyond prime's RT template
budget, but `design_cas9` never attached a donor, so routing it would advertise a bare double-strand break
as a correction. This round builds the foundation — the candidate must be a complete reagent before any
rule may offer it.

- **`feat(design)` a precise nuclease candidate carries its repair template.** `DesignCandidate` gains
  `hdr_donor`; the vertical attaches what `hdr_donor()` builds (PAM-blocking silent mutation included),
  flags its re-cut disposition (`hdr-donor:recut-blocked` / `:recut-not-blocked` / `:none`), and flags
  `outcome-is-nhej-spectrum` so the attached distribution is not misread as the correction — NHEJ, not HDR,
  is the majority repair outcome at a break. The reagent line names the pair. Knock-out candidates are
  untouched: they want the break itself. **Routing deliberately still does not offer it** — that is the
  next step, and the rule's rationale says so.
- **A caught precedence bug, mine.** The rationale was first written as
  `f"..." + (... if donor else ...) if precise else ""`, which Python parses as `(A + B) if C else D` — so
  every *knock-out* rationale silently became the empty string. An existing test caught it immediately.
  Rewritten as a named helper; a conditional that convoluted was the wrong shape regardless.
- **`fix(docs)` ten published JSON Schemas had drifted, and nothing was watching.** Adding a field to
  `DesignCandidate` moved the reproducibility golden, which prompted regenerating `docs/schemas/` — and
  **ten** files changed, most of them for reasons predating this session. `Variant`, the core input type,
  had been missing `source_assembly` for several releases: a consumer validating against the *published*
  schema would have **rejected a document the library emits**. The exporter's docstring claimed it was
  "wired into the docs build"; nothing referenced it. Regenerated all ten, corrected the claim, and added
  `test_committed_schemas_match_the_code`, which names the stale files and the command that fixes them.
  Mutation-checked by deleting `source_assembly` from the committed file.

**Lesson: the published artifact and the code are two different things, and only one of them has tests. The
schemas drifted for releases behind a docstring asserting they could not — the same shape as R48's stale
speedup, and again invisible to every gate, because a stale generated file is still a green build. Any
generated artifact committed to the repo needs a test that regenerates it and compares; without one, the
comment claiming it stays fresh is the only thing keeping it fresh, and comments do not run. Second, on
scope: the honest move when a feature is half-built is to ship the half that is *complete and correct* (a
candidate that carries its donor) and leave the rule that would expose it switched off, with the reason
written down — not to flip the switch and let the menu advertise a break as a correction.**

## Round 53 — the switch R52 left off (1 feature completed)

R52 built the complete reagent and deliberately left routing untouched. This round flips it, having first
confirmed the vertical actually delivers: the 41-base restoration produces two candidates, each with a
141 nt donor whose re-cut the correction itself blocks.

**Shipped:** `_nuclease_eligible` admits a precise intent when — and only when — no break-free chemistry
can reach the edit. The "only when" is the whole design. HDR is inefficient, S/G2-restricted, and the same
break yields NHEJ indels as its majority product, so routing it as a peer of base and prime editing would
bury every small-edit menu under a strictly worse option. Tested from both sides: the 40 bp deletion now
routes to `[cas9_nuclease]` where it previously routed to nothing, and a transition SNV, a small indel, and
a small insertion all keep the nuclease out.

Two consequences worth naming:
- **This is the one rule that reads the others**, and the docstring says so and why: "last resort" is not a
  property of the variant alone. It remains a pure function of `(resolved, intent)` — it re-evaluates the
  same predicates rather than reaching for shared state.
- **Routing can no longer return nothing**, which made R51's empty-menu explanation unreachable *through
  routing*. It is still reachable when a caller restricts chemistries, so the test was re-pointed at that
  path rather than deleted — the explanation still has a job.

A precise nuclease candidate scores **0 on cleanliness**, because the NHEJ spectrum it carries contains no
intended allele. That is the honest number. Inventing an HDR rate to improve it would be the R43 mistake —
a fabricated coefficient inside a calibrated-looking interval — so the flag `outcome-is-nhej-spectrum`
carries the explanation instead.

**Lesson: splitting "build the reagent" from "offer the reagent" across two rounds was worth it. R52 could
be reviewed on one question (is this candidate complete and honestly labelled?) and R53 on a different one
(when should it be offered?), and the second question turned out to be the harder and more consequential
of the two — the naive answer, route it for every precise intent, is defensible in a sentence and wrong in
practice. A feature flag's off position is a legitimate place to stop for a round.**

## Round 54 — the reagent you cannot order (1 feature; 1 real defect found by a failing test I wrote)

R52-53 made a precise nuclease candidate complete and routed it. It still could not be *ordered*:
`oligos_for` emitted only the sgRNA duplex — the half that cannot make the edit.

- **`feat(report)` the donor is emitted as an orderable template.** A new `DonorOligo`
  (`kind="hdr-donor-ssodn"`) rides on `SgRnaOligos.donor`, with its hazards promoted into the prominent
  warnings list rather than buried in the JSON block: a donor beyond the ~200 nt most vendors synthesize as
  one oligo (order it as a dsDNA fragment instead — a 300 nt "oligo" should not reach a cart unremarked),
  and a repaired product still cuttable by its own guide.
- **`fix(cas9)` a repair template built over an assembly gap.** Found by writing a test I expected to pass.
  `hdr_donor` splices 50 bp homology arms unguarded, so an arm reaching a reference `N` — a gap the guide
  itself never sees — produced an unsynthesizable oligo that, if forced, would template an ambiguous base
  into the genome **permanently**. This is exactly R34's prime-RTT `N`-gap class, in the one reagent where
  the ambiguous base is written in for good. `hdr_donor` now returns `None` there, and `donor_oligo`
  refuses an ambiguous donor at the ordering boundary too.
- **The fix's first version was wrong, and three existing tests said so.** Guarding on "any `N` in the
  donor" also refused every donor near a **contig end**, where the fetch is `N`-padded. Padding is not a
  gap: the reference simply stops. Clamping the right arm to `contig_length` separates the two — a short
  arm near a contig end is the honest reagent, and only a genuine *interior* gap fails closed. The three
  red tests were the signal that the first guard conflated two different absences of sequence.

**Lesson: I wrote the ambiguous-donor test as a formality — a boundary case I assumed was already handled,
to round out a feature. It failed, and the defect behind it is the most consequential kind this codebase
has: a wet-lab reagent that looks valid, passes every existing check, and installs an uncontrolled base
into a genome. The test that finds a bug is often not the one aimed at a suspicion; it is the one written
to confirm something obvious. Second: when a new guard turns tests red, read them before deciding they are
stale. Those three were reporting that "no sequence available" has two causes with opposite correct
responses, and the first version of the guard knew about only one.**

## Round 55 — joining up the HDR thread, and saying so in the README

R51-54 built the nuclease-plus-HDR route one hop at a time, each with its own unit test. Nothing asserted
the hops connect, and the README still drew the donor as a dotted side-branch off the design flow.

- **An acceptance test from variant to orderable reagent.** The 41-base restoration — the edit that
  returned a blank menu three rounds ago — now runs `design()` → ranking → `build_report` →
  `oligos_for` → `render_html`, asserting routing admits only the nuclease, the top candidate carries a
  gap-free donor with its `hdr-donor:*` and `outcome-is-nhej-spectrum` flags, the reagent line names the
  pair, and the donor arrives as an orderable `hdr-donor-ssodn` that reaches the HTML.
- **README updated to the shipped state**: the donor now feeds the candidate in the flow diagram rather
  than dangling off it, with a note spelling out that a precise nuclease candidate is a *pair* — labeled
  at every layer, scoring 0 on cleanliness because the NHEJ spectrum contains no intended allele (the
  honest number, not an invented HDR rate), refused outright when a homology arm would reach an
  assembly-gap `N`, and shortened rather than refused when an arm merely runs past a contig end.

**Lesson: the same pattern as R45, and worth naming as a habit rather than a coincidence. A feature built
across several rounds accumulates unit tests at every hop and no test of the seam, because each round's
scope ends at its own module boundary. The end-to-end test is cheap, it is the only one that would notice
a hop being silently dropped, and the right time to write it is when the last hop lands — while the whole
chain is still in view.**

## Round 56 — the reassuring default (1 safety fix, found by running the tool)

Drove the real `aforge batch` over a three-variant cohort — an SNV, a small deletion, a 41-base deletion —
to check the whole session's work through the cohort path. It routed all three correctly. One column in
the output looked wrong: `worst_offtarget = 0.0` on a run invoked with `--no-offtarget`.

**`fix(cohort)` "we did not look" rendered as the reassuring value.** `_summarize` took
`max(..., default=0.0)` over the candidates carrying an off-target report, so a skipped search produced
**exactly the same number** as a search that ran and found nothing. `best_specificity`, right beside it,
already used `None` correctly — the two fields disagreed about how to say "absent". A cohort manifest is
triaged by scanning that column, so an entire cohort designed with the search off read as *no off-target
risk anywhere*. Now `None` when nothing was measured.

The harm is not hypothetical. In the very cohort used to check this, the first variant's **measured**
worst off-target is `1.0` — a perfect-match hit — and the old code reported `0.0` for that same variant
whenever the search was skipped. The regression test pins both directions: a fix that made every run
report `None` would be equally wrong, and only the pair distinguishes them.

**Lesson: this is the repo's most-repeated defect class (a safety input inert on its consumed axis, green
suite) in its purest form yet — not a wrong computation but a *wrong default for absence*. `default=0.0`
is what `max()` wants to be given; that it is also the safest-looking number on a safety axis is a
coincidence of the domain, and the coincidence is the bug. Rule of thumb: on any axis where one end means
"safe", absence must never be encoded as a value on that axis. And the neighbouring field already had it
right — when two adjacent fields disagree about how to represent "not available", one of them is wrong,
and it is worth stopping to ask which.**

## Round 57 — sweeping for the pattern, not the instance (1 fix; the rest a clean bill)

R56 fixed one numeric default standing in for absence on a safety axis. R51's lesson says to grep for the
*condition* rather than the function, so this round swept every `default=0.0` / `else 0.0` in the library.

**Mostly a clean bill, and instructively so.** The metrics suite defaults to `0.0` all over — and it is
*right* to, deliberately: `spearman`, `pearson`, `roc_auc`, `pr_auc` and `topk_accuracy` are all bounded
below, so `0.0` is their **pessimistic** end and a degenerate input cannot flatter itself. `spearman`'s own
docstring shows the authors reasoning about exactly this ("would otherwise emit finite-but-meaningless
ranks that score as a perfect 1.0"). The ranking layer's `p_intended → 0.0` and the cas9 sort key's
`worst → 0.0` likewise fall to the cautious side.

**One genuine outlier: `kl`.** `LOWER_IS_BETTER = {"kl", "ece"}` — so for KL, `0.0` is not the pessimistic
end, it is the **optimum**. `_distribution_metrics` returned `sum(kls) / n if n else 0.0`, meaning a
distribution task evaluated over **zero examples posts a perfect divergence and ranks first**. The
convention the whole module follows inverts on this one metric, and the code did not notice. KL is also
unbounded above, so unlike its neighbours it has no worst value to fail toward — the only honest answer is
*undefined*. Now `None`, which is what `ece` (computed from the same empty inputs, and the other member of
`LOWER_IS_BETTER`) already returned, and what the runner's `float | None` type and its "primary metric is
undefined for this run" path were already built for. Mutation-checked; the paired test also pins that a
non-empty evaluation still returns a number.

**Lesson: "fail toward the pessimistic value" is a sound convention that silently stops being sound for any
metric whose direction is inverted — and a codebase that ranks on a mix of higher-is-better and
lower-is-better metrics will have exactly one or two such members, sitting in a set that names them. The
sweep worth doing after finding one bad default is not "where else is `0.0`" but "where does `0.0` mean
*good*". `LOWER_IS_BETTER` was a two-element set naming precisely where to look, and one of its two members
was already correct — which, as in R56, is the tell.**

## Round 58 — the same number under two definitions (1 CLI fix, found by running it)

Continued driving CLI surfaces the session had not exercised. `aforge offtarget` on a spacer that exists in
the reference reported **specificity 0.333** — because the guide's own perfect match was counted against it.

The off-target engine's `_is_on_target` docstring warns about exactly this: "counting it would peg every
guide's worst-case score at 1.0 (inert safety axis) and cap specificity at 0.5 for even a perfectly clean
guide. A caller that knows the on-target placement passes it." The CLI was the one caller that never did,
and had no way to.

**The fix is not to guess.** Given only a spacer, the tool genuinely cannot know which perfect match is the
intended locus, so reporting all of them is the correct answer to the question asked. What was wrong is
that the answer was unlabelled: the CLI and a design report both printed a number called "specificity",
computed under different definitions, with nothing to tell them apart. **Shipped:** `--on-target
'chrom:start-end(strand)'` (the exact form the tool already prints) excludes the locus when the caller
knows it; when they do not, the human line carries `[on-target locus NOT excluded; pass --on-target]` and
the JSON carries `on_target_excluded: false`. A malformed locus exits as a usage error rather than silently
searching without the exclusion — a typo must not quietly restore the old behavior.

**Lesson: the bug was not a wrong computation, it was an unlabelled one — two quantities sharing a name
across two surfaces. That class is invisible to tests (both numbers are correct for their own definition)
and invisible to code review of either surface alone; it only shows up when you compute the same thing two
ways and compare, which is what running the tool after reading the library does for free. Where a metric's
definition depends on an optional input, the output should say which definition it used.**

## Round 59 — the flagship's provenance was one model short (2 gaps, one asymmetry each)

Kept driving CLI surfaces. `aforge verify` on a prime design reported **"1 model(s)"**. A prime design
invokes two: an efficiency scorer and a byproduct predictor.

- **`feat(scoring)` the prime byproduct model had no card.** `prime_model_checkpoints()` documented this
  as intentional — "a card-free heuristic, so it contributes no checkpoint" — but the siblings do not work
  that way: `indelphi-mh-baseline` (nuclease) and `be-dict-baseline` (base editing) each carry one. The
  *flagship* was the one chemistry whose outcome model went unrecorded, and it is the model whose
  `p_intended` feeds the ranking's cleanliness objective. A `prime-outcome-baseline` card now records its
  version, citation, and three real failure modes — including that it is keyed on pegRNA geometry alone,
  the same blindness R43 surfaced on the efficiency side.
- **`feat(design)` `design()` could not be given prime overrides at all.** The signature tell: its siblings
  are `cas9_model_checkpoints(scorer, predictor)` and `base_editor_model_checkpoints(predictor)`, while
  `prime_model_checkpoints()` took nothing — correct only because there was nothing to take. A caller
  could substitute a scorer for the nuclease and for base editing, but not for the flagship. `design()`
  now accepts `prime_efficiency_scorer` / `prime_outcome_predictor`, and records the override's card
  rather than the default it replaced — otherwise a re-run from the stamped provenance reproduces
  different numbers. (**Corrected in R60:** this round's first write-up claimed the change made the
  trained PRIDICT2 engine reachable through `design()`. It does not — see R60.)

Golden regenerated for exactly one added model, verified by diffing the canonical run's body; no number
changed.

**Lesson: three parallel implementations of the same idea, and the odd one out is the finding. Two
verticals took overrides and recorded two cards each; the third took none and recorded one — and its
divergence was *documented*, which is what made it look deliberate rather than missing. A comment
explaining why one branch is different is not evidence that it should be; it is often just the place where
someone stopped. When N implementations of a pattern exist and one differs, the useful question is not
"why is this one different" but "would anyone choose this difference today" — here the answer was no, on
the chemistry the project calls its flagship.**

## Round 60 — correcting my own claim from one round ago

R59's own lesson said to look for the odd one out among parallel implementations, so this round checked the
CLI: it has `--trained-efficiency` and `--trained-outcome` (SpCas9) and `--trained-base-outcome` (base
editing), and nothing for the flagship. The obvious completion was a `--trained-prime-efficiency` flag.

**There is nothing to wire it to, and R59's write-up said otherwise.** Reading the adapters before adding
the flag:

- `PridictEngineAdapter` — the real PRIDICT2.0 path — exposes `design(sequence)`, **not**
  `score(pegrna, ...)`. It is a sequence-level engine and does not satisfy `PrimeEfficiencyScorer`.
- `DeepPrimeAdapter` / `GenETAdapter` *do* implement `score(pegrna, ...)` — and raise
  `NotImplementedError` by design, documented placeholders because "DeepPrime's per-pegRNA API needs edit
  metadata a `PegRNA` does not carry".

So no trained per-pegRNA prime scorer exists to pass to `design()`. R59's changelog and commit message
claimed its change made the trained PRIDICT2 engine "reachable ... not through the unified entry point",
implying it was reachable through `design_prime`. It never was — the adapter does not fit that protocol
either. The R59 *change* stands (the asymmetry was real, and provenance is now override-aware); the
justification overstated what it unlocks.

**Shipped:** the claim corrected in the changelog and the round log, the real state written into
`design()`'s and `prime_model_checkpoints()`'s docstrings so the next reader is not misled the same way,
and no CLI flag added — there is nothing valid behind it. A test now pins the gap: it asserts
`PridictEngineAdapter` has no `score` and that the two placeholders still document refusing, so it fails
the moment a genuine trained scorer lands and the "no trained scorer today" docstrings need updating with
it.

**Lesson: the most dangerous inaccuracy in this session was one I wrote myself, one round earlier, while
fixing an inaccuracy. It came from reasoning about an adapter's *role* ("the trained PRIDICT2 engine")
instead of its *signature* — and it read as plausible precisely because the surrounding facts were right.
The check that caught it was mechanical and took a minute: before writing that X can be passed to Y, look
at whether X has Y's method. Also: the right response to "there is no flag for the flagship" was to find
out why, not to add one — the asymmetry was load-bearing, and a flag would have shipped a
`NotImplementedError` to users.**

## Round 61 — refreshing the status file caught a regression I shipped five commits ago

`specs/readiness-assessment.md` is the file a future session reads first for honest state, and it was
stale — 906 tests, 93 files, 3 notebooks, against an actual 1,288 / 95 / 4. Updating it meant re-verifying
every number rather than copying them forward. That is what caught the bug.

- **`fix(examples)` a notebook broken by R56, shipped for five commits.**
  `03_batch_vcf.ipynb` renders its cohort table with `round(s.get("worst_offtarget", 0.0), 3)`. A `.get`
  default does not fire when the key is **present with value `None`** — which is precisely what R56 made
  that field. CI's `examples` job (`pytest --nbmake examples/`) would have caught it on the first push;
  my local gate for R56-R60 had quietly stopped including it after R55. The cell now renders `-`, matching
  how it already renders a missing best chemistry.
- **`docs(specs)` the readiness assessment brought current**: verified gate numbers, the capability added
  this session (variable-length RTT, the nuclease+HDR last resort, the >10x off-target scan), and one row
  corrected — the table listed three axes as "usable via `aforge design --trained-*`" and prime as
  "sequence-level engine", a distinction easy to read past. It now says plainly that a `design()` menu's
  prime efficiency is the heuristic baseline today whatever weights are installed.

**Lesson: the regression was not caused by the change, it was caused by trimming the gate. I ran the
notebooks in R55, then for five rounds ran lint + types + tests + docs + reproduce and considered that
"the full gate" — because those five are fast and the failure they missed was in the one command I had
dropped. A gate is only as good as its least convenient member, and the member most likely to be dropped
is the slow one that catches a different *class* of failure. Second, and more useful: the thing that
actually caught it was refusing to copy numbers forward into a status document. Re-deriving a number you
are about to publish is a cheap, load-bearing habit — the status file was not even where the bug lived.**

## Round 62 — fixing the gate, not just the thing the gate missed

R61 found a notebook that had been broken for five commits and diagnosed the cause honestly: I had trimmed
`pytest --nbmake examples/` out of the gate I was running. Fixing the notebook does nothing about that.

The project had the same bug, in writing. The Makefile's header promises "CI runs the same commands; this
is the local mirror so `make ci` reproduces the gate before a push" — and `ci` ran
`lint type test docs reproduce`, omitting `examples`. The one job that would have caught the regression
was missing from the mirror that claims to be complete, which is very likely why it was missing from mine.

**Shipped:** a `make examples` target, `examples` added to `make ci`, and
`tests/test_gate_mirrors_ci.py`, which reads `.github/workflows/ci.yml` and fails when any blocking job is
absent from the `ci` target. Two jobs are excused by name with their reasons (`security` is advisory in CI
via `|| true`; `rust` needs the compiled crate and `make native` covers it), and a second test fails if an
excuse names a job CI no longer has — a stale exemption is exactly how the next drift would hide.
Mutation-checked in both directions: removing `examples` fails, and adding an unmirrored CI job fails.

**Lesson: when a process failure causes a defect, the defect is the cheap half of the fix. I could have
stopped at "repair the notebook, remember to run nbmake" — a resolution with no mechanism behind it, and
one that would decay exactly as fast as the last one did. The durable version is to make the shortcut
impossible: put the missing step in the documented entry point, then test that the entry point still
matches the thing it claims to mirror. Note also that the guard reads the workflow rather than a
hand-written list of jobs, because a hand-written list is one more copy to drift.**

## Round 63 — the fix I applied to one surface and not the other

Drove the web API for the first time this session. All three variant classes route correctly through it,
including the new nuclease+HDR fallback. `POST /api/offtarget` returned **specificity 0.333** — the exact
defect R58 fixed in the CLI five rounds ago, on the surface I did not touch. Its response docstring even
promises "the same summary the `aforge offtarget` CLI surfaces", a claim R58 had silently falsified.

**Shipped:** `on_target` on the request, `on_target_excluded` on the response, 422 on a malformed locus —
and `GenomicInterval.parse`, the exact inverse of `__str__`, now shared by both surfaces so they cannot
drift into accepting different spellings of a locus.

**A design error caught by running the round trip.** The first version took the locus as the CLI's
`chrom:start-end(strand)` string. Then I tried the actual client flow — read a site out of a response,
hand its locus back — and got a 422: the API serializes `locus` as an *object* and never emits that string
at all. A field accepting only the string form would have required every client to reformat a value the
API had just given them, in a spelling the API itself never produces. It now takes the `GenomicInterval`,
and the test performs that exact round trip rather than constructing a locus by hand.

**Lesson: R59's "the odd one out is the finding" has a companion — after fixing a defect, ask which other
surface has the same shape. The CLI and the web API are both thin shells over one library, which is
precisely why a defect in how a shell *labels* a library result will exist in both, and why fixing one
feels complete. Second: an API's input format should be whatever its own output format is. The string
version passed its unit tests and would have been wrong for every real client, and the only thing that
surfaced it was performing the round trip a client performs instead of asserting on a value I had typed
myself.**

## Round 64 — the last two surfaces, and the prose beside the generated docs (clean bills + a doc refresh)

Finished exercising the surfaces this session had not driven, then swept the API reference for the prose
that auto-generation does not cover.

- **Web `/api/batch` — clean.** R56 made a cohort summary's `worst_offtarget` `None` when nothing was
  measured, which could have been a 500 if the response model typed it as `float`. It is
  `dict[str, object] | None`, and the endpoint returns `null` honestly. Verified by driving it.
- **The browser frontend — clean, and already defensive.** Its cohort table reads
  `typeof s.worst_offtarget === "number" ? …toFixed(3) : "—"`, so it rendered the new `null` correctly with
  no change. The design view embeds the *server-rendered* HTML report in an iframe, so this session's
  reagent line, render cap, donor and flags all reach it for free. Worth noting against R61: the frontend
  was written defensively for a non-numeric value and the notebook was not — the notebook is the artifact
  that broke.
- **`docs(api)` the hand-written tables had gone stale.** The pages use mkdocstrings, so classes and
  functions (`DonorOligo`, `donor_oligo`, `visible_candidates`, `GenomicInterval.parse`) documented
  themselves. The prose beside them did not: the routing table still described prime as "≤ RTT length" and
  the nuclease as knock-out-only, and the cloning table listed three chemistries with no mention that a
  precise nuclease candidate ships with an HDR donor. Both corrected, plus a paragraph on the render cap
  and why the Pareto front is exempt from it.

**Lesson: auto-generated documentation makes the surrounding prose *more* likely to rot, not less. The
docstrings updated themselves as the code changed, which is exactly what makes the hand-written table two
lines above them easy to forget — the page looks maintained. Wherever generated and hand-written content
share a page, the hand-written half is the one to re-read after a behavior change.**

## Round 65 — 100% coverage on a primitive with no direct test, and the bug hiding under it

`EditFrame` — the coordinate primitive the prime *and* cas9 enumerators both depend on since R42 — reported
**100% coverage** and had no direct test. It was reached only through two enumerators, on their specific
loci. That is coverage, not verification, and every coordinate defect this codebase has produced (a
placement off by an indel's length, a cut index that did not move with its allele) is exactly that shape.

Wrote the direct property tests. The first one failed.

**`fix(enumerate)` a span starting at a pure deletion was placed four bases too early.** A span boundary
sitting on the edit is ambiguous and the two directions want opposite answers: with an empty carried allele
— the target genome has a pure deletion — index `edit_plus` is at once "just before the removed reference
bases" and "just after" them. A span *starting* there begins after them; one *ending* there stops before
them. `_reference` served both, so a 6-base span reported a 10-base footprint whose first four bases are
not in the protospacer at all. Split into `_reference_start` / `_reference_end`, which is precisely what
`_alt_coordinate_lift` in the off-target module already does — "``lo`` for a span start, ``hi`` for a span
end" — a solved problem in this repo that the newer primitive collapsed back into one map.

Reachable through an **anchorless** deletion (`alt=""`), which `VariantClass.DELETION` and routing both
admit even though `normalized()` keeps an anchor. **Every existing test still passed** — the enumerators
are exercised on anchored loci, where the two maps agree. Mutation-checked; the new tests also pin
monotonicity, the reverse frame mirroring the plus frame, and the identity frame being a plain offset.

**Lesson: 100% coverage on a shared primitive reached only through its callers is a coverage number, not a
verification. The callers pin the paths *they* take; the primitive's contract is broader than any of them,
and the gap is precisely the inputs no caller happens to produce today — which is also precisely where the
next caller will land. Second, and more pointed: this repo had already solved this exact boundary problem,
in `_alt_coordinate_lift`, with a docstring explaining why two maps are needed. The newer, shared, more
central implementation collapsed them into one. When extracting a primitive, look for whether an older
corner of the codebase already fought this fight.**

## Round 66 — sweeping R65's lesson: which other primitives are tested only through callers?

R65 found a real bug under 100% coverage on a shared primitive with no direct test. That is a repeatable
query, so this round ran it: every private module in the library, checked for whether any test imports it
directly rather than reaching it through a caller.

**Six of seven were already tested directly** (`_kmer`, `_haplotype`, `_io`, `_search`, `_native`, and
`_frame` as of R65). The outlier: **`benchmark/_canon.py`**, imported by exactly one test, for one
function, at 92%.

It is not a minor module. It is the single definition of "how an object becomes bytes" that the generator
minting a frozen split and the loader verifying it must agree on — and every clause of its contract is a
claim about *bytes*, not values, so a silent break does not raise. It makes a frozen split fail to verify,
or lets two different results claim to be the same re-derivation. Now directly tested, at 100%:
key-order independence (the stated invariant), list order still mattering (a split's membership is
ordered), stability **across `PYTHONHASHSEED` in a subprocess** — because dict iteration order is
per-process, and a canonical form that depended on it would verify on the machine that minted the split
and fail everywhere else, intermittently — non-ASCII round-tripping under `ensure_ascii=False`, and the
`reproducibility_digest` rounding reaching floats nested in lists and mappings while still separating a
genuinely different number from a last-ULP one. A final test pins that the two digests are *not*
interchangeable, since conflating them would let a tamper seal pass on a rounded body.

Mutation-checked: dropping `sort_keys` fails the order test; rounding only top-level floats fails the
nesting test. No defect found this time — a clean bill on the primitive, and the gap it closes is that
nothing previously would have *reported* one.

**Lesson: a finding is worth more as a query than as a fix. R65's bug was one instance; "which shared
primitives are reached only through their callers" is a question the whole codebase can be asked in one
command, and asking it took less time than the fix did. The answer being mostly reassuring is not a waste
— it converts an anxiety into a bounded, checked list, and it found the one module where the anxiety was
justified.**

## Round 67 — profiling the design pipeline, and a cache key that did not cover its value

Profiled `design()` with the off-target search on, now that R46–47 made the scan ~10x faster. A 60 kb
reference, 451 candidates, **0.64s** — still ~78% off-target scan, but the remaining cost is per-anchor
alignment evaluation (~80%) rather than anchor enumeration (~15%), so batching the scan across spacers
would buy at most ~15% and further gains need vectorization or the native kernel. Recorded as measured, not
pursued.

The profile did show something else: only **20** strand-scans for 451 candidates, because `design_prime`
caches the merged two-nick report. Reading that cache found the finding.

**`fix(prime)` the cache key named the spacers but not the loci.** The cached value has each spacer's *own
locus* excluded from it, and that exclusion is locus-specific — so two pegRNAs sharing a spacer pair at
different loci would share an entry, and the second would be handed a report that dropped a genuine
paralogous off-target for it. That is the on-target-as-off-target class (R10, R40) inverted: not counting
a guide against itself, but *failing to count* a real site because another candidate's locus was excluded
in its place. The key now names both placements.

**Honest scope, stated in the code and the changelog:** I could not construct a locus that actually
produces the collision — the enumerator's RT-reach window makes a repeated spacer-pair across placements
hard to arrange — so this closes a key/value mismatch rather than a demonstrated miss. The invariant is
pinned by a direct test of the keying function (two pegRNAs identical but for placement must not share a
key), mutation-checked, rather than by a genomic scenario I could not build.

**Lesson: a cache key is a claim that it names everything the value depends on, and that claim is
checkable independently of whether you can trigger its failure. The temptation with an unreachable-looking
bug is to leave it and note it; here the fix is one line, provably correct, and the alternative is a
latent hazard whose trigger is "a repeat region", which is exactly the context this tool's users work in.
Also worth naming: the finding came from reading code the *profiler* pointed at, not code I set out to
audit — 20 scans for 451 candidates was an oddity worth understanding, and the cache was the explanation.**

## Round 68 — the cache-key sweep (clean bill), and codifying a pattern that has now bitten three times

Ran R67's finding as a query across every cache in the library. **All clean:**
- `offtarget/cache.py`'s `search_signature` already includes the on-target locus — and its docstring
  already warns about the exact hazard R67 fixed: two searches "collide on one key and one is served the
  other's report, silently either counting the self-match or hiding a perfect-score site".
- The VEP adapter keys on `(variant, assembly, transcript)`, which is every input `predict` takes.
- `CachedEmbedder.persistent` scopes its disk store to `f"{name}-{version}"`, so two models' embeddings
  cannot collide on a shared sequence hash.
- R47's per-scan `pam_ok` memo is keyed on the window string within one scan, where the PAM is fixed.

**The finding is the pattern, not the sweep.** That is the *third* time this session a newer, more central
implementation re-broke something an older corner had already solved and documented:

| New code | Older code that already had it right |
|---|---|
| `EditFrame`'s single coordinate map (R65) | `_alt_coordinate_lift`'s `lo`/`hi` split, with a docstring explaining why |
| `design_prime`'s spacer-only cache key (R67) | `search_signature`'s on-target-inclusive key, with a docstring naming the hazard |
| `_cut_outcome`'s length-preserving guard (R51) | `_overlay_allele`, one function over, which had just lost it (R42) |

Codified in `openspec/project.md` under the conventions a spec must respect, with all three instances and
the practical rule: **when you add a coordinate map, a cache key, or an allele overlay, grep for the other
ones first.**

**Lesson: the reason this keeps happening is that the older implementation is usually in a module you are
not editing, and its lesson lives in a docstring rather than a type or a test — so nothing surfaces it at
the moment you need it. Three instances is enough to stop treating each as bad luck. A convention note is
a weak mechanism, but it is the right weight here: the alternative (extracting one shared coordinate/cache
primitive across `offtarget` and `enumerate`) would couple two subsystems that have good reasons to stay
separate, and would itself be a fourth new central implementation.**

## Round 69 — tidying after myself in the changelog (and stopping at the line where it stops being mine)

The `[Unreleased]` section had grown to ~2,500 lines across sixteen `###` change-type headings, which
Keep a Changelog — the format the file's own header claims to follow — allows one of per type per release.

Checked whether I caused it before fixing it. At the session's base commit the file already had five
`### Added` and several `### Fixed`, so the duplication is largely pre-existing. What I *did* cause is
narrower and worse: inserting a `### Changed` block into the middle of the pre-existing `### Fixed`
section, splitting it in two.

**Shipped:** the top of `[Unreleased]` is now `Added → Changed → Fixed` in Keep-a-Changelog order, with the
pre-existing Fixed content contiguous again. Done as a script, not by hand, with the verification a pure
reordering deserves: a `Counter` of every non-blank line before and after, asserting the only difference is
the one duplicate heading removed. It caught its own scope — the first run reported exactly one "lost"
line, `### Fixed`, which is the merge working.

**Stopped there.** The other thirteen duplicate headings are from before this session, in ~1,000 lines I
did not write, and restructuring them is a separate change with its own review. Flagged as a follow-up
task rather than folded in silently.

**Lesson: "clean up your own mess" needs a boundary, and `git show <base>:file` is how you find it. The
instinct on seeing a malformed 2,500-line section is to fix all of it — but the diff would then mix a
correction I owe with a refactor nobody asked for, and reviewing it would mean re-reading a thousand lines
of someone else's release notes to confirm nothing was dropped. Separately: any edit that claims to be a
pure reordering should be *verified* as one mechanically. Reordering is exactly the kind of change where
eyeballing a diff gives false confidence, because every line looks familiar.**

## Round 70 — every committed generated artifact, checked for a guard (1 gap, 2 clean)

R52 found that ten published JSON Schemas had silently drifted because nothing regenerated or compared
them. That is a question the repo can be asked in full: *which committed files are generated output of
code that keeps changing, and which of those have a test?*

| Artifact | Generator | Guard |
|---|---|---|
| `docs/schemas/*.json` | `scripts/export_schemas.py` | added in R52 |
| `scripts/reproduce_golden.json` | `scripts/reproduce.py` | CI's `reproduce` job |
| `benchmark/datasets/fixtures/`, `benchmark/splits/` | `scripts/make_benchmark_fixtures.py` | **content hashes** — a split carries its dataset's `content_hash` and `verify()` raises `SplitIntegrityError` on load, with tests pinning it |
| `docs/assets/figures/*.svg` | `scripts/figures.py` | **none** |

The figures are embedded in the README and the preprint. The existing tests covered determinism and that
rendering writes files — never that what is *committed* matches what the code renders now. They happened
to be current; nothing would have said so if they were not, and a stale figure shows numbers the pipeline
no longer produces to a reader with no way to tell. Guard added, mutation-checked, and pointed at
`make figures`.

Worth noting how the benchmark fixtures pass: not by a comparison test but by **content hashing** — the
split proves on load that neither its membership nor its dataset drifted. That is a stronger guarantee than
a regeneration check, and it is why R66's direct tests of `_canon` matter: the integrity of these fixtures
rests entirely on that one primitive being byte-stable.

**Lesson: the useful unit here is not "add a test for the figures" but the table — enumerate the class,
then check each member. Three of four were already covered, by three *different* mechanisms (a comparison
test, a CI job, content hashing), which is why no single search would have found the gap. The question that
finds it is about the artifact's nature ("is this generated and committed?"), not about the guard's
shape.**

## Round 71 — the intent nothing tested

*Entry reconstructed in R146 from commit `d88ce8b`; the original was never written, and R72 opens by citing
this number. Content is from the commit message, not from recall.*

`EditIntent.REVERT` is offered by the CLI (`--intent revert`), appears in five places in the library, and had
one mention in the whole test suite — an incidental line grouping it with `CORRECT`.

All five are independent `intent in (CORRECT, REVERT)` checks: routing, the cas9/base/prime enumerators, and
the HDR donor. Nothing centralizes the equivalence. A sixth branch added later that forgot `REVERT` would not
error — it would fall through to the `INSTALL` behavior and write the alternate allele where the user asked
for the reference. A wrong reagent from a one-word omission, on a path with no coverage.

`EditIntent` now documents all four intents and why `REVERT` exists (mechanically identical to `CORRECT`; it
distinguishes *why* the edit is being made, in provenance). Eight tests pin the equivalence at every layer,
each paired with an assertion that `CORRECT` and `INSTALL` genuinely differ at that locus, so the equivalence
cannot pass vacuously. The first draft used a locus where `enumerate_cas9` returned `[]` for every intent, so
the equivalence passed on `[] == []`; only the paired "must differ" clause caught it.

**Lesson: coverage measures whether code *ran*, never whether each public option was exercised. Ask which
public options nothing tests.** *(This lesson is quoted by R72, which generalizes it across every enum in
the library; the wording here is reconstructed from that citation and the commit.)*

## Round 72 — running R71's query across every enum in the library

R71 found an untested CLI-exposed intent by asking "which public options does nothing test?". Ran that
mechanically over every `Enum` in the package: 33 members are never named in a test. Most are false
positives — the CLI's `OutputFormat.json` is exercised as `--format json`, `Consequence.FRAMESHIFT` through
severity tables — so the list needed reading, not acting on.

Two looked behavioral. `ScoreMethod.CFD_CAS12A` turned out to be covered (`tests/offtarget/test_scoring.py`
names the scorer, not the enum member). **`ThreePrimeMotif.MPKNOT` was genuinely untouched** — no test, and
no caller either, since the enumerator only ever emits `tevopreQ1`. It is nonetheless a sequence that goes
into a *synthesized* extension oligo for anyone who builds a pegRNA with it, and `reconstruct()` strips the
declared motif off the 3' end before checking the RTT/PBS boundary, so a mishandled motif either corrupts
that boundary or ships the wrong bases silently. All three motifs are now parametrized through the oligo
round trip. Mutation-checked.

**What I did not do.** Both motif sequences are exactly 46 nt and share the 9-nt prefix `GAAACCCGG`, while
the adjacent comment describes only tevopreQ1 as carrying a linker. That may be perfectly correct. It is
also exactly the kind of thing I cannot check from memory — a published sequence, destined for a wet-lab
reagent — so it is flagged for a human to verify against the paper rather than asserted either way.

**A note on the tests catching me:** the first fixture used a truncated scaffold, and `pegrna_oligos`
rejected it with "a wrong or empty scaffold would ship a non-functional pegRNA". A guard written for users
caught the test author instead, which is a good sign about the guard.

**Lesson: line coverage cannot see an untried enum member — every line `MPKNOT` touches is covered, by
`TEVOPREQ1`. The generalization of R71 is that coverage measures whether code *ran*, never whether each
value a public type *admits* was tried, and enum members, boolean flags, and optional parameters are
precisely where an untried value takes a different branch. Enumerating the type's members and grepping is
a five-line script.**

## Round 73 — finishing a feature at both shells at once

The render cap added in R49/R50 was library-only: `render_html` and `render_pdf` took `max_candidates`, and
neither the CLI nor the web API exposed it. A user wanting the full page had no way to ask — only the
JSON/TSV exports, which are a different artifact.

**Shipped:** `aforge design --render-candidates N` and the API's `render_candidates` field, with `0`
spelling "draw them all" — the command line has no natural way to write `None`, and a zero-candidate render
is not a thing anyone wants. Tests on both surfaces pin that the cap changes the rendered page and **never**
the lossless export, which is the property a display cap must not violate.

The deliberate part is doing both shells in one change. R63 fixed the CLI's off-target labeling five rounds
after fixing the same thing in the library, and only found the web API still wrong by driving it — because
the CLI and the web API are both thin shells over one library, so a gap in how one *exposes* a capability
almost always exists in the other. Applying that forward is cheaper than rediscovering it.

**Lesson: "expose it on the surface I am touching" is how two shells drift. When a library capability is
worth reaching from one shell it is nearly always worth reaching from the other, and the cost of doing both
together is a few lines — versus a later round spent noticing, plus the window where the two behave
differently. The generalizable version: after adding a parameter to a library function, grep its call
sites in the shells before closing the change.**

## Round 74 — the honesty flag you could not raise

R73 ended with "after adding a parameter to a library function, grep its call sites in the shells". Ran the
inverse: which `design()` parameters can the shells not reach at all?

`cell_context` was the answer, and it is not a minor one. It is the input that raises the **OOD flag** —
the mechanism the README leads with ("any other cell context flags the efficiency prediction
out-of-distribution and raises an `ood` flag rather than hiding it"). It was reachable only through a CLI
*config file*, and **not at all** from the web API, whose `DesignRequest` had no such field.

So every design the web API returned reported `in_distribution: true` regardless of the cell line the user
was actually working in — not because the flag was broken, but because the surface most likely to be used
casually had no way to tell it the truth. A safety-by-honesty mechanism that cannot be *triggered* is
inert in the same way a mis-computed one is, and this one failed silently in the reassuring direction.

**Shipped:** `aforge design --cell-context HepG2` (overriding the config key, matching how the other
options resolve) and the API's `cell_context` field. Verified end to end: no context or `HEK293T`/`K562`
stays in-distribution; `HepG2` flips to `in_distribution: false` with the `ood` flag. Parametrized tests on
both surfaces, and a spec requirement that the flag be reachable from every surface that designs.

**Lesson: "is the feature implemented?" and "can a user reach it?" are different questions, and the
codebase only answers the first. The OOD machinery was correct, tested, and documented — and unreachable
from one of the two shells, which is indistinguishable from absent for anyone using that shell. The query
that finds this class is not about code quality at all: take the library's entry point, list its
parameters, and check each one against the surfaces. The gaps that turn up are, by construction, features
someone thought worth building and nobody finished exposing.**

## Round 75 — the differentiator was library-only

Continued R74's query — which `design()` parameters can the shells not reach? — through the rest of the
list. `gnomad`, `haplotypes`, `patient_vcf`, `offtarget_regions`, `encode_tracks` and `chromatin_track`:
none reachable from the CLI. The first one matters most.

**Population-aware off-target nomination is the capability this project is built around.** The README calls
reference-only off-target "a known safety gap", cites the Casgevy / BCL11A `rs114518452` case as the
cautionary tale, and `specs/readiness-assessment.md` names it "the genuinely differentiated, trustworthy
part — promote this without caveats". `design()` and `search()` have always accepted a `gnomad=` database.
**No CLI command could supply one.**

What made it hard to see: `--populations` *exists* on `design`, `batch` and `offtarget`. It names the
ancestry labels to stratify by and carries no alleles. So `aforge offtarget SPACER --populations afr,eur`
runs, exits 0, and returns `ancestry_stratification: {}` — an empty breakdown that reads as "no
ancestry-specific risk found" when it means "no population data was loaded". The presence of a
plausibly-related flag is what made the absent one invisible.

**Shipped:** `--gnomad <sites.tsv[.gz]>` on all three commands (`#chrom pos ref alt af <pop>...`, 1-based
`pos` as in a VCF — stated in the help, since the parser converts and the repo's conventions require being
explicit about that); an explicit warning when ancestries are requested without a source, saying the scan
is reference-only and the breakdown is *not measured* rather than clean; and a data error on an unreadable
path, because silently continuing hands back a reference-only scan the caller believes is population-aware.

Verified by reproducing the reference-bias case **through the CLI**: 0 sites reference-only, then one
`population`-origin site at score 1.0 with the risk concentrated in African ancestry (`afr` 0.105 vs `nfe`
0.001). Deliberately *not* extended to the web API in this round: a client-supplied filesystem path is a
server-side file-read primitive, so that surface needs server-side configuration like the reference, which
is a separate change.

**Lesson: the gap was not in a dark corner — it was in the feature the README leads with, on the primary
interface, and it survived because a neighbouring flag looked like it. `--populations` answered the
question "can I do ancestry-aware analysis from the CLI?" with a yes that was true about labels and false
about data. When auditing reachability, match on the *capability*, not on whether some related-sounding
option exists; and the fastest way to settle it is to run the command and check the output actually
contains what the capability promises, which here was one empty dict.**

## Round 76 — finishing the safety inputs, and a false warning I shipped one commit earlier

R75 exposed `--gnomad`. The same sweep had listed two more unreachable safety inputs, and both belong to
claims the README makes: the **haplotype**-aware pass (the second half of "population- *and haplotype*-
aware" — it catches a site that exists only on a co-inherited combination of alleles) and **patient**
personalization (a site present in this genome but not the reference).

**Shipped:** `--haplotypes <panel.tsv>` and `--patient-vcf <vcf|list>` on `design`, `batch` and
`offtarget`. Patient variants are resolved against the reference, so an allele asserting a base the genome
does not have fails loudly rather than silently personalizing the scan with a wrong-build variant.
`HaplotypePanel` gained `__iter__`/`__len__` — the engine consumes a flat iterable and does its own
overlap/frequency filtering, so a caller holding a whole panel with no single interval to query previously
had to reach into its private buckets. Verified through the CLI: 0 sites reference-only, one
`patient`-origin site with `--patient-vcf`, one causally-attributed site with `--haplotypes`.

**A false statement I shipped one commit earlier, caught by using the thing.** R75's "reference-only"
warning keyed on `--gnomad` alone. So the first `--haplotypes` run printed *"no population alleles were
searched. The off-target scan is REFERENCE-ONLY"* — on the same line as a report listing a population site
the haplotype pass had just found. The warning existed to stop a user misreading an empty ancestry
breakdown; keyed too narrowly, it told a confident lie instead. It now fires only when neither
ancestry-bearing source is present (`--patient-vcf` deliberately does not count — a personal genotype
carries no population frequencies and cannot fill an ancestry breakdown), and a parametrized test covers
all three cases.

**Lesson: a warning is a claim, and claims added to make something honest can be *less* accurate than the
silence they replaced. R75's warning was written against the one input that existed at the time and became
wrong the moment a second was added — one commit later, by me. Two guards worth taking from this: state
the condition in terms of *what the user needs* ("is there any ancestry-bearing data?") rather than the
flag in front of you, and run the feature you just added with the *other* flags it now coexists with. The
lie was visible in the first line of the first manual run.**

## Round 77 — writing down what the CLI can now do, and what it still cannot

Closing out the reachability thread with the documentation, which is where the gap was most damaging: a
reader could not have discovered that `--populations` carried no data, because nothing said so.

- **README**: the command table now carries an `IMPORTANT` callout stating plainly that the three safety
  inputs are opt-in files and the scan is reference-only without them, that `--populations` only names the
  ancestries to stratify by, and that an unbacked request warns "not measured, not clean". The `offtarget`
  example shows all three sources.
- **`specs/readiness-assessment.md`**: the honest-state file records what the sweep found and what it
  fixed, so a future session does not have to rediscover that the differentiator was library-only.
- **Named the remainder rather than leaving it implicit**: `offtarget_regions` and
  `encode_tracks`/`chromatin_track` are still library-only, and the three file inputs are deliberately
  *not* on the web API — a client-supplied filesystem path is a server-side file-read primitive, so that
  surface needs server-side configuration like the reference already has.

**Lesson: the reachability gap was really a documentation gap wearing a code costume. Nothing in the README
was false about the *library*; every claim held for `design(gnomad=...)`. What was missing was the sentence
connecting the claim to the interface a reader would actually use — and its absence let a plausible
neighbouring flag stand in. Writing down what a feature needs *from the user* is the check that catches
this: "population-aware" is not an adjective a tool has, it is a thing a tool does when given a file, and
the moment you have to write that sentence you notice whether the file can be given.**

## Round 78 — the gap was one layer deeper than the shells

Went to expose the last practical off-target knob, `offtarget_regions`, on the CLI — and found the
reachability gap was not in the shells at all. **`design()` does not accept a region restriction.** Every
vertical does (`design_cas9`, `design_prime`, the base-editor path all take `offtarget_regions`; `search()`
takes `regions`), and the unified entry point — the one the CLI and web API are thin shells over — took
none of them and passed nothing through. A whole-genome scan could not be narrowed from anywhere except by
calling a vertical directly, and over a real reference that scoping is the difference between a practical
run and an impractical one.

**Shipped:** `design()` gains `offtarget_regions` and threads it to all three verticals; the CLI exposes
repeatable `--region chrom:start-end` and `--regions-bed panel.bed` on `design`, `batch` and `offtarget`.
Two failure modes handled deliberately: a malformed region is a **usage error**, not a silent widening back
to the whole genome; and an empty restriction stays `None` ("search everything") rather than becoming an
empty list, which would restrict the search to *nothing* and report every guide spotless — the reassuring
value again, from an accidental `[]`.

**Lesson: "can a user reach this?" has more than two answers. The previous rounds assumed the library was
complete and the shells were behind it; here the aggregating layer was the one missing the parameter, and
the shells were faithful to it. When a capability is present in N specific implementations and absent from
the thing that composes them, every caller of the composer silently loses it — and it looks like a shell
problem right up until you read the composer's signature. Check the aggregator, not just the endpoints.**

## Round 79 — mistyping my own new flag found a bigger bug than the flag

Exposed the last library-only capability, the ePRIDICT open-chromatin adjustment: `--encode-tracks` +
`--chromatin-track` on `design` and `batch`, requiring the pair together (one alone would be silently
ignored, leaving efficiency unadjusted while the user believes it is chromatin-aware). `design()` was
missing these parameters too — the same aggregator gap as R78 — so they were threaded through to the prime
vertical. Verified: efficiency moves 0.4521 → 0.4972 with an open-chromatin track.

Then I mistyped the track name to check the failure path, and got **zero candidates, exit code 0, and no
error**. The designer had done its job perfectly: it caught the failure, degraded gracefully instead of
crashing the whole design, and recorded `prime: skipped (KeyError: "unknown track 'missing'; known:
('atac',)")` in `menu.rationale`. **`DesignReport` has no rationale field.** Every renderer dropped it.

So the diagnostic existed, was precise, and reached nobody. Worse, the same drop had been silently
discarding the empty-menu explanation added earlier in this session — routing's per-chemistry reasons lived
on the `RankedMenu` object and never appeared in a single user-facing artifact. Two rounds of careful work
on "explain why the menu is empty", invisible.

**Shipped:** `DesignReport.rationale`, rendered by the HTML under "How this menu was assembled" and printed
by the PDF above the candidates, with a spec requirement that a render explain how its menu was assembled.

**Lesson: graceful degradation and honest reporting are two halves of one mechanism, and only the first
half was built. Catching an error so one failure does not kill a run is right; it converts a crash into a
silence, and the silence is only acceptable if something downstream speaks. Worth checking wherever a
codebase "records a note and continues": follow the note all the way to a rendered artifact, because the
recording is the easy half and the delivery is where it gets dropped. Also, plainly: mistyping your own new
option is a cheap test worth running every time.**

## Round 80 — following every recorded diagnostic to a rendered artifact

R79 ended with a rule worth running as a sweep: *wherever a codebase records a note and continues, follow
the note all the way to a rendered artifact, because the recording is the easy half.* Enumerated every
`note`/`warning` sink in the library and traced each one.

**Already delivered, correctly:** cloning-oligo warnings (rendered prominently, above the JSON block),
cohort item errors (a TSV column), HDR donor re-cut disposition (in the reagent line *and* promoted into
the oligo warnings), routing/skip notes (fixed last round).

**One gap: `Prediction.notes`.** The renderers spell out `calibrated` and `in_distribution` inline —
"nominal — coverage not measured", "out-of-distribution" — but **nothing rendered `notes` at all**. The
flags had renderers; the free text did not. So the note added earlier in this session stating that the
default prime scorer *has no edit-size term* lived only in the JSON, and the HTML and PDF for a multi-base
prime edit were silent about it. That note exists for exactly one reader — someone looking at a 4-nt
insertion's efficiency number — and it was absent from exactly their page.

**Shipped:** both renders show any note the inline wording does not already convey, deduplicated across
efficiency and bystander predictions, skipping the nominal-interval note because the parenthetical already
says it. Verified end to end: the caveat appears for a multi-base edit and is absent for an SNV.

**Lesson: a data model with both structured flags and free text will grow renderers for the flags, because
flags are what you format. Free text has no obvious place in a layout, so it gets carried faithfully
through every serialization boundary and then quietly omitted at the last one. If a field is worth adding
to a model for honesty's sake, the same change should add it to the render — otherwise it becomes a
disclosure that only satisfies a machine.**

## Round 81 — re-examining my own exclusion, and finding it too broad

R75 declined to put the safety inputs on the web API, for a real reason: a client-supplied filesystem path
is a server-side file-read primitive. R78 then added region scoping to the CLI and I filed it under the
same exclusion. Re-reading it: **a region restriction is not a file.** It is a list of intervals — data,
the same shape a reported site's `locus` already has — and carries none of that risk. The exclusion was
right for four inputs and wrong for the fifth, because I applied it to the batch rather than to each
member.

**Shipped:** `offtarget_regions` on `POST /api/design` and `POST /api/offtarget`, via a small `Region`
model that deliberately does **not** require a strand (a restriction covers both by construction) while
still accepting a `locus` pasted from a previous response, whose extra keys are ignored. Two failure modes
handled: an empty interval is a 422 rather than a scan silently scoped to nothing, and an empty *list*
means "search everything" rather than "search nowhere".

**A test that was wrong, not the code.** Restricting the scan to a site's own 20 bp span returned zero
sites, which looked like a bug. It is correct: the scan needs room to place a protospacer *and* its PAM,
which a 20 bp window does not give. The test now uses a containing window and says why — a note worth
leaving, because the intuition "restrict to the hit's locus and you should still find the hit" is wrong
here and someone will have it again.

**Lesson: a security exclusion should be justified per capability, not per batch. "The file inputs are
unsafe over HTTP" was a correct sentence that quietly absorbed a non-file input standing next to them, and
the cost was a capability withheld from a whole surface for a reason that did not apply to it. Blanket
exclusions are cheap to write and hard to notice being wrong, because nothing fails — the capability is
simply missing, and the reason sounds sound.**

## Round 82 — the inputs I had just made reachable were not being recorded

Having spent several rounds making the safety inputs reachable, asked the obvious follow-on: does a run
that uses them *say* it did? The project's stated principle is that a result is re-derivable from its
provenance, and `specs/` requires every consumed dataset be recorded.

**It recorded none of them.** `_collect_datasets` consulted the reference, gnomAD and ClinVar, and only
kept a source carrying a `dataset_version` descriptor — which a file loaded from a path does not have. The
haplotype panel and patient variants were not consulted at all. So a run could be population-aware,
haplotype-aware *and* personalized while its provenance named nothing of it. Beyond reproducibility, a
reader could not tell a populated scan from an unpopulated one — the same ambiguity R56 fixed in the
cohort summary, one layer up.

**Shipped:** each supplied file is pinned by the **content hash of what it contained** (a user's file has
no upstream version, so the honest pin is the bytes); `design()` collects the haplotype and chromatin
sources; and the CLI now passes the *panel* rather than a flattened tuple, so the descriptor survives the
trip. A source with no descriptor is omitted rather than given an invented one.

**One deliberate asymmetry.** Personal variants are recorded as *that the run was personalized, and over
how many variants* — no content hash. Reproducibility does not require one, and a content hash of a
personal VCF embedded in a shareable report is an identifier for that file and, transitively, for a
person. The reader's actual need is to know a `patient`-origin site could appear and at what scale, which
the count gives. Written into the spec so the asymmetry reads as a decision rather than an oversight.

**Lesson: making a capability reachable and making it *accountable* are separate pieces of work, and the
second does not follow from the first. Every round that adds an input should ask what the result now
depends on that it did not before — because provenance is a whitelist, and a whitelist silently omits
whatever nobody added to it. Also worth naming: the flattening (`tuple(panel)`) that dropped the
descriptor was a line I wrote two rounds earlier for a good reason. Convenience conversions are where
metadata goes to die.**

## Round 83 — a scoped scan that looked exactly like a clean one

R82 fixed *which data* a run consumed. The neighbouring question: does the result record *how much of the
genome it looked at*?

It did not. The provenance config snapshot carried `intent`, `weights`, `populations`, `run_offtarget`,
`cell_context` and the resolved settings — and nothing about the region restriction I had added two rounds
earlier. A scan narrowed to a 100 bp window reports far fewer off-targets than one over every contig, and
**"0 off-target sites" read identically either way**. A user who scoped a run for speed, or inherited a
scoped config, had no way to tell from the artifact that the search had been narrowed. Same class as the
cohort's `worst_offtarget = 0.0` (R56) and the CLI's unlabelled `specificity` (R58): a number that is
correct for what was measured, presented without what was measured.

**Shipped:** `null` for a genome-wide scan; otherwise `{n, bases, sha256}` — how many intervals, how much
sequence, and a content pin of the canonicalized list. Compact enough not to drag a whole BED file into
provenance, order-independent (sorted before hashing) so two runs agree iff they restricted to the same
intervals, and content-sensitive so a different panel does not collide. `chromatin_track` is recorded too,
since it changes every efficiency number in the menu.

**Lesson: this is the third instance of one shape, so it is worth stating as a rule rather than a story —
*any parameter that narrows what was examined must appear beside the result*. Not for reproducibility,
which is the usual argument, but because the result's *meaning* depends on it: "we found nothing" is a
different claim from "we found nothing in the 140 bases we looked at", and only one of them is what the
number alone conveys. When adding a knob that scopes work, add it to the record in the same change.**

## Round 84 — the same rule, swept instead of storied

R83 ended with a rule rather than an anecdote: *any parameter that narrows what was examined must appear
beside the result*. A rule is only worth stating if it can be **run as a query**, so I ran it against the
off-target engine's own knobs — the place the rule matters most, since the whole value proposition is a
number that says "this guide is safe".

`search()` takes five settings that narrow what it can possibly find: the mismatch budget, the DNA and RNA
bulge budgets, and the CFD and MIT reporting cut-offs. `OffTargetReport` recorded **one** of them. That is
the "N implementations, one differs" tell, and here the odd one out was the *honest* one: whoever added
`mismatch_threshold` did it for exactly this reason, and the four settings added later did not follow.

The consequence is not a reproducibility footnote. A zero-bulge scan physically cannot report the bulged
hits a one-bulge scan finds, and the default 0.20 CFD cut-off hides sites a 0.05 cut-off shows — so "2
sites" and "15 sites" for the same guide are both correct and not comparable, with nothing on either
artifact to say why. Provenance carried the settings for the *run*; the report a user actually reads and
forwards did not.

**Shipped:** `dna_bulge_budget`, `rna_bulge_budget`, `cfd_threshold`, `mit_threshold` on `OffTargetReport`,
populated from the arguments actually used; a spec requirement; and a test mutation-checked against a
hardcoded cut-off. The reproduce golden moved — diffed field by field to confirm the only delta was the
four new keys.

**Lesson: a rule earned in one round should be spent in the next as a search, not re-derived from a new
story. The cheapest form of that search is "this module takes five parameters of one kind — how many reach
the output?", and the answer being *one, added deliberately* is evidence the rule is right, not evidence
the gap is closed.**

## Round 85 — the round before had already broken something

R84 added four fields to `OffTargetReport`. The obvious next question is not "what else needs recording?"
but **"who else builds one of these?"** — because a model gains fields, and every place that *reconstructs*
one field by field silently drops what it does not name.

`grep 'OffTargetReport('` returned exactly two call sites: the engine that creates it, and
`design/prime.py:_merge_offtarget`, which merges the pegRNA-nick and ngRNA-nick reports for every PE3/PE3b
candidate. It rebuilt the report field by field. R84 had therefore, three commits earlier, made every prime
candidate report `cfd_threshold=0.20` regardless of what the run used.

The comment above that rebuild is the real finding. It documented — carefully, with reasoning — two earlier
occurrences of the identical bug: the scorer/matrix identity lost through the merge, and the sub-threshold
tail reset to `0.0`. Each had been fixed by adding the forgotten field to the constructor call. Three
instances, three point fixes, and the mechanism untouched. The comment was a monument to a bug that kept
being patched instead of removed.

**Shipped:** `peg.model_copy(update={...})`, naming only the two fields that genuinely aggregate — the
deduplicated sites and the summed sub-threshold tails. Everything else is `peg`'s already, because both
reports come from the same search. The regression test compares the merged report against the pegRNA report
**by iterating `OffTargetReport.model_fields`** rather than naming fields, so it covers fields that do not
exist yet; mutation-checked by restoring the old rebuild, which fails on `dna_bulge_budget`.

**Lesson: a *narrowly wrong* value is worse than a missing one — an absent cut-off invites a question, a
default cut-off answers it falsely. And when a comment explains why a particular field is carried through a
manual reconstruction, that comment is the bug report: the fix is not to add the next field to the list, it
is to stop keeping a list. After adding a field to a shared model, grep for the model's other constructors
before doing anything else — that is a two-second check that R84 skipped and R85 paid for.**

## Round 86 — recorded is not the same as shown

R84 recorded the search's budgets and cut-offs on `OffTargetReport`. R85 found that the very next code path
dropped them. R86 asked the third question in that sequence: **who displays them?**

Nobody. Four surfaces render an off-target result — the HTML page, the PDF leave-behind, the CLI's human
line, and its JSON payload — and all four printed "2 nominated site(s), specificity 0.82" with no statement
of the scan that produced it. The fields existed, were correct, serialized fine, and were invisible to
every human who would ever read one.

That is worth separating from the R83/R84 rule rather than folding into it. "Record the parameter that
narrowed the result" is satisfied by a field on a model, and a field on a model satisfies a schema check, a
round-trip test, and a reproducibility argument — while doing nothing at all for the person holding the
printout. The artifact a collaborator receives is the thing that has to be self-describing.

**Shipped:** `OffTargetReport.search_description()`, a one-line statement of all five settings;
`CandidateReport.offtarget_search` carrying it beside the existing scorer/matrix labels; render lines in
HTML, PDF and the CLI; a structured `search` object in the JSON payload. The shared report fixture was
moved to **non-default** budgets and cut-offs, because a render test asserting the defaults cannot
distinguish "prints the settings" from "prints a hardcoded string that reads like them" — the three new
assertions were mutation-checked against a hardcoded description and all three fail.

One incidental find: the PDF's existing font-coverage guard caught that `≤` and `≥` are not in WinAnsi and
would have printed as `?` on the page. The description is ASCII for that reason. A guard written four
rounds ago for a different problem paid for itself here.

**Lesson: "the field exists" and "the reader can see it" are different claims, and the tests that prove the
first (schema freshness, round-trip, provenance hashing) all pass while the second is false. After adding a
field whose purpose is to inform a human, grep the renderers — the field is not done until every surface
that shows the number it qualifies also shows it.**

## Round 87 — the successful path was the silent one

The R86 sweep — "which model fields does no renderer touch?" — was cheap enough to run over every core
type, not just the report models. Six came back. The one that mattered: `BlockingMutation.reference_base`
and `.donor_base`.

A precise nuclease correction ships an HDR donor. If the repaired allele still presents the guide's PAM and
seed it gets cut again, so the donor carries an extra base substitution to break it. That substitution is
an edit to the patient's genome that nobody requested, and whether it is silent depends on a reading frame
AlleleForge does not have. The enumerator knew this and wrote it down — `note="PAM-blocking mutation
chr2:36 G>A; confirm it is synonymous in your reading frame"` — and every render put that note inside a
collapsed `<details>` JSON blob.

So the report's prominence was inverted. **When the block could not be found**, the user got a loud warning
that the correction is re-cuttable. **When it succeeded**, the reagent quietly acquired a second permanent
mutation and the instruction to verify it was filed where nobody looks. The failure mode was well
signposted; the success mode was not, and the success mode is the one that ends up in a genome.

**Shipped:** `donor_oligo()` promotes the blocking mutation into `warnings` — the same channel the
too-long-for-one-oligo and re-cuttable hazards already use, which the HTML and PDF renders print as their
own line — naming the position, the change, the region, and the check. A donor with nothing extra stays
silent (asserted, or the warning would mean nothing). Mutation-checked, and confirmed end to end by
building a real blocked donor and reading it out of both renders.

**Lesson: "confirm X" is an action, and an action does not belong in a `note`. More generally — when a
mechanism has a success path and a failure path, check which one is louder. It is natural to write the
warning for the failure and let the success pass without comment, but here the success *is* the
intervention: it does something to the genome that the failure does not. Ask what the successful path
actually did before deciding it needs no words.**

## Round 88 — the footer that proved the wrong thing

The R86 field sweep had one more entry worth acting on: `Provenance.tools`, which no renderer touched. It
turned out to be worse than the sweep said. `datasets` *was* referenced somewhere in the render/CLI corpus
— by the `verify` command — so the sweep scored it as covered. It was not in the report footer either.

That footer is the trust anchor. It exists so a result is self-contained for audit, and it printed the
AlleleForge version, the reference build, the seed, the timestamp, and the models. A reader could tell
exactly which code ran and nothing whatsoever about the data it ran on — while the headline claim of the
whole tool, *population-aware* off-target search, is a claim about data: which gnomAD release stratified
those ancestries, whether a patient VCF was applied at all. Two rounds ago (R82, R83) I made the pipeline
record its data inputs precisely. The last step dropped them.

The footer was also two implementations, in `html.py` and `pdf.py`, which had already drifted on wording
and would each have had to grow the same field twice.

**Shipped:** one `provenance_lines()` both renders call, now including `datasets` and `tools`; and a test
that iterates `Provenance.model_fields` asserting each is either rendered or named in
`PROVENANCE_FOOTER_OMITTED` with its reason. The omission list is itself checked against the real fields so
it cannot rot. Mutation-checked by removing the datasets line.

**Lesson: a grep-based "is this field used anywhere?" sweep answers a weaker question than the one that
matters, and will mark a field covered because some unrelated command mentions it. The sharper query names
the surface — "does *the footer* print it?" — and it is worth re-asking per surface rather than trusting
one corpus-wide grep. Also: a curated summary is fine, but every omission from it should be a recorded
decision, because otherwise there is no difference between 'left out' and 'forgotten'.**

## Round 89 — a number computed for nobody

Last of the R86 field sweep, and the one with teeth: `NickingGuide.nick_offset`. The enumerator computes
it, the model stores it, and nothing reads it. Not the reagent line, not the flags, not the ranking.

This is not a display gap of the R86 kind, where a qualifier was missing from a number that was at least
shown. PE3 *is* the nick offset. A PE3 candidate is a pegRNA plus a second nick, and the second nick's only
free parameter is where it goes. Every PE3 candidate in a menu therefore read identically — same spacer,
same PBS, same RTT, "PE3" — while differing in the one thing a user would choose between them by. And two
nicks placed close together on opposite strands are a staggered double-strand break, which is the outcome
prime editing is picked over nuclease editing to avoid. Running the fixture confirmed the concern is not
hypothetical: its only PE3 nicking guide sits **4 nt** from the pegRNA nick, and nothing in the output said
so.

**Shipped:** a signed `nick-distance:+62nt` flag, `PE3 (+62 nt nick)` on the reagent line, and a
`close-nick` annotation below a `CLOSE_NICK_NT` floor. The test drives both sides of that boundary — the
fixture only produces close nicks, so a distant one is constructed explicitly, or "close-nick" would only
ever have been asserted true and a flag that is always on carries no information.

**Not shipped, on purpose:** nick distance does not enter ranking. There is a real relationship between
nick distance and indel byproducts, and no calibrated model of it here — inventing a weight would have made
the composite score look better informed than it is. The number is shown; the user applies the literature.
The constant is labelled in the source as a conservative floor rather than a fitted threshold, and flagged
for verification against the primary literature.

**Lesson: "computed but unread" is a stronger signal than "unrendered". An unrendered field usually means a
display gap; a field that no consumer reads at all means the work of computing it was done for a purpose
nobody finished. Grep for a field's *readers*, not its mentions. And when the honest fix is
half-a-feature — show it, do not score it — ship the half you can defend and say in the source why the
other half is absent, rather than filling the gap with a plausible constant.**

## Round 90 — three doors locked, one open

R89's lesson was to grep for a field's *readers*, not its mentions. Run over every pydantic model in the
project, that query returned 36 fields nothing reads. Most are legitimately write-only — API response
models, serialized outputs. Two were not, and they point at the same place: `Settings.allow_network`, whose
docstring says the registries "must never auto-download" when it is false, is read by nothing at all.

Chasing what that toggle was supposed to govern found four network egress points. Three — the model zoo,
the dataset registry, the reference genome — refuse to fetch without an explicit `consent=True`. The
fourth, `VepRestPredictor.predict()`, issued a live GET with no gate whatsoever. The "N implementations,
one differs" tell, and the one that differs is the one that leaks.

The asymmetry is worth naming, because it is why the missing gate is not merely inconsistent. The three
registries *download*: a URL goes out, a file comes back, and the gate is really about bandwidth, licensing
and the checksum guarantee. The VEP call goes the other way — the variant's chromosome, position and both
alleles leave the machine and land at a third-party public API, and this project accepts patient VCFs as
input. **Consent to fetch a reference genome is not consent to disclose a variant**, so it has to be asked
separately rather than inherited.

**Shipped:** `consent=True` on the built-in fetcher, with a refusal that names both what leaves and where
it goes. An injected fetcher stays ungated — the caller owns the transport, and that is exactly how CI
replays a recorded response offline; gating it would break offline use to protect against nothing.
Mutation-checked.

**Deliberately not in this round:** making `Settings.allow_network` load-bearing across all four paths.
That is a real second change with its own semantics to settle (a process-level floor beneath the per-call
consent) and its own tests, and folding it in here would have made both halves shallower. It is the next
round.

**Lesson: when auditing a permission gate, do not stop at "is it enforced?" — ask what each gate is
protecting, because the same word can cover two different risks. Here `consent` meant "may I download" in
three places and would have to mean "may I disclose" in the fourth, and only the second one has a patient
on the other end of it. A consistency sweep that had simply copied the existing gate would have got the
mechanism right and the reasoning wrong.**

## Round 91 — finishing the switch that wasn't wired

R90 deferred this deliberately: `Settings.allow_network`, documented as the switch that stops the
registries auto-downloading, read by nothing.

The interesting part was not the wiring, it was deciding what the setting *means*, because two readings of
the same field name are both plausible. As a **floor**, a fetch would need `consent AND allow_network` — a
hard kill switch. As a **standing consent**, a fetch needs `consent OR allow_network` — an environment-level
form of the per-call flag. The field name argues for the floor; the docstring argues for the standing
consent, saying callers "pass an explicit consent flag" as the alternative to it.

Both readings agree on the default, which is the part that matters: `allow_network=False` and no per-call
consent means nothing is downloaded, either way. They differ only on whether `consent=True` should keep
working when the setting is false — and today it does, everywhere, including in the CLI's own
`--trained-efficiency` path. The floor reading would have been a silent breaking change to the documented
API, justified by nothing more than my preference for how the name reads. So: standing consent, stated
plainly in the docstring and in `docs/data.md`, and the default preserves current behavior exactly.

The scope limit is the R90 finding carried forward. `allow_network` permits **downloads**. It does not
authorize disclosure — a variant sent to Ensembl stays gated at its own call site whatever this setting
says, because the two are different acts and one of them has a patient on the other end.

**Shipped:** `artifact_download_permitted()` in `config.py`, called by all three registries in place of
three identical `if not consent` copies (R85's rule about duplicated checks), refusal messages naming both
ways to consent, and a docs table. Two tests, both mutation-checked: one on the predicate in both
directions, one through a real registry — because a correct helper that no gate calls is precisely the
state this round found.

**Lesson: when a dormant flag is finally wired up, the ambiguity in its meaning is the change, not the
wiring. Prefer the reading the existing docstring and call sites already assume, and prefer the one that
does not silently break a documented API — then write the choice down where the next reader will see it.
Picking the interpretation that sounds stricter is not the safer option if it changes behavior nobody asked
to change.**

## Round 92 — the reason the variant was chosen

Back to the R90 sweep of fields nothing reads. `ClinVarRecord.significance`, `.review_status` and
`.raw_significance` were all on it: parsed carefully out of `CLNSIG` and `CLNREVSTAT`, normalized through a
hand-built ACMG map, and then dropped. `resolver._from_clinvar` was one line —
`return clinvar.get(accession).variant`.

Nobody resolves `VCV000012345` because they want its coordinates. They want it because of what ClinVar says
about it. The tool read that, threw it away, and produced a menu in which a *Benign* variant and a
*Pathogenic* one are indistinguishable — happily designing a "correction" for an allele the database says
is harmless. `docs/data.md` even listed ClinVar's role as "accession → normalized variant + clinical
significance"; half of that was fiction.

Two design points were worth getting right rather than fast:

**Carry the review status, not just the class.** "Pathogenic, no assertion criteria provided" and
"Pathogenic, reviewed by expert panel" are the same class and completely different evidence. Reporting the
class alone would have been a second, subtler version of the same error — a correct number without the
thing that makes it interpretable, which is the R83 rule again.

**Annotate, never refuse.** Correcting a benign variant may be exactly right: a research control, or a
reclassification ClinVar has not caught up with. The system has no business blocking it. It has every
business making sure the user is not doing it by accident. So the menu states the assertion, adds a note
when intent and classification disagree, and stops there — and a congruent design stays silent, which is
what makes the note mean anything.

`ClinicalSignificance` moved to `types/variant.py` so the resolver could carry an assertion without
importing the data layer it deliberately reaches only through a Protocol; a coordinate-only stub still
resolves and simply asserts nothing.

**Lesson: ask what the *input* was for. Most of these rounds have asked what an output means; this one came
from asking why a user would type a ClinVar accession instead of `chr11:5227002:A>T`. The answer is the
classification — so a pipeline that keeps only what the two input forms have in common has quietly thrown
away the entire difference between them. Whenever an input form is richer than the one it is normalized
into, check what the normalization dropped and whether the user would have expected it to survive.**

## Round 93 — the honest field that never left the card

Last of the R90 sweep. `ModelCard.intended_use` and `.out_of_scope_use`: read by nothing.

Following them found the same break twice in one chain. `to_checkpoint()` is a hand-written field list —
the R85 shape, except `ModelCard` and `ModelCheckpoint` are different classes so `model_copy` cannot save
it — and it carried `known_failure_modes` while dropping the other two. Then, at the far end, no render
printed *any* of the three. `known_failure_modes` had a docstring saying it exists so a consumer can audit
a design "without re-opening the cards". The audit still required re-opening the cards.

What makes this worth a round rather than a line: the content is not boilerplate. The shipped
`cas9-efficiency-ensemble` card — the **default** Cas9 efficiency scorer, the number at the top of most
menus — says out of scope is "trusting the point estimate as a trained activity prediction (the heads are
an unfitted pseudo-random scaffold)". The project wrote that down, honestly, in the right place, and then
every report it produced was silent on it. A model card nobody reads is a compliance artifact; a model card
printed under the result is a warning.

The ordering argument matters too. A result that lists how a model fails but not what it was never meant
for carries the weaker half of the card. Failure modes describe the edges of a valid use; out-of-scope says
this was not a valid use at all.

**Shipped:** both fields on `ModelCheckpoint` and in `to_checkpoint()`; a **Model limitations** section in
HTML and PDF from one shared `model_limitation_lines()`; and a `to_checkpoint()` test that compares against
the card over the two models' shared field *names*, so tomorrow's field is covered without editing it. A
model documenting nothing yields no line and no section — an empty heading reads as "no known limits",
which is the opposite of the truth. Both layers mutation-checked.

**Lesson: a self-contained-for-audit claim is testable, and it is not the same claim as "the field is in
the JSON". Ask who performs the audit and with what in their hands. Here the field was serialized,
schema-checked, provenance-hashed and reproducibility-pinned — every mechanical guarantee held — and the
human doing the safety audit still had to go and find the model card, which is the exact thing the field
was added to prevent.**

## Round 94 — paid for, then thrown away

`VariantEffect` had *every* field on the R90 no-readers list, and so did `ResolvedVariant.effect` itself.
Wiring up an effect predictor made the resolver call it, build the full annotation — gene, consequence,
impact tier, HGVS c. and p., transcript, canonical flag — attach it to the resolved variant, and stop.
Nothing downstream ever looked.

The mirror of R92, but with a sharper edge, because R90 had just raised the price. That lookup is a network
round trip to a third-party API, and I had spent the previous round making the user explicitly consent to
sending their variant there. Consent to disclose, granted, for data that is then dropped on the floor.
Whatever the right trade is between a VEP annotation and a disclosure, *disclose and discard* is not on the
list.

Two details worth the care:

**Qualify the transcript.** The same variant is missense on one transcript and intronic on another. A bare
"missense variant" is half a statement, so the line names the transcript and says explicitly when it is not
the canonical one — R83's rule, applied to a consequence instead of a count.

**Modifier impact is a note, not a verdict.** A correction targeting a variant with no predicted protein
consequence is worth a second look before the bench work starts, and nothing more: a silent variant can
still be a splice or regulatory target, and the predictor speaks for exactly one transcript. Annotate,
never refuse — same disposition as R92's ClinVar notes, and a design with real predicted impact stays
quiet so the note keeps its meaning.

**Lesson: when a feature has a *cost* — a network call, a disclosure, a paid API, a slow pass — trace its
output to a consumer before anything else. An expensive dead end is worse than a cheap one, and the cost
makes it findable: ask what the user was buying. This one became visible only because the round before had
put a price tag on it.**

## Round 95 — the column that was missing from the honest table

The last productive entry on the R90 no-readers list: `BenchmarkResult.n_out_of_distribution`, computed by
the runner and read by nothing.

The leaderboard's columns are Rank, Model, Submitter, primary metric, ECE, Split. Including ECE is a
deliberately honest choice — calibration next to accuracy, so a confident-and-wrong model cannot hide
behind a good score. Its sibling was left off. `n_test` and `n_out_of_distribution` were both sitting on
the result, so the share was one division away, and without it two models with the same number in the
metric column are indistinguishable: one that stood behind every prediction, and one that disclaimed 87% of
them. The uncertainty contract *makes* models declare this. The board then hid the declaration.

Two small distinctions were worth keeping:

**`n/a` is not `0%`.** A model that scored nothing must not appear to have stood behind everything. The
board already draws this line for an undefined ECE — a degenerate model cannot win the calibration
tie-break with a perfect `0.0` it never earned — so the OOD cell follows it.

**Report, do not rank.** Making the OOD share a ranking term needs a defensible exchange rate between
accuracy and coverage, and there isn't one to hand. Same call as R89's nick distance: show it, let the
reader weigh it, and do not manufacture a number that makes the ranking look better informed than it is.

An incidental confirmation: the first version of the test edited a result with `model_copy` and the
submission gate rejected it, because the signature is a content hash over the body. The gate works. The
test now re-signs properly and asserts `verify_signature()` on the way through.

**Lesson: when a table already contains one honesty column, ask what its siblings are. Whoever added ECE
was answering "what would let a bad model look good here?" — that question has more than one answer, and
the first one usually ships alone. This closes the R90 sweep; the next round needs a different query.**

## Round 96 — reading the README as a claim

The R90 field sweep is exhausted, so: a different query, and an overdue one. Twelve rounds had changed what
the tool does for a user without once checking whether the README still described it. Read the README not
as documentation but as a **list of assertions**, and test them.

Two findings, of opposite kinds.

**A false claim.** The external-adapter table said VEP supplies "molecular consequence for chemistry
routing". Routing is `route(resolved, intent)` — a pure function of variant class and intent that has never
seen a consequence, and until R94 *nothing at all* read one. Not a stale claim that used to be true: an
architectural description of a wire that was never connected. Those are the dangerous ones, because they
survive every test the code has.

**A missing one.** Checking mechanically that every registered CLI command appears somewhere in the prose
turned up `aforge verify` — the command that re-hashes a result's pinned checkpoints and datasets against
provenance, the thing that makes "provenance is a checkable contract" more than a slogan — documented in
neither the README nor `docs/`. It shipped complete, its tests pass, and no user would ever find it.

The mechanical half is now a test. It cannot judge whether documentation is *good*, only whether each
command is mentioned at all — which is exactly the check that was missing, and it comes with a
guard-the-guard case so it cannot pass on prose it never read.

The rest of the round was catching the prose up to twelve rounds of shipped change: the two kinds of
consent, the clinical and effect notes that now lead a menu, the settings and model limitations every
render carries, the PE3 nick distance, the HDR blocking mutation, the leaderboard's OOD column.

An honest note on process: mid-round I ran `git checkout README.md` to undo a one-line mutation test and
destroyed every README edit in the round. Recoverable only because each edit was scripted. **Never
`git checkout <file>` to revert a deliberate local mutation — copy the file aside first, as the source
mutation checks in every other round already do.**

**Lesson: documentation drift is invisible to a test suite by construction, so it needs its own pass, and
the pass that finds the most is the mechanical one — every command, every flag, every file path in the
prose, checked against the code. Prose claims about *architecture* deserve the most suspicion: "X feeds Y"
is exactly the sentence nobody re-reads after Y stops reading X, and no test will ever notice.**

## Round 97 — the rest of the mechanically checkable prose

R96's every-command check was one instance of a general idea, so this round ran the rest of it: do the
prose's **links** point at files that exist, and are the **module paths** it cites importable?

Symbols: clean, all thirteen. Links: one break, and a telling one. `README.md` and `CONTRIBUTING.md` both
sent contributors to a Contributor Covenant that was not in the repository. Not a stale path — a promise
that had never been kept, on a public open-science project, in the two files a first-time contributor reads.

The repair needed some care about what is mine to decide. Adopting a code of conduct is a governance act,
and the repository had already committed to one twice; making that commitment real is repairing a stated
intent rather than inventing policy, so the file went in. But two choices inside it are the maintainer's,
and both are now flagged rather than settled quietly:

- **Adoption by reference, not verbatim.** Reproducing a specific versioned document from memory risks
  getting it subtly wrong, and a copy in-repo can silently drift from the version it claims to be. By
  reference it cannot. Some maintainers still want the text inline, for GitHub's community-standards check.
- **GitHub-only reporting.** The Covenant expects a direct contact and the repository publishes no
  maintainer email. Publishing a personal address on someone's behalf is not a call to make silently, so the
  file names the channels that exist today — a private security advisory, or an issue.

Both checks are now tests, with an explicit allow-list (each entry needing a reason) for paths the prose may
legitimately cite before they exist, so the mechanism cannot become somewhere to park the next broken
promise.

**Lesson: the highest-value target for a mechanical prose check is not the API documentation, which people
re-read, but the *governance and onboarding* files, which nobody re-reads and which a newcomer reads first.
A README's technical claims get corrected by users who hit them; `CONTRIBUTING.md` pointing at a file that
does not exist just quietly greets everyone who shows up.**

## Round 98 — reading my own output as a user

The mechanical prose checks came back clean this round (README imports resolve, module paths import, links
now check themselves), so I did what my own notes say has the highest yield and stopped auditing: built a
realistic correction on a 4 kb contig with a gnomAD sites file and two ancestries, ran it through the CLI,
and read the rendered HTML page as a user would.

The top candidate — rank 1, on the Pareto front, the reagent someone would order — said this:

```
flags: epegRNA:tevopreQ1, pe3b, nick-distance:+8nt, close-nick, both-nicks-searched
```

An 8 nt nick pair is a staggered double-strand break. It is the single most consequential fact about that
candidate, and it was rendered as the fourth item in a comma-separated list, indistinguishable from *the
motif is tevopreQ1*.

The uncomfortable part: I added `close-nick` in R89, and R87 had already established, for the HDR donor,
that a hazard belongs in the hazard channel rather than the notes bag. I applied that lesson to the oligos
and then, two rounds later, dropped a new hazard straight into the flat flag list — which is exactly the
failure the lesson describes. Reading the output caught in one minute what nine rounds of source-level
queries did not.

Nine other flags turned out to be in the same position: `ood` (the whole honest-uncertainty mechanism, in a
comma list), a re-cuttable HDR donor, an NHEJ-spectrum outcome, bystander bases in the base-editing window,
a population-only off-target, an internal cloning-enzyme site that will cut the insert.

**Shipped:** `CAVEAT_FLAGS`, a hazard → reason map; caveat lines in HTML and PDF ahead of the flat list,
which still carries everything. And a guard that reads every `flags.append(...)` literal **out of the
source** and fails on any flag classified as neither hazard nor description — deliberately defaulting to
"needs a decision", because defaulting to harmless is the direction that loses a hazard.

**Lesson: source-level queries find things that are absent; only reading the output finds things that are
present but *weightless*. Nothing was missing here — every fact was on the page, computed correctly,
serialized, tested. It was flat. A rendering that gives a double-strand break the same visual weight as a
motif name is a correct report and a misleading one, and no query over the code can see that. Run the
product and read it, on a schedule, not only when a query comes up empty.**

## Round 99 — a ranking finer than its own error bars

Kept reading the same rendered page as R98, one level down. The menu offered **470** prime candidates in a
strict order. Measuring the numbers behind it:

| | |
|---|---|
| composite score, #1 | 0.747 |
| composite score, #50 | 0.720 |
| spread across the ranked top fifty | **0.027** |
| the leader's own efficiency interval | **0.30** wide |

The interval on the single largest input is **eleven times** the entire spread of the list. Every candidate
in the top sixty was within 0.05 of the leader. On the full menu, 248 of 470 are within the leader's own
uncertainty of it. The sort is exact arithmetic on numbers that do not support it, and a reader who takes
"#1" to mean "better than #12" is reading a claim the tool never had the evidence to make.

This one stings a little, because "honest uncertainty" is the project's headline principle and every piece
of machinery for saying this already existed — the interval is computed, carried, calibrated, rendered, and
already used to discount the efficiency term. What was missing was the arithmetic nobody did: comparing the
spread of the ordering against the width of its own inputs.

The rule is stated, not fitted. The efficiency term contributes `w_efficiency x efficiency`, so the honest
uncertainty in that term alone is `w_efficiency x (upper - lower)`; a composite gap below that is inside
the noise of the biggest input. No hypothesis test, because a real one needs an error model that does not
exist here, and inventing one would be the same false precision one layer up. The rule can only ever say
*these are not separable* — never that one candidate beats another — so an error makes the menu more
cautious.

Nothing is reordered. A deterministic total order is still worth having; it just should not be read as a
finding. The menu now says so, and says nothing when the spread genuinely resolves.

Two process notes. The reproduce golden's field-by-field diff — the ritual before updating it — showed the
note firing on the canonical **single-candidate** run as *"The top 1 candidates are within the leader's own
uncertainty of each other"*, which is nonsense. It turned out the code was already correct and I was reading
**stale bytecode** left behind by restoring a mutated file, which also cost a CI cycle and a fruitless hunt
for a logic bug: `inspect.getsource` showed the right source, the AST parsed right, and Python ran the
mutant. Clearing `__pycache__` after a mutation loop is now written into `project.md`. The single-candidate
case has its own test regardless, separate from the quiet-when-sharp case, so neither can mask the other.

**Lesson: when a system computes uncertainty, check whether its own *presentation* respects it. The
intervals were honest everywhere they were displayed and ignored where the tool spoke with the most
authority — the ordering itself. Look for the places the product asserts a difference, and ask whether the
difference clears the error bar the product itself published.**

## Round 100 — the guide off-targeting itself

Still reading output rather than code. This time the cohort surface, which nothing in this session had
looked at. One row said:

```
"worst_offtarget": 1.0,
"best_specificity": 1.0,
```

Both numbers correct, side by side, and contradictory. Two bugs behind them, one of them the worst thing
found in this whole stretch.

**The real one.** `worst_offtarget = 1.0` meant some candidate had a *perfect* off-target site. Chasing it:
170 of 470 candidates, and the site was the guide's own locus, reported at `chr11:2019-2038(-)` against a
placement of `chr11:2018-2038(-)`. A 20-nt spacer aligning to its own protospacer through one RNA bulge —
zero mismatches, score 1.0, one base short. `_is_on_target` matched the placement exactly, so it sailed
through.

The consequence is the exact failure that function's docstring describes and exists to prevent: worst-case
score pegged at 1.0, specificity halved to 0.5, the safety axis inert — for a third of every prime menu. The
exactness was a deliberate choice, and a correct one, for the reason the docstring gives (a paralog abutting
the on-target must survive). It just had no answer for the same locus arriving at a *different interval*,
which only bulges make possible.

The fix is containment in the placement grown by the hit's own bulge budget. It subsumes the exact case
rather than special-casing it — an un-bulged hit has zero slack, and a full-length window contained in the
placement *is* the placement — so the separate zero-bulge branch was deleted as a branch nothing could
distinguish, which the mutation run had already shown by surviving its removal.

**The presentational one.** `worst_offtarget` was a max over the whole menu while `best_specificity` came
from the top candidate. Two facts about different reagents, adjacent, in the column a reader scans to triage
hundreds of variants. Both are now the recommended candidate's.

Two notes on the tests. The first pair I wrote were **vacuous** — both mutants passed — because a synthetic
fixture does not reliably admit a bulged self-alignment. The genomic window in the test is now lifted
verbatim from the reproduction, with an assertion that the fixture still produces a bulged self-match, so
the test fails loudly if it ever stops testing anything. And the containment predicate's other direction —
not swallowing a *distant* bulged off-target — cannot be reached end to end, so it is exercised directly on
synthetic hits. All three surviving branches now fail under mutation.

**Lesson: an exact-match guard against a known-bad case is only as good as the enumeration of ways that case
can present itself. `_is_on_target` asked "is this hit at the guide's coordinates?" when the question is "is
this hit the guide?" — and the moment the aligner gained bulges, those stopped being the same question, in a
function whose own docstring explains why getting it wrong is dangerous. When a feature widens what an
identifier can look like, revisit every equality test on that identifier.**

## Round 101 — the row that could not be read

Reading output again. After R100 the standalone `offtarget` command still showed something odd on the same
guide:

```
chr11:2019-2038(-)  mm=0  score=1.0
chr11:2018-2038(-)  mm=0  score=1.0
```

Two sites, overlapping by 19 of 20 bases, both perfect. The obvious reading is double-counting — one
physical locus reported twice, inflating the site count and depressing the specificity aggregate from 0.5
to 0.333 — and the obvious fix is to merge them.

That reading was wrong, and the round is mostly about how I found out. `OffTargetSite` records the locus,
the mismatch and bulge counts, the score, the matrix, the origin, the causal allele, the populations, the
frequencies — and not **which PAM anchored it**. So there was no way to tell, from the report, whether
those two rows were one site printed twice or two real cut registers.

They are two real registers: `AGG` and `GGG`, one base apart. Merging them would have silently deleted a
genuine off-target from the count of a safety-critical report, on the strength of a plausible-looking
duplicate.

**Shipped:** `pam_sequence` on the site, printed on each CLI row and in the JSON payload. It also closes a
second gap that had nothing to do with duplicates: the engine has a low-stringency `NAG` path, so a report
can mix canonical and relaxed-PAM sites — very different real risk — and the table showed no difference
between them.

**Not shipped, deliberately:** no merging, no adjusted aggregate. Deciding that two overlapping registers
count as one site is a convention, and I do not have one to cite. Record the fact the reader was missing
and let them decide.

**Lesson: the instinct that finds bugs — "these two rows look like one thing counted twice" — is the same
instinct that breaks working code. The difference is whether the data can settle it, and here it could not,
which was itself the finding. When a suspicious pattern cannot be resolved from what the system records,
the first fix is to record what would resolve it, not to act on the guess. It would have been a quiet,
plausible, safety-critical mistake.**

## Round 102 — the export nobody reads out loud

Still reading output, now the machine-readable kind. The TSV a pipeline consumes had sixteen columns, and
exactly one about off-target risk: `n_offtarget_sites`.

Everything the last several rounds established about that number — that it is meaningless without the
cut-offs (R84), that the aggregate and the scoring basis belong beside it (R86), that hazard flags are not
decoration (R98) — had been applied to the HTML page and the PDF leave-behind and to neither export format.
A row reading `n_offtarget_sites = 0` said nothing about how hard anyone had looked.

The asymmetry is backwards from where the risk actually is. A human reading the HTML at least sees the
`0` in a page full of qualifications and can go looking. A pipeline reading the TSV filters on the column
and moves on; there is nobody to notice the number is unqualified, and nobody to ask. **The export is where
missing context does the most damage, and it was the surface that got it last.**

**Shipped:** `offtarget_specificity`, `offtarget_scorer`, `offtarget_matrix`, `offtarget_search`, `caveats`
and `rationale` columns, with the export schema version bumped from 2 to 3 — which is what that field is
for, and the test asserts the row's `schema_version` cell matches the constant so a consumer can branch
before parsing. `caveats` is the hazard subset of `flags` so a downstream filter does not have to
hard-code which flag names are hazards, a list that has grown twice this month.

**Lesson: when a fix is applied to "the renders", ask which renders — and remember the ones with no reader
to complain. Human-facing surfaces get fixed first because someone eventually squints at them; the JSON,
the TSV, the API response are consumed by code that never squints. Rank the surfaces by *who would notice
the omission*, and do the silent ones first, not last.**

## Round 103 — the principle the busiest surface did not follow

The R102 lesson was to rank surfaces by *who would notice the omission*. By that ranking the cohort summary
is the worst place in the system for an unqualified number, and it had one:

```
chr11:2001:A>T  ok  best=prime  eff=0.61  n=470
```

A bare point estimate, on the surface whose entire purpose is scanning hundreds of rows to decide which
variants deserve a closer look. The README's own quickstart says, in a comment: *"Every numeric prediction
carries a calibrated interval, never a bare float."* Every other render honours it. This one printed `0.61`
for a prediction whose interval is `[0.46, 0.76]` and for an out-of-distribution guess alike, with nothing
to tell them apart — and triage is exactly when a reader takes a number at face value, because looking
closer is the thing they are deciding whether to do.

**Shipped:** `eff=0.61 [0.46,0.76]`, an `OOD` marker, and the recommended candidate's hazards as
`!close-nick` on the human line; `best_efficiency_low`, `best_efficiency_high`,
`best_efficiency_in_distribution` and `best_caveats` on the machine-readable row and the summary TSV. An
empty menu still reports `None` rather than a reassuring zero — the R56 distinction, preserved.

**Lesson: a stated principle is worth grepping as a specification. "Never a bare float" is a testable claim
about every surface, and it had been kept everywhere someone would read carefully and broken where they
would not. The places a principle is *most* load-bearing are the summaries, the dashboards and the triage
views — the ones written to be skimmed — and those are exactly the ones that get built with the short
version of the number.**

## Round 104 — the principles, read as claims

R103 ended on "a stated principle is worth grepping as a specification". The README has eight of them, so
this round tested all eight.

**Principle 3 was an overclaim.** *"AlleleForge searches population variation by default."* It does not.
Without `--gnomad`, `--haplotypes` or `--patient-vcf` the scan is reference-only, because the project
vendors no gnomAD data. Every surface already says this — R75 added the explicit reference-only warning, and
the README's own CLI section spells it out: *"`--gnomad` is what makes the off-target scan
population-aware"*. So the document contradicted itself, with the false version in the headline and the
true version three sections down where fewer people read.

This is the worst place in the project to overclaim. Population-aware off-target search is the
differentiator, the Casgevy / BCL11A cautionary tale is quoted right there in the same principle, and the
whole point of quoting it is that a reference-only scan looks clean when it is not. A reader who takes
"by default" at face value is making exactly the mistake the principle warns about.

**Principle 8 was false at the edges.** *"Every dataset... carries a literature citation."* A user's own
gnomAD slice or patient VCF has none, and provenance recorded `citation: null` for it. The guarantee that is
real — and worth stating — is that everything in the *registries* is cited and versioned, and a
user-supplied input is pinned by content hash instead: recorded, not attributed.

**Shipped:** both principles rewritten to what is true, the same overclaim fixed in `docs/index.md`, and
`tests/test_stated_principles.py` — the citation-and-version guarantee asserted over both registries, and
the specific "by default" phrasings guarded. That test also asserts the honest wording is still *present*,
so it cannot be satisfied by deleting the claim instead of correcting it, which is the obvious way to make a
prose test pass and the wrong one.

**Lesson: a project's principles are the least-tested and most-quoted text it has, and they drift in one
direction — toward the version that sounds better. The tell is a contradiction *inside the same document*:
the honest description usually already exists, further down, written by someone who was looking at the code
at the time. When the headline and the manual disagree, the manual is right.**

## Round 105 — the chemistry I had not run

Every round since R98 has read output from the *prime* path, because that is what the test variant routes
to. So this round ran a base-editor correction instead and read its card. Two findings, and the second is
about my own machinery.

**The spacer caveats were prime-only.** The top-ranked candidate — `recommended`, Pareto-optimal — held a
spacer of 5% GC and was reported `clean`. `gc-out-of-band` and `no-5prime-g` were computed in
`design/prime.py::_flags` and nowhere else, so an identical spacer was a caveat inside a pegRNA and
unremarked inside an ABE sgRNA. Nothing about U6 transcription or oligo synthesis cares which chemistry
holds the spacer. They are now one shared `spacer_quality.py` that all three verticals call, and the
reproduce golden moved by exactly two flags — the canonical scenario's own ABE candidate has a 10% GC spacer
that had gone unflagged since it was written.

**The guard was under-covering itself.** R98's check reads every `flags.append(...)` literal out of the
source and fails on an unclassified flag. The base-editor vertical attaches `recommended` through
`model_copy(update={"flags": ...})`, which that scan never saw — so the guard reported complete coverage
while a flag had never been classified. The mechanism built to stop a hazard being missed was missing one,
for the same reason the original bug happened: it enumerated *one* way the thing is done.

What saved it was the guard's second half — "every classified flag must actually be emitted" — which fails
when the scan is narrowed, so the two halves keep each other honest. That was written as an
anti-rot measure and turned out to be the anti-blindness one.

**Lesson: exercise every branch of the product, not every branch of the code. Coverage was green on the
base-editor path the whole time; what was missing was never having *looked at* its output, and one
chemistry of three had a caveat the others had. And when a guard enumerates how something is done — call
sites, literals, patterns — assume the enumeration is incomplete and give the guard a second, differently
shaped assertion that fails when the first goes blind.**

## Round 106 — the table that looked like a bug

Continuing R105's method — run the chemistry you have not run — this round designed a **knock-out**, the
nuclease path, and read its card:

```
P(intended) = 0.87
  del5:mh3@17   0.069  ✓
  del2:mh1@18   0.060  ✓
  del5:mh2@18   0.055  ✓
```

A reader checks 0.069 + 0.060 + 0.055 = 0.18 against a headline of 0.87 and concludes something is broken.
Nothing is: `P(intended)` sums every frameshifting allele across a forty-six-allele NHEJ spectrum, and the
table shows the top three. But the page gave no way to know that, and the failure mode is worse than a
missing qualification — it actively looks like an arithmetic error, which costs trust on a report whose
entire value is being believable.

The project already had the right idiom. The candidate list says *"Showing 50 of 470: the top 50 by rank
plus every Pareto-front candidate. The remaining 420 are in the lossless JSON/CSV export."* The outcome
table needed exactly that sentence and did not have it.

**Shipped:** `n_outcome_alleles` and `outcome_shown_mass` on the candidate report, and *"showing 3 of 46
predicted alleles (0.18 of the probability mass)"* in HTML and PDF. Reporting the **mass**, not just the
count, is the part that closes the arithmetic: it says where the missing 0.69 went. A complete table adds
nothing, so the note means something when it appears.

**Lesson: look for numbers that appear together, not just numbers that appear alone. Nine rounds of this
audit have asked "is this figure qualified?" — this one came from asking "do these two figures, side by
side, tell a consistent story?" A truncation that is invisible is a missing qualification; a truncation
next to a total computed over the whole distribution reads as a mistake, and readers who spot mistakes stop
trusting the rest of the page.**

## Round 107 — the surface with the least technical audience

R105's rule again: run the part of the product you have not run. This round drove the **web API** and read
the served SPA.

The API itself came back clean — the design endpoint returns the full report, so every field added in the
last twenty rounds reaches a client automatically, and the SPA embeds the *server-rendered* HTML report in
an iframe, which means caveats, model limitations and search settings all arrive without the frontend
knowing anything about them. That is a good design and it held.

The cohort tab did not. It builds its own table from the batch JSON, and it had both problems:

**A bare estimate, again.** R103 fixed exactly this on the CLI line and in the machine-readable row, and I
did not follow it into the browser. The interval, the OOD flag and the hazards were all sitting in the
response; the table printed `0.61`. This is the triage view for the audience the web UI exists for — the
README says "users who will not touch a terminal" — so it is the surface where a lone number is most likely
to be believed, and it was the last one to get the guarantee.

**An XSS hole.** `item_id` is a raw line from the pasted variant list, `error` is an exception message
quoting it back, and both were interpolated straight into `innerHTML`. A list containing
`<img src=x onerror=…>` executed. Not something I went looking for — it surfaced because writing the caveats
column meant reading the row builder closely enough to notice what else was in it.

**Shipped:** interval, `OOD` marker and a caveats column on the browser table; escaping on every value it
inserts. Both pinned by structural tests against the served `app.js` and mutation-checked.

**Lesson: a fix is not done at the layer where it was found. R103's "never a bare float" landed on two of
three surfaces and I logged it as complete, because the third was written in a different language and
reached by a different route. Ask which *other* renderers exist for the same data — including the ones that
are not Python — before closing a presentation fix. And read the untouched lines around the ones you are
changing: the injection had been there the whole time and no query would have found it.**

## Round 108 — the renderer that teaches

R107 ended on "ask which other renderers exist for the same data". One more does: the example notebooks.
They are not tests and not quite docs — they are the thing a user copies into their own script, which makes
them the highest-leverage renderer in the repository and the one nobody audits.

`03_batch_vcf.ipynb` built a cohort table, and it had both halves of the problem:

```python
"best_eff": round(s.get("best_efficiency") or float("nan"), 2),
```

A bare point estimate — the exact omission fixed on the CLI two rounds ago and in the browser one round
ago — and, in the same expression, `or` as a default. `or` fires on any falsy value, so a genuine
efficiency of **exactly 0.0** renders as `NaN`. This notebook has already shipped one bug of that shape (a
`.get` default that never fired because the key existed with value `None`, R61), which makes it two
falsy-default bugs in one file.

**Shipped:** the table now renders `0.59 [0.16,1.00]`, marks `OOD`, carries a caveats column, and checks
`None` explicitly. Running it immediately showed something the old table could not: the example's own
candidates carry `gc-out-of-band:0.10`, the caveat R105 extended to every chemistry.

Plus a guard: an example that renders `best_efficiency` must render its interval, and no notebook may
default a summary field with `or`. Both mutation-checked — and the first attempt at the mutation silently
did nothing, because a notebook is JSON and the source line is escaped inside it. Mutating through
`json.loads` rather than text substitution is the only way to test a notebook guard honestly.

**Lesson: documentation that executes is still documentation, and an example is a *recommendation*. Every
presentation rule this audit has established — the interval travels with the estimate, a zero is not a
default, a hazard is not decoration — applies to the notebooks with more force than to the product, because
a user copies the example and then owns the copy.**

## Round 109 — the check that did not check

Two queries this round. The first — sweep the source for `x or <default>`, the falsy-default shape that had
just produced two bugs in one notebook — came back essentially clean: sixteen hits, all on dicts, lists and
objects where the empty case and the absent case mean the same thing. Worth recording as a negative result
rather than forcing a finding out of it.

The second was R105's rule again: run the command you have not run. `aforge verify` — the command I
*documented* in R96 without ever executing.

```
$ aforge verify result.json
provenance: aforge 0.1.0.dev0, seed 20240501, 2 model(s), 0 dataset(s)
verified: provenance is complete and consistent
```

with `"checkpoint_checks": []`. Nothing was hashed. Re-hashing requires `--cache-dir`, and without it the
command checks that provenance is *complete* — that it names its models and datasets and carries a seed —
and nothing at all about whether those artifacts are intact. The word "verified" covers both claims and only
one was tested.

This is the project's own recurring failure — "not measured" printed as "clean" — landing on the command
whose entire purpose is checking, and it is worse here than at any of the surfaces where I have found it
before. A user runs `verify` *because* they want the integrity claim. Green output is the answer they were
looking for, which is exactly when nobody reads the field list.

**Shipped:** the human output states that no bytes were re-hashed and how to make it happen, and states it
again in the sharper case where `--cache-dir` *was* given and every artifact turned out unpinned, uncached
or of unknown layout — the flag was passed and still nothing was established, which is the version most
likely to fool someone who thought they had done it right. `artifact_verification_run` and
`artifacts_rehashed` in the JSON; the README row corrected to say the two claims are separate.

**Lesson: documenting a command is not running it. I wrote the README row for `verify` thirteen rounds ago
from its help text and its source, and both describe what it does when given `--cache-dir` — which is the
interesting path, so it is the one the prose describes and the one the author has in mind. The default
invocation is the one every user types first, and nobody had looked at what it prints.**

## Round 110 — permission is not presence

R109's rule: run the command's *default* invocation. So this round ran the rest of them — `resolve`,
`data list`, `bench list` — and read what they print.

`aforge data list`:

```
gnomad    v4.1    CC0-1.0    vendored
```

No gnomAD data ships with AlleleForge. The column was rendering `redistributable`, which is a **licence
permission** — the project *may* redistribute this — under the word **vendored**, which is a claim about
what is on your disk. Every CC0 and public-domain source therefore read as bundled.

The consequence is specific and bad. Six rounds ago (R104) I corrected the README for claiming
population-aware search "by default"; the same misunderstanding was being printed by the command a user runs
to find out what data they have. Someone checking whether they need a gnomAD file was told they already had
one.

The fix had a trap in it. Splitting into "may redistribute" and "cached" made every row read
`not cached` — including `doench-2016-cfd`, whose bytes genuinely **do** ship, inside the package as
`offtarget/cfd_matrix.json`, loaded from there and never from the cache. Reporting the one real vendored
dataset as absent is the same error pointing the other way. `DatasetDescriptor` gains `bundled`, true for
exactly that entry, and the table now answers the question a user is actually asking: *can a run use this
today?*

**Lesson: when a boolean's name and its rendered label are different words, check that they mean the same
thing. `redistributable` → "vendored" reads as a reasonable shortening and is a change of claim — from what
is permitted to what exists. And when correcting an overclaim, check the correction does not create the
mirror-image understatement: the fix that makes seven rows honest made the eighth row lie.**

## Round 111 — the number that measured nothing

The last command I had never run:

```
$ aforge bench run cas9-efficiency
cas9-efficiency @ v1: spearman=0.0000, ece=0.2000 (n=10, model=crispr-bench-baseline)
```

Three things are wrong with that line and only one of them is obvious. `n=10` is a sample size on which a
Spearman correlation means very little. `spearman=0.0000` gives no way to tell a deliberately weak baseline
from a broken pipeline. And the third, which the first two are symptoms of: **the dataset is synthetic**.

`rs3-validation` is a stand-in shipped so the harness runs in CI without the real corpora, and it says so —
`BenchmarkDataset.synthetic`, one of the fields on the R90 no-readers list, which I had passed over as
plumbing. Nothing read it. So a metric over ten fabricated rows was printed in exactly the format a
GUIDE-seq result would be, on the component the project describes as "a calibration-first benchmark". Of
every unlabelled number this audit has found, this is the one whose label matters most.

**Shipped:** `dataset_is_synthetic` on `BenchmarkResult`, a note under the `bench run` line saying the
number measures the contract and not the model, and a **(synthetic)** mark on the leaderboard in both
renders, so a board cannot rank a stand-in against a real result silently.

The placement is the deliberate part. The flag goes in the **scientific body** — the part the
reproducibility digest covers — not the provenance. Which corpus a metric came from is as scientific as
which split: two runs that differ only in whether the data was real are not the same result and must not
share a digest. That also forced a result-schema bump, which is what the field is for.

**Lesson: sweep results are not conclusions. The R90 field sweep listed `BenchmarkDataset.synthetic` twenty
rounds ago and I filed it as plumbing without asking what it was *for*. A field named after a property of
the data is worth chasing even when its module looks like infrastructure — and "which command have I still
not run?" found in one line what "which field has no reader?" had already surfaced and I had dismissed.**

## Round 112 — the mechanism with no consumer

R111's lesson was that a sweep result is not a conclusion: `BenchmarkDataset.synthetic` sat on the R90
no-readers list for twenty rounds because I filed it as plumbing. So I went back to that list and asked, of
each remaining entry, *what was this for?*

`BenchmarkResult.reproducibility_digest`. Computed on every run. Stored on every result. Read by nothing.

Its own docstring states the purpose precisely: a digest over the scientific body only, stable across
releases and platforms, "so a second lab's re-derivation matches — which the timestamp-sealing signature
cannot show". Every word of that is a promise about an operation — *compare two results* — that did not
exist anywhere in the codebase. The digest was a fact nobody could use.

Worse, and less obvious: there was no `verify_reproducibility_digest()` beside `verify_signature()`. Nothing
ever recomputed the digest from the body it accompanies. A runner bug producing wrong digests would have
shipped wrong digests in every result, and the signature would have kept passing — it covers the digest as
one more field, so it certifies that the wrong value was not *edited*, never that it was right.

**Shipped:** `scientific_body()`, `verify_reproducibility_digest()`, `agrees_with()`, and
`aforge bench compare a.json b.json`. It re-derives both digests before comparing them, and when results
differ it names the differing fields instead of leaving a user to diff two JSON files. The tests show the
thing the mechanism was built for: two runs at different wall clocks agree while their signatures differ,
and a re-signed result with one altered number passes the signature check and fails the digest.

One structural note: the runner builds the scientific body from raw inputs and cannot call
`scientific_body()`, because at that point no result exists and the digest is one of the fields being
signed. Two constructions, pinned equivalent by a test that runs a real benchmark and asserts the recomputed
digest matches — it fails the moment either side gains or loses a field.

**Lesson: for every stored value, ask who *reads* it — but for a value whose name is a promise (a digest, a
signature, a checksum), ask the sharper question: what operation would use this, and does that operation
exist? A verifier with no verify function is not a weak guarantee, it is no guarantee, and it looks
identical to a working one from the inside.**

## Round 113 — the same number, one surface later

R111 labelled the synthetic-derived numbers on `bench run`, the signed result, and the leaderboard. The
obvious next question — R107's — is which *other* surface renders them, and there is one:
`scripts/calibration_study.py`, which the README names as the thing that "regenerates the per-task-ECE +
gap + recalibration report".

That report opened:

```
| Task            | Kind       | Primary  | Value | ECE |
| cas9-efficiency | regression | spearman | 0.0   | 0.2 |
```

Ten rows of a synthetic stand-in, presented with neither the sample size nor the corpus. It is the artifact
someone looking for evidence of the calibration story would open, and the one they would quote.

The preprint *does* say the fixtures are synthetic, in prose, in a section about the benchmark's design.
That is the trap: the fact was written down, in a document that also contains the numbers, so it feels
covered. But the generated report is a separate file that travels on its own — into a screenshot, an issue,
a slide — and a caveat two documents away does not travel with it.

**Shipped:** a block quote at the top of the generated report, before any table, saying every number below
comes from synthetic stand-ins at single-digit sample sizes, demonstrates the measurement machinery, and is
not a measurement of any model. Plus per-row `n` and a `synthetic`/`real` column — the row label matters
because when a real corpus does arrive it must look *different*, not silently occupy the same cells.

**Lesson: a caveat has to live in the artifact that travels, not in the document that explains the
artifact. "It's documented" is a claim about a corpus of text; the thing a reader ends up holding is one
file out of it. For anything generated — a report, an export, a figure — ask what it says when it is the
only thing in the room.**

## Round 114 — the artifact that travels furthest

R113's lesson: a caveat has to live in the artifact that travels. Asked which artifact travels *furthest*,
the answer is a figure. A report gets read once; an SVG ends up in a slide, an issue thread, a paper.

All four committed figures plot fixture data. None said so.

The per-task ECE chart is the sharp one. Its subtitle read *"Expected calibration error per task on the
frozen weight-free splits. Dashed: the flag threshold"* — and it draws a real threshold line across bars
computed from eight to twelve synthetic rows. The threshold is meaningful; the bars are not; the picture
puts them on the same axis. That is a stronger claim than any of the prose I have corrected in the last
thirty rounds, because a chart with a reference line reads as a measurement by construction.

The reference-bias figure needed a different caveat, and finding it was the useful part. It is the project's
headline demonstration — reference-only finds nothing, population-aware finds a CFD-1.0 site at 10.5% AFR
frequency — and it is built on a **constructed** locus "in the style of" rs114518452, with the frequency
supplied to it rather than measured. The mechanism it demonstrates is real and the numbers on the bars are
inputs. The subtitle now says which is which.

**Shipped:** data provenance in every figure's subtitle, conditional on the rows actually being synthetic so
it vanishes when a real corpus arrives rather than becoming permanent furniture. Both mutation-checked, and
the committed SVGs regenerated — a pre-existing freshness test caught that I had changed the renderer
without re-rendering, which is exactly its job.

**Lesson: rank a project's artifacts by how far they travel from their explanation, and caveat them in that
order. Prose keeps its context; a table loses some; a *chart* loses all of it and gains authority on the way
out. And when a figure draws a reference line, check that everything it crosses is on the same footing as
the line.**

## Round 115 — how much of the genome was actually looked at

A different query this round: feed the product the inputs a real genome actually contains, rather than the
tidy ones the fixtures use. Soft-masked (lowercase) sequence as UCSC ships it, a contig edge, CRLF line
endings, IUPAC ambiguity codes, assembly gaps.

Four of five were handled correctly and are worth recording as a negative result — soft-masking in
particular, since a repeat-masked hg38 would otherwise have silently failed to match in exactly the regions
where off-targets live.

The fifth was not a crash but a silence. A scan over a contig that is 99.1% `N`:

```
1 site(s), worst score 1.000, specificity 0.500
```

Identical in shape to a scan over fully-resolved sequence. Windows containing a gap or an ambiguity code
cannot be scanned at all, so the search examined roughly forty bases out of four thousand and said nothing
about it. Restrict a real search to a region overlapping a centromere, a scaffold gap or a segmental
duplication and "0 off-target sites" is a statement about almost nothing.

This is the R83 rule reaching its natural limit: I have spent many rounds recording the *settings* that
narrowed a search, and never asked whether the **sequence itself** did. A parameter is not the only thing
that can shrink what was examined.

**Shipped:** `searched_bases` and `resolved_bases` on the report, and *"only 1% of the 4,038 requested bases
were searchable (the rest are assembly gaps or ambiguity codes)"* in the search description whenever the
fraction is below 99%. Under that, nothing — a scattered ambiguity code is not news, and a caveat on every
report is furniture. Counted with four `str.count` passes so it costs nothing beside a scan already walking
those bytes. All three branches mutation-checked.

**Lesson: when auditing what narrowed a result, include the *data*, not only the parameters. Everything I
have recorded so far — budgets, cut-offs, regions, populations — is something a caller chose. The reference
genome is an input nobody chose and it silently determines how much of the search was possible. Ask what the
inputs, not the arguments, made unmeasurable.**

## Round 116 — the file that was supplied and did nothing

R115's lesson: ask what the *inputs* made unmeasurable, not only the arguments. The reference genome was one
input; the population frequency file is the other, and it is the one the project's differentiator rests on.

Two ways it can quietly contribute nothing. The first I expected to be a bug and it was not: gnomAD ships
contigs as `1`, `2`, …; UCSC references use `chr1`, `chr2`. Mixing them is the single most likely real-world
mistake, and AlleleForge handles it — `canonical_contig` normalizes both sides and the results are
identical. Worth recording as a negative result, along with soft-masked sequence from R115: two plausible
silent failures that are genuinely closed.

The second is open. A gnomAD file covering only chromosome 1, used for a search on chromosome 11, produces:

```
1 site(s), worst score 1.000, specificity 0.500
ancestry_stratification: {}
```

Exactly what a reference-only scan produces. The user passed `--gnomad` and `--populations afr,nfe`, so the
missing-source warning stays silent, and the empty ancestry breakdown — which that warning exists to
explain — is left to speak for itself. This is the more dangerous of the two cases: nothing is missing, so
nothing prompts a second look. A per-chromosome download, a region subset, a filtered slice all reach it.

**Shipped:** `sources_considered`, a mapping from each **supplied** source to how many of its entries fell
in the searched region — key absent means "not supplied", `0` means "supplied and covered nothing here" —
and a description that explains the empty breakdown. It covers gnomAD, haplotype panels and patient VCFs
together, because a panel for another locus is exactly as inert as a frequency file for another locus, and
my first pass had checked only gnomAD: the very shape this round is about. A mapping rather than a field per
source, since the set of sources grows and one of them silently missing the check is how the gap arose.

Two notes on the fix itself. It began as a single `population_variants` counter and only reached the other
two sources when I asked, out of habit by now, "which siblings did I just skip?" — the answer was two of
three. And my first version counted with `population_variants = (population_variants or 0) + len(variants)`,
which the mutation run caught: removing the initializer changed nothing, because the `or` recreated it. That
is the falsy-default pattern I had swept the codebase for seven rounds earlier, written by me, in the code
whose entire purpose is keeping `None` and `0` distinct.

**Lesson: "the input is present" is not "the input applies". A supplied-and-inert dependency is worse than a
missing one, because absence prompts a question and presence closes it. Check coverage, not configuration.**

## Round 118 — the third sibling

*Numbering note (added in R146): there is no Round 117. The work this entry and R121 attribute to "R117" —
`sources_considered`, and the "which siblings did I just skip?" habit — is logged under **Round 116**, whose
entry covers both of that round's commits. The number was skipped, not the work.*


R117 ended on a habit worth keeping: after fixing something, ask *which siblings did I just skip?* Two
rounds ago that question turned a gnomAD-only coverage check into one covering haplotype panels and patient
VCFs. Asked again, one supplied input still had no coverage check: the **chromatin track**.

The per-candidate code turned out to be the good example. It computes the accessibility signal, and:

```python
# An uncovered locus (signal 0) is a no-op in the scorer, so only note an
# adjustment that actually moved the estimate — never claim chromatin
# evidence where the track had none.
```

Exactly right, written long before this audit. So the gap is one level up. R83 added `chromatin_track` to
the provenance config snapshot — correctly, since it changes every efficiency in the menu — which means a
run with a track covering nothing now *records* a chromatin-aware configuration while producing entirely
unadjusted numbers. The per-candidate honesty was in place and the artifact still overclaimed.

**Shipped:** a menu note when a supplied track adjusts no candidate, and a `chromatin-adjusted` flag on the
ones it did move — that fact previously existed only as prose inside a candidate's rationale, so nothing
could count it, including the check I needed to write.

One more thing the round produced. My first version attached the new flag with tuple concatenation at the
construction site, and the R98 classification guard failed — not on the "is it classified?" half, but on the
"is a classified flag actually emitted?" half, because the guard reads `flags.append` literals out of the
source and a third attachment shape was invisible to it. That is the second time a novel construction has
slipped past that scan (R105 was the first, via `model_copy`). The fix this time was not another regex: the
flag now goes through `_flags()` like every other one, and the docstring says why that uniformity is
load-bearing. **Widening a guard to accept more shapes is the worse repair; making the code have fewer
shapes is the better one.**

**Lesson: a careful local decision can still produce a misleading global artifact, and adding provenance can
*create* the gap rather than close it. Recording an input in the config snapshot asserts it was used;
whether it did anything is a separate fact, and only the second one is what the reader takes away. When you
record that an input was supplied, record whether it applied.**

## Round 119 — the ancestry that was asked about and never looked at

R118's rule: when you record that an input was supplied, record whether it applied. Run over the provenance
config snapshot, one entry stands out — `populations`, the list of ancestries to stratify by, which is the
project's differentiator expressed as a parameter.

Request `--populations afr,sas,eas` against a frequency file whose records carry `afr` and `nfe` columns.
`afr` is used. `sas` and `eas` contribute nothing and are dropped without a word, while the snapshot records
all three as considered.

The failure is precisely the one the whole population-aware apparatus exists to prevent. An ancestry missing
from the breakdown reads as *no risk found in that population*; here it means *nobody looked*. That is the
BCL11A cautionary tale in miniature — the harm in a reference-only scan is not that it is wrong, it is that
it is silent in exactly the populations that are under-represented in the data, which are the same
populations a user is most likely to name explicitly and least likely to have coverage for.

Three cases now distinguished, where before there were two:

| | |
|---|---|
| no source supplied at all | the reference-only warning (existing) |
| a source supplied that covers no part of the region | `sources_considered` (two rounds ago) |
| a source supplied that has no column for a requested ancestry | `unbacked_populations` (this round) |

**Shipped:** `GnomadDB.available_populations`, an `unbacked_populations` field checked across every supplied
source — a haplotype panel backs its own ancestries — and a line in the search description naming them. It
stays empty when no source was supplied, because that case already has a warning and two warnings for one
situation is worse than one. All three branches mutation-checked.

**Lesson: the finest-grained version of "was this input used?" is per *value*, not per input. A list-valued
parameter can be half-applied, and the half that was dropped is invisible precisely because the other half
worked. When a parameter names things — ancestries, tracks, chemistries, regions — check each name, not the
list.**

## Round 120 — the panel for the wrong genome

R119's rule: when a parameter names things, check each name. Ancestries were one list; **regions** are the
other, and a region panel is the most likely of all to be wrong, because it is usually a file somebody else
made.

A BED naming `chr99` against a reference that has no such contig produced a Python traceback. The CLI
catches `ValueError` around the search; a missing contig raises `KeyError` from inside the fetch, and
nothing caught that. Not a subtle failure — but the ordinary cause is a panel built against a different
assembly or naming convention, which is a thing a user does routinely and needs a sentence about, not a
stack trace.

The interesting part was deciding what *else* to refuse, and getting it wrong first. My first version also
refused a region starting past a contig end. That broke an existing test which used exactly such a region on
purpose — to scope a search to nothing and check the scoping worked. The test was right and I was wrong:
a region past the end is valid scoping, and R115's searchable-fraction line already reports it far better
than a refusal does, reading "0% of the 100 requested bases were searchable". So the refusal is narrowed to
the one case no coordinate can rescue — an unknown contig — and the rest is left to the reporting that
already existed.

That same check then found a wording bug in R115's own message: bases past a contig end were being described
as "assembly gaps or ambiguity codes". They are neither; nothing is missing from the assembly there, the
region simply asked for more than the contig has.

**Lesson: before adding a refusal, check whether the system already *reports* the condition — and check the
tests that exercise the case you are about to forbid. A test doing something odd on purpose is documentation
of an intent you are about to break. Refuse only what no reporting can make comprehensible.**

## Round 121 — the same sweep, across the siblings

R117 turned "which siblings did I just skip?" into a habit, and R120 fixed one file input. So this round
fed a *wrong-in-a-realistic-way* file to each of the four: a frequency file, a haplotype panel, a patient
VCF, a chromatin track, all naming a contig the reference does not have.

`--gnomad` came back clean, and pleasingly so: the run completes and reports "supplied but contributing
nothing in this region", which is the mechanism from four rounds ago handling a case I had not written it
for. That is what a general fix looks like from the outside.

The other two failed with tracebacks, for different reasons and needing different answers:

**A haplotype panel with the wrong header** raised a bare `KeyError: 'frequency'`. The fix names the missing
column *and* prints the expected header, because the user's next question after "which column?" is "what
should it be?" and a panel exported from somewhere else is the ordinary cause.

**A real VCF without the optional `genome` extra** raised an uncaught `RuntimeError` whose message was
already excellent — it names the extra and the pip command. Only the presentation was wrong. That one also
wanted a different exit code: `UNAVAILABLE`, not `MISSING_DATA`, because the file is fine and the *feature*
is absent. The CLI already distinguishes those and a script can branch on it; the traceback path could not.

**Lesson: a traceback is a missing decision, and the decision is usually not just "catch it" but *which*
answer it is. Three failures in one sweep wanted three different treatments — refuse with the valid
alternatives, refuse with the expected schema, and report a missing capability — and collapsing them into
one generic handler would have thrown away the useful part.**

## Round 122 — the empty genome that passed

Continuing the input sweep with files that are malformed in *plausible* ways rather than absent ones.

**A frequency column in percent.** `af=1.5`, `afr=2.0` was accepted without complaint. Downstream the MAF
filter admits everything and the ancestry breakdown — the table a person reads to decide whether a guide is
safe in a population — shows 200%. Frequencies are now validated as fractions at the parse boundary, with a
message that names the likely cause, because a scale error that propagates produces a safety number wrong by
100x that looks entirely deliberate.

**And then the one that matters.** Chasing an empty-FASTA traceback, I tried a *header-only* FASTA — a
download that got `>chr1` and stopped. It indexes fine. The scan returns:

```
0 site(s), worst score 0.000, specificity 1.000
```

A perfect safety report, from a genome containing no bases. Every number is arithmetically correct. R115's
searchable-fraction line does not fire, because it takes a fraction of the requested bases and there were
none. This is the purest example of the pattern this entire audit has been about: the *most reassuring
output the system can produce* is what it produces when it has nothing at all.

Two smaller notes on discipline, both from mutation runs. My first fix added a `not reference.contigs` guard
at load time; it is unreachable — a header-only FASTA has a contig — and the mutation proved it, so it is
gone and the condition is reported where it is actually observable. And a narrow `except (OSError,
ValueError, KeyError)` in front of a broad `except Exception` also survived removal: two clauses differing
only in the verb of their message. One handler now.

**Lesson: check what the system says when it has *nothing* — no sequence, no data, no candidates. Systems
are built and tested around having input, and the empty case tends to fall through every guard into the
default, which is silence. Silence reads as success. For anything that reports a risk, the zero-input path
deserves an explicit test, because that is the path where a wrong answer is maximally reassuring.**

## Round 123 — the mismatch that was not one

R122's rule — check what the system says when it has nothing — extended to *degenerate* rather than empty
inputs: a PAM of `NNN`, a one-base spacer, a spacer with an `N`.

The last one:

```
spacer ACGTAACGTTACGTAACGTN: 1 site(s), worst score 0.000, specificity 1.000
```

The site is the guide's own locus, at one mismatch, CFD **0.0**. The CFD matrix has no entry for a non-ACGT
base, so the position is treated as a mismatch, and a mismatch lowers the score. The headline safety number
for that guide is therefore the best one available.

The direction is what makes it a bug rather than a limitation. An unknown base *might match perfectly* — an
ambiguous position is the case where a reader should be **less** sure a guide is safe, and the arithmetic
made them more sure. Everywhere else this project treats an unmeasured thing as unmeasured; here it was
silently treated as measured-and-fine.

What I deliberately did **not** do: change the score. Treating the ambiguous position as a match instead —
the conservative direction — is a convention, and adopting one silently is how the current behaviour arose.
The score stays as computed and the report now names the positions and states which way they bias it, so a
reader can discount the number rather than have it quietly re-derived for them.

Also confirmed sound in the same sweep: a `NNN` PAM (matches everywhere, still runs and scores correctly)
and a one-base spacer (0 sites, and a sub-threshold tail correctly keeping specificity below 1.0).

**Lesson: when a value cannot be computed, check which way the fallback leans. "Unscoreable → 0" is the
natural implementation and, for a score where low means safe, it is a bug that only shows up as
over-confidence. For every default that stands in for a missing measurement, ask whether it reads as good
news, and if it does, say what it actually is.**

## Round 124 — the safety score nobody earned

R123's rule — when a value cannot be computed, check which way the fallback leans — swept across the
codebase's zero-defaults. Most are fine; `p_intended` defaulting to `0.0`, for instance, leans *pessimistic*
for a maximised objective, which is the safe way round.

One did not. `_safety` returns `1.0` when a candidate has no off-target report:

```
score 0.690 [eff 0.45 [0.30, 0.60], clean 0.71, safe 1.00, simple 0.40]
```

A perfect safety mark, weighted 0.30 in the composite, awarded for *not having been screened*.

The function knew. Its docstring read: "A candidate with no off-target report (search skipped) is treated as
fully safe but flagged elsewhere; that absence is surfaced in the candidate's flags." I checked. No vertical
emitted any such flag. The justification was written, plausible, and false — and because it was written, it
would have stopped the next reader from checking, which is what it did to several of my own earlier passes
over this file.

**Shipped:** `offtarget-not-searched` from all three verticals, classified as a hazard so every render lifts
it out of the flat list, and a docstring that says what is true. The arithmetic is unchanged on purpose:
penalising an unmeasured axis means choosing *how much*, and there is no basis for a number here.

The test needed three fixtures. My first version routed only to prime, and the mutation run showed the cas9
and base-editor checks were untested — a check in one vertical leaving two silently reassuring is how most
of the gaps in this audit began, so the test now drives all three.

**Lesson: a docstring that explains why something unsafe-looking is safe is a claim, and it is the least
tested kind of claim in a codebase. It reads as evidence the question was considered, which is precisely why
nobody re-asks it. When a comment says "this is handled elsewhere", go and look at elsewhere.**

## Round 125 — my own regression, and an assumption underneath it

R124's rule — when a comment says "handled elsewhere", go and look — swept the codebase's deferral and
invariant claims. They held. The SVG colour validator really is called on every attribute-bound value; the
API's `on_target` really is model-validated. A clean sweep, recorded as such rather than stretched into a
finding.

So I looked instead at what *I* had added recently, and found a cost. R115's searchable-base count does
`seq.upper()` before counting, once per region. On a whole chromosome that allocates a ~250 MB copy on top
of the sequence already resident — in a path the project describes as bounded-memory — to save, measured,
about 8% of a step that is negligible beside the scan (20 Mb region: 140 ms and +20 MB, versus 151 ms and
zero).

Then the interesting part. Removing the copy, I first wrote the count as case-*sensitive*, reasoning that
`ReferenceGenome.fetch` upper-cases anyway. The mutation run agreed: dropping the lowercase arm broke
nothing. So I deleted it, per the discipline of not leaving branches nothing can distinguish.

That was wrong, and the reason is worth writing down. The normalization does not come from `fetch` — it
comes from `pyfaidx`, constructed with `sequence_always_upper=True`. It is a **dependency default**. "No
test can distinguish this branch" and "this branch cannot be reached" are the same statement only when the
invariant is *yours*. Here, a pyfaidx option change or a different FASTA backend would make every base of a
repeat-masked genome count as unsearchable, and the report would announce that a real scan had covered
almost nothing — the false alarm exactly inverse to the one the count exists to raise. Eight `str.count`
passes instead of four is not a price worth arguing about against that.

One more turn of the same screw. Having written the case-insensitive counter, I tested it with an inline
`sum(lowered.count(base) for base in "ACGTacgt") == 8` — and the mutation run passed, because that test
restates the expression rather than calling the code. Since the reference normalizes case, no end-to-end
fixture can reach the lowercase path either. The counter is now a named function so it can actually be
called; mutating it fails. **A test that reproduces the implementation is not a test, and an inline
expression in a hot loop can be untestable for exactly that reason — extracting it is what makes the
defensive branch defensible.**

**Lesson: audit your own recent changes for cost, not only for correctness — a feature added ten rounds ago
is now legacy nobody is looking at, and I had added a quarter-gigabyte allocation to the hot path without
measuring. And when deleting an "unreachable" branch, ask *whose* invariant makes it unreachable. Deleting
defensive code is right when the guarantee is local and wrong when it belongs to a dependency.**

## Round 126 — the cost of being careful

R125 ended on "audit your own recent changes for cost", having found a 250 MB allocation I added ten rounds
earlier. Run properly over rounds 84–125, that query found two more, both worse.

The last dozen rounds have added a lot of *labelling* to `search()` — which sources covered the region,
which ancestries are backed, how many bases were searchable. Every one of those is cheap in isolation. But
`search()` runs **once per candidate**, and a realistic prime menu has 470 candidates. Anything O(database)
inside it is O(database × candidates) in practice.

`GnomadDB.available_populations`, added six rounds ago to name unbacked ancestries, scans every record on
every call. Over 200,000 records that is 49 ms; times 470 candidates, **23 seconds added to one design** —
and a per-chromosome gnomAD file is an order of magnitude bigger. For a label. It is now computed once; the
database is immutable after construction, so there was never a reason to recompute.

The haplotype and patient coverage counts, added nine rounds ago, re-derived `canonical_contig` for every
(entry, region) pair. On a 2,000-haplotype panel that is 19% of an entire search. Indexing the regions by
contig once takes it to 4%.

Neither was visible in the test suite, because every fixture is small. Both were visible in one minute of
measurement with a realistic-sized input.

**Lesson: honesty features have a cost profile of their own, and it is the opposite of the code they
annotate. A scan is written to run once per genome; a *label* about that scan gets written wherever the
answer is needed, which is per call — and per call means per candidate. When adding an explanation to a
function, ask how often the function runs, not how expensive the explanation looks. And measure at the size
of the real input: a fixture with ten records makes an O(n) scan indistinguishable from a constant.**

## Round 127 — three clean sweeps and a guard

Three queries this round, and the first three came back empty. Worth recording, because "I looked and it
holds" is the result that stops the next pass wasting time:

- The off-target **cache key** covers everything the newer report fields depend on. The fields added over
  the last dozen rounds derive from the spacer, the reference and the regions — all in the key — or from
  sources that make a search cache-ineligible anyway.
- Every **"handled elsewhere"** comment (R124's query) holds: the SVG colour validator really is called on
  every attribute-bound value; the API's `on_target` really is model-validated.
- Every **whitelisted config key** is honored. `populations` — the one I most expected to be dropped — is
  read.

What the third query left behind is worth keeping: the check itself. `_load_config` warns on an *unknown*
key, so a key inside the whitelist gets no warning, and a whitelisted key nothing reads would be accepted
silently and do nothing. The comment beside the run-param handling names that failure precisely. Nothing
tested it, and the contract is exactly the kind that decays when an option is added.

Two tests now hold it: every whitelisted key is read somewhere in the CLI source, and — the half that
matters — a config-only run produces the same candidates, rationale and provenance snapshot as the
equivalent flags.

The first version of the static check reported `run_offtarget` as unread. It is honored, by subscript, in a
helper whose docstring says so; my regex only recognized `cfg.get`. **A guard narrower than the code it
guards accuses working code, which is worse than not guarding** — and I nearly "fixed" a function that was
correct.

**Lesson: when a comment describes a failure mode in order to explain why some code exists, that description
is a test waiting to be written. The code guards the case; nothing guards the code. And a clean sweep is a
result — write it down, so the next pass spends its time somewhere new.**

## Round 128 — reading the same input twice

R126 audited my recent changes for cost. This round audited them for *aliasing*, and found one.

`search(patient_vcf=...)` is typed `Iterable[Variant]`. Two rounds' worth of additions ago I gave it a
second consumer — the region-coverage count — beside the one that was already there, the enumeration that
personalizes the search. A list survives that. A generator does not: the second pass gets an exhausted
iterator.

Which pass loses matters. The count runs first and reports `patient-vcf: 1`; the personalization runs second
and does nothing. So the failure mode is the one this project keeps hunting — **the label says the safety
data was used and the work did not happen** — and it is invisible, because a patient VCF that contributes no
sites is indistinguishable from one that contributes none.

Haplotypes were already materialized at the top of `search` (`haplotype_list = list(haplotypes)`). The
pattern was there; the new consumer did not follow it.

Two turns on the fix itself, both from mutation runs. My first version passed a `Sequence` through
uncopied, justified by preserving the attribute `_PatientVariants` carries — and nothing could tell the
difference, because the *caller* keeps its own object either way, so the justification was empty. Checking
the cost instead: 470 copies of a 10,000-variant list total 10 ms. One branch is worth more than that, so
the special case is gone.

**Lesson: adding a second reader to a parameter is an interface change even when the signature does not
move. `Iterable` is a promise the caller can keep with a generator, and every consumer after the first
breaks it. When a function grows a new use of an existing argument, check the argument's *type*, not just
its value — and if a sibling argument is already materialized, that is the convention telling you why.**

## Round 129 — the same bug, one layer up and worse

R128 fixed a doubly-consumed `Iterable` in `search()` and ended on: when a function grows a new use of an
existing argument, check the argument's *type*. That is a mechanical query, so I ran it — an AST sweep for
parameters annotated `Iterable`/`Iterator` and loaded more than once. Four hits. Three were fine. The fourth
was `design()` itself, reading `haplotypes` and `patient_vcf` four times each: once per vertical, plus
provenance collection.

```
one-shot -> {'base_abe': {haplotypes: 1}, 'prime': {haplotypes: None}}
```

The base editor got the panel. Prime got an exhausted iterator. **One menu, two chemistries, two different
standards of safety screening** — and the candidates are then ranked against each other on a `safety`
objective that means something different for each. Nothing on the page distinguishes them; a reader
comparing an ABE candidate against a pegRNA in that menu is comparing a haplotype-aware result with a
reference-only one.

That is strictly worse than R128's version, where the whole search silently lost the input. A uniform loss
is at least uniform. This one is *selective*, and selective silence in a comparison is the failure mode that
makes a ranking actively wrong rather than merely uninformative.

Worth noting how it was caught. The reproduction reads
`candidate.offtarget.sources_considered` — the field added in R117 to say which sources contributed to a
report. Without it there is no observable difference between "the panel found nothing here" and "the panel
was never read", which is precisely the distinction that field exists to make. A transparency feature paid
for itself as a debugging tool twelve rounds later.

The fix took two goes, and the suite caught the first. Materializing with a plain `list()` **stripped the
provenance descriptor** that `HaplotypePanel` and `_PatientVariants` carry as an attribute — `_collect_
datasets` reads it off those very objects, and the CLI's `_load_haplotypes` docstring warns about exactly
that flattening. Two provenance tests failed and were right to. Converting only a true `Iterator` fixes the
aliasing without touching a re-iterable carrier, and both directions are now pinned by mutation: removing
the conversion loses the second chemistry, and converting unconditionally loses the provenance record.

Which is also the answer to a question R128 left open. There I removed an `isinstance` guard as unjustified,
having checked that the caller kept its own object. That was true *at that call site* and false one layer
up, where `design()` rebinds the name it later hands to `_collect_datasets`. The same guard, in two places,
is dead code in one and load-bearing in the other.

**Lesson: run the mechanical sweep even when you have just fixed the instance you found by hand — the hand
version finds one, the sweep finds the family. And the layer above is usually worse than the layer you
fixed, because a shared resource consumed at a fan-out point fails *asymmetrically*, and asymmetric failures
survive comparison.**

## Round 130 — one layer up again

R129 ended on "the layer above is usually worse". There is one more layer above `design()`: `design_many`,
which forwards `design_kwargs` verbatim to every variant in a cohort and, when `max_workers > 1`, to every
worker thread.

A generator passed there is consumed by the first item. Every later variant is screened without it. In
parallel, *which* variant gets it is a race between threads. Fixing the aliasing inside `design()` — last
round — does nothing for this, because `design()` materializes its own local copy while the exhausted
original is what the next item receives.

The instructive part was that I could not test it. Both mutations passed: removing the fix changed no
assertion I could write, because a cohort summary reports candidate counts, and the haplotype panel does not
move those — it changes off-target *sites*. The difference between "screened against the panel" and "not
screened" was genuinely unobservable from the surface a cohort produces.

So the fix needed a companion. `offtarget_sources` now appears on each cohort row: which safety sources
actually contributed for that variant. That is worth having on its own terms — a cohort row is scanned
across hundreds of variants, and two rows that were screened differently looked identical — and it is what
makes the aliasing bug detectable. With it, the mutation fails.

One mutation still passes, and the reason is worth recording rather than papering over: converting
unconditionally would strip the provenance descriptor these carriers hold, but a cohort keeps summaries and
*discards the per-item menus* that would carry that record, so the loss has no observer here by design. It
is pinned where it is visible, in `design()`.

**Lesson: when a bug is untestable, the missing test is usually a missing *output*. Twice now the fix has
been detectable only because some earlier round had added a field recording what a run actually consumed —
and here the field did not exist yet and had to be added first. If you cannot write the assertion, ask what
the system would have to say for the difference to be visible, and consider whether it should be saying it
anyway.**

## Round 131 — the reference that stopped keeping up

The aliasing family is swept at three layers, so: a different axis. Forty-odd rounds have added public
API — `caveats`, `provenance_lines`, `spacer_quality_flags`, `indistinguishable_leaders`, `bench compare`,
`artifact_download_permitted`. Does any of it appear in the API reference?

Twelve modules had no `:::` directive anywhere in `docs/`. The docs build is silent about this by
construction: mkdocstrings renders what you point it at, and has nothing to say about what you never
mentioned. So the reference falls behind at exactly the rate new modules are added, and nothing complains.

The clearest gap was not one of my additions. **`alleleforge.design.cohort`** — `design_many`, the
cohort-scale batch entry point, with its own README section, its own CLI command and its own example
notebook — has never been in the API reference. A user reading the reference to find how to design a cohort
would not find it.

Eight modules added, four excluded on the record (the CLI and the HTTP surface, documented as commands and
endpoints rather than as functions), and a test that fails on a public module which is neither. Plus a
second test rejecting an exclusion for a module that no longer exists, so the list cannot decay into an
excuse.

**Lesson: a documentation tool that renders on request is a documentation tool that cannot notice absence.
Anything driven by an explicit list — nav entries, `:::` directives, `__all__`, an exclusion set — needs a
check that the list still covers the thing it lists *from*. The build passing means the pages it was told
about are valid, not that the pages exist.**

## Round 132 — the other explicit lists

R131's lesson — anything driven by an explicit list needs a check that the list still covers what it lists
*from* — names its own follow-up. This repository has several such lists. I went through them.

The **mkdocs nav** is complete: every page is listed, every listing has a page. Clean.

Module-level `__all__` turned out to be a non-question: exactly one module of sixty-five defines one, so the
convention here is that *packages* declare their surface and modules do not. Worth knowing before
"fixing" sixty-four modules to match a convention that was never adopted — the R101 trap.

The gap was one level over. Seven public names are not re-exported by their packages, and the two clearest
were declared public elsewhere and simply not honored: `routing.__all__` names `PRIME_MAX_EDIT` and
`PRIME_MAX_TEMPLATED_EDIT`, the README cites both by name, and `alleleforge.design` exports neither.
`alleleforge.data` exports `ClinicalSignificance` and not the `ClinicalAssertion` that carries it. And
`alleleforge.report` — the package for a project whose principle is "the library is the source of truth" —
exported the renderers but none of the pieces a caller needs to write a render of their own.

The rules I settled on are deliberately mechanical, because "what belongs in the public API" is a taste
question and taste does not survive forty rounds. A name in a submodule's `__all__` is a *declaration*, so
the package must honor it. A dotted name the docs cite must resolve. Both are checkable, neither requires a
judgment, and the second catches a cross-reference left pointing at a renamed function.

**Lesson: before enforcing a convention across a codebase, check how widely it is actually followed. One
module in sixty-five defining `__all__` is not sixty-four omissions — it is a different convention, and the
"fix" would have been a large, confident, wrong change. Look at the ratio before writing the sweep.**

## Round 133 — the screen that passed by not looking

Back to running the product: what does a bench user actually order? The oligo payload, and the Golden-Gate
screening behind it, which turns out to be careful work — it checks both strands *and* both junction seams,
because a recognition site can be reconstituted across the overhang/insert boundary.

Then the edge: `_screen_enzyme_site` returns `()` for an enzyme not in its table. Docstring and all — "no
site to screen against". Every shipped scheme is covered, so this never fires in practice. But
`VectorScheme` is a public, exported type, and a caller cloning into their own vector with a different Type
IIS enzyme received an empty warnings list for an insert nobody looked at. On a cloning-lethal hazard,
silence is a pass. It now says `enzyme-not-screened`.

The better finding came from the mutation run. Un-classifying the new flag changed nothing — and chasing
that turned up something about my own machinery. The R98 guard finds candidate flags by scanning for
`flags.append(...)` in the source. `report/oligos.py` fills a local *also called* `flags` with oligo
warnings, a different channel rendered separately. So the guard had been treating oligo warnings as
candidate flags, and `internal-<enzyme>-site` had sat in `CAVEAT_FLAGS` since R98 as a classification that
could never match anything, with the guard's own "every classified flag must be emitted" half satisfied by
the wrong list.

Both misfiled entries are gone, and the guard now scans only `design/`, where candidate flags are built.

**Lesson: a guard that matches on a *name* matches on a coincidence. `flags` is an obvious name for any list
of short strings, and two unrelated channels chose it — so the check silently spanned both and validated
one against the other. When a static check keys on an identifier rather than a type or a call graph, pin
down its scope explicitly, because the language will not.**

## Round 134 — counting two different things

First, the roadmap, since I had not consulted it this session: R0–R5 are all "in progress" and all blocked
on things outside the repository — real model weights, real benchmark corpora, pinned artifact hashes that
require real downloads. Two I could check rather than assume: the whole-genome FM-index (R4) really does
have SA-IS in the native kernel *and* an O(n log²n) prefix-doubling fallback in Python, and the external-tool
adapters (R3) are all present with recorded-fixture tests. Nothing there to do.

So: run a path I have not run. The cohort **resume** — stateful, and the kind of thing that quietly diverges.

Resume itself is sound. An interrupted run picks up exactly the outstanding items, produces results
identical to an uninterrupted run, and leaves a complete manifest. Worth recording as a negative result.

The reporting was not. `skipped` was `len(done)` — the size of the manifest file — while `total` counted
what this run processed. Two numbers about two different populations, printed side by side and inviting
addition. Reusing a manifest with a narrower variant list produced `total: 0, skipped: 5` for a two-item
request, and the human line led with **"cohort: 0 item(s)"** for a resume that had nothing left to do.

`skipped` now counts *requests*, computed lazily as the input stream is consumed so a lazy input stays lazy,
and the header states the requested count so the numbers visibly add up.

A note on the investigation. I briefly believed I had found a much worse bug — a brand-new variant not
designed at all on a resume. It was my own test artifact: an earlier invocation had failed at its *output
parsing* step, long after the design had run and appended to the manifest. Checking that before writing it
up cost two minutes; reporting it would have been wrong in public.

**Lesson: when two counts appear in one summary, check they range over the same population. `total` and
`skipped` were both honest and individually documented, and their juxtaposition was the lie — nothing in
either field's definition is wrong, and no test of either one alone would have caught it.**

## Round 135 — the rank column was the claim

Straight application of R134's lesson: sweep for numbers presented together that were computed over
different populations. The candidate pairs in the benchmark result all checked out — `n_test` and
`n_out_of_distribution` really do range over the same scored examples, and the regression ECE's
count-weighted average has no reachable path where an undefined level dilutes the denominator (the guard
is defensive; groups are built by appending, so none is empty). Recorded as negative results.

The leaderboard was a different story, and it is not a *field* that mixes populations — it is the **rank**.

`rankings()` sorted every entry for a task into one 1-2-3 column regardless of which frozen split it was
measured on, which corpus, or even which metric. Built the board and looked at it: a model scoring 0.91 on
the bundled *synthetic* fixture printed as **rank 1**, above a model scoring 0.42 on a real corpus, with a
third measured on a different split sitting between them. Every cell was honest. The split version was in
its column, the synthetic row carried its `**(synthetic)**` mark. The ordering was the lie, and the module's
own docstring said ranking synthetic against real is "the one thing a leaderboard must not do silently" —
the fix that had been applied was a *label*, and a label does not stop a rank.

Two further consequences of the same root: sort direction and the score column's header both came from
`entries[0]`, so a submission naming a different primary metric for the same task was sorted by another
metric's direction and printed under another metric's name. A submission is externally supplied and
self-hashed, so that is reachable from untrusted input, not hypothetical.

Introduced `ComparisonGroup` — `(primary_metric, split_version, dataset_is_synthetic)`, the population a
score was measured over and the unit a rank is valid within. `comparison_groups(task)` ranks within each and
orders groups real-corpus-first; `rankings()` concatenates them and says in its docstring that position is a
rank only within a group. Both renderers emit one captioned table per group with the count restarting at 1,
and a task spanning more than one gets an explicit "not comparable across groups" note.

**Lesson: an aggregate can be a claim even when it is not a number. Every cell on that board was labelled
and correct, and the labels were added precisely to stop this — but the rank is an assertion of its own, and
no amount of annotating the rows retracts it. When a fix is "we now show X," ask what the surrounding
presentation still asserts on its own.**

## Round 136 — the number a scientist pastes into a browser

Following R135 into other presentations that assert something on their own. The design menu turned out to be
well defended already — out-of-distribution candidates are ranked on their lower interval bound, and the
rationale says outright when the top N are within the leader's own uncertainty of each other — and the
cross-chemistry efficiency axis was made comparable in an earlier round. Negative results, recorded.

Then: coordinate base. AlleleForge is uniformly **0-based half-open**, which is a fine choice and internally
consistent — `GenomicInterval.parse` and `__str__` are exact inverses, so a locus the tool prints can be
handed straight back to it. The defect is that this was never said anywhere a human reads.

Three pieces of evidence. `grep to_one_based` across the whole tree returns **only its own definition**: the
declared I/O-boundary converter has no callers, so no coordinate is ever converted for display. The report
prints `cut 5530600` bare — the single number a scientist is most likely to paste into IGV, which reads the
same digits as 1-based. And on one command line, `--pop-freqs` help says *"1-based pos as in a VCF"* while
`--region` help says only `'chrom:start-end'`; a reader carries the stated base onto the silent neighbour.
`chr7:100-200` searches 100 bases from offset 100. A browser shows 101 for that string.

The fix is labelling, not a semantic change — changing the convention would break the parse/print inverse and
the BED interop, and 0-based half-open is right. Reports state it once in the footer, beside the reference
build the coordinates are against, so it covers every locus in the document rather than repeating beside each
number. `--region` states it and names the contrast with the 1-based options. `docs/data.md` grew the two
human boundaries alongside the file-format ingest table it already had.

**Lesson: a convention that is uniform, correct, and documented in the source can still be a defect at the
boundary, because the reader's default is not the code's default. The tell here was cheap and mechanical —
an exported converter for a boundary, with zero callers, means the boundary is not being crossed. Grep for
unused conversion helpers; each one marks a place where two conventions meet and nobody arbitrated.**

## Round 137 — an instruction the tool would not carry out

R136's tell, run as a sweep: for every `to_*`/`from_*`/`normalize*`/`canonical*`/`convert*` in the tree,
count callers in `src` versus `tests`. Four came back defined-but-called-only-by-tests. `from_gtf` and
`from_build` are library entry points a user is meant to call, so that is the expected shape. `to_one_based`
was R136. The fourth was `Liftover.from_chain_file` — and pulling on it, **nothing in the entire library
constructs a `Liftover` at all**.

Which matters because of where the subject comes up. `resolve` refuses a database record whose native
assembly disagrees with the requested build, and it is right to: relabeling a GRCh37 coordinate as hg38
designs a guide at the wrong place in the genome, and the check was deliberately written to reconcile rather
than overwrite. Its error message ends *"lift the coordinates to hg38 before resolving rather than relabeling
them."* The liftover is implemented, tested against real chain files, correct, and fails closed on a split
interval — and reachable only by writing Python. The README advertises liftover in the genome layer,
`pyliftover` is a declared dependency, and the CLI offered no way to do it. A hard stop whose stated remedy
the tool declines to perform is a dead end for the person it stops.

Added `aforge lift`. It takes loci in exactly the form `--region` accepts and prints them in the same form,
so its output pipes straight back in — the parse/print inverse makes that exact, which is the payoff of the
uniform convention R136 documented. An unmappable locus prints `UNMAPPED` and the run exits non-zero rather
than the locus disappearing from the list: this repo's standing rule is that a smaller search reports fewer
off-targets and reads as safer. The resolver's error now names the command.

**Lesson: a "0 callers in src" converter was R136's tell for an unarbitrated boundary; here the same tell
found an unreachable *capability*. Worth pairing with a second query — grep the error messages for
imperatives ("lift the coordinates", "run X first", "pass --y") and check the tool can actually do each
thing it tells the user to do. An instruction is a promise.**

## Round 138 — the same result, told differently on two surfaces

Started on R137's paired query — check the tool can do what its error messages instruct — and it came back
clean. Every `alleleforge[extra]` named in a message is a real extra, and each one actually contains the
package the message promises (`polars` in `core`, `cyvcf2` and `pyliftover` in `genome`, `lightgbm`/`sglearn`
in `cas9-rs3`). A mechanical check of `--flag` names against the live click tree I could not get to traverse
Typer's subcommands correctly; rather than trust a broken checker I dropped it. Recorded as inconclusive, not
as a clean bill.

So: surface parity instead. The CLI and the web API answer the same question; do they answer it as honestly?

`OffTargetResponse` says, in its own docstring, that it exists to give a client *"the same summary the*
`aforge offtarget` *CLI surfaces."* It projects `n_sites`, `worst_score`, `specificity_score`,
`ancestry_stratification`, `effective_matrix` — every method that returns a **number**. The one method that
returns **prose**, `search_description()`, it did not project, and grep confirms only two callers in the tree:
the CLI and the design report builder.

Constructed the case that matters and printed both:

    CLI says   : up to 4 mismatches, 1 DNA / 1 RNA bulges; … NO SEQUENCE WAS SEARCHED — the reference or
                 region scope yielded no bases, so this is not a clean result, it is an empty one
    API returns: {"n_sites": 0, "worst_score": 0.0, "specificity": 1.0, …}

Same report object. One surface refuses to let the reader mistake an empty run for a clean one; the other
hands over the three most reassuring numbers in the system with nothing attached. The raw fields are all in
the embedded report and a client could in principle reassemble the sentence — no client will, which is the
whole reason the sentence exists.

One field, `search_description`, populated in `from_report`.

**Lesson: when the same result is delivered on two surfaces, the qualifications travel worse than the
numbers. A number is a field and gets projected mechanically; a caveat is usually a method or a rendering
step, and it is dropped by exactly the code whose job is to be equivalent. Diff surfaces by what they omit,
not by what they carry — and treat "gives the same summary as X" in a docstring as a claim to test, since
this one was written by someone who had just enumerated the numeric methods and stopped.**

## Round 139 — the denominator was covered and the numerator was not

First, two negative results. Chasing R138 further, I checked which other qualification helpers reach which
surfaces: `model_limitation_lines` renders only in HTML and PDF, but the JSON and API paths carry the raw
`ModelCheckpoint` fields it formats, so the data travels. And `report_to_tsv`'s `caveats` column joins only
the flag names from `caveats()`, discarding the reason half — which looks exactly like R138 until you read
the test beside it: the column is *deliberately* the hazard subset of `flags`, so a pipeline can filter on
"needs review". A documented, tested design decision, not an oversight. Left alone.

Then: run a command I had not run. `aforge bench compare` — a *comparison* surface, which after R135 is a
category worth suspecting.

Ran it on two results differing in exactly one field:

    a.json: cas9-efficiency @ v1  digest e699679b422d…
    b.json: cas9-efficiency @ v1  digest e699679b422d…
    agree: the same scientific result (timestamps and versions aside)      exit 0

One of those models stood behind every one of its ten predictions. The other disclaimed nine of them.

`n_test` was in the scientific body; `n_out_of_distribution` was not. One ratio, split across the honesty
boundary — the digest covered how many examples were scored and not how many the model was willing to be
judged on. And this is not a field nobody cares about: the leaderboard carries it precisely because a board
without it *"puts two very different models on the same row"*, in a comment written when that column was
added. The same argument that made it ranking-relevant makes it part of the scientific claim.

Moved it into the body, bumped `RESULT_SCHEMA_VERSION` to 4 — an old result's stored digest will no longer
re-derive, and the version is how a consumer detects that instead of misreading it. Compare now says
`DIFFER — n_out_of_distribution: 0 != 9`.

One note on the test. My first version asserted `not disclaimed.agrees_with(result)` after a `model_copy`,
and it failed: `agrees_with` compares *stored* digests, and a copy carries the original's. The record was
right and my assertion was wrong. The real guarantees are that a genuinely-different run re-derives to a
different digest, and that a record whose count was edited fails its own digest verification — which is what
`bench compare` reported. Asserting the mechanism I had actually demonstrated, rather than the one I assumed.

**Lesson: when a ratio's parts are stored as separate fields, check they sit on the same side of every
boundary that matters — signed/unsigned, scientific/volatile, shown/hidden. R134 found `total` and `skipped`
ranging over different populations; this is the same pair split by a different axis. A denominator inside the
integrity envelope and a numerator outside it is a guarantee that covers half a fraction.**

## Round 140 — a gate that could fail but not explain

Continuing R139's boundary question onto the design side. There is no `agrees_with` there; the equivalent is
`scripts/reproduce.py`, which re-derives a canonical menu twice (asserting determinism) and diffs a
canonicalized digest against a committed golden. It is a blocking `make ci` job.

Read what it excludes: `_VOLATILE_KEYS = {alleleforge_version, config_snapshot}`. The config snapshot is
dropped wholesale, but `seed` also lives at the top level of provenance and is *not* dropped, and any setting
that changes a result changes the candidates it is hashed over — so the exclusion is sound. Negative result.

The defect is in what happens when it fails. Induced a drift and read the output:

    REPRODUCIBILITY DRIFT
      golden : 0000000000000000000000000000000000000000000000000000000000000000
      current: 15c7255c68273cb36314a333f7e19dec3b25754bd0388c93063f5d90e45ad87f

That is the whole report. A blocking gate tells a developer that something moved and refuses to say what,
while holding both bodies in memory at the moment it prints. The golden stored `{sha256, n_candidates}`, so
the information was not on disk either — even `git log` on the manifest shows only a changed hash, and a
reviewer looking at a reproducibility change sees one opaque line.

The canonical body is 8 KB and 200 lines. Committing it makes the golden a readable artifact where drift
shows up as an ordinary diff in review, and lets the gate walk the two bodies and name the leaves:
`candidates[0].efficiency: 0.5 -> 0.7`, truncated after 25. Also gave the script its first tests — it is the
mechanism the project's central reproducibility claim rests on and it had none.

**Lesson: a check that can only say yes or no is half a check. Whenever a gate compares two artifacts, ask
whether it keeps the losing side around long enough to explain itself — and whether the committed reference
is something a human can read in review, or only a hash that changes for reasons no diff will show.**

## Round 141 — one name, seven classes

R140's lesson sent me through the other gates asking whether each keeps the losing side. They all do, and
better than I expected: `Split.verify` names the leaking fold *and an example id*; the FM-index integrity
check prints expected and reconstructed digests; `aforge verify` accumulates a `problems` list rather than
failing on the first. Nothing to fix. Recorded.

What the sweep did surface was next to those checks rather than inside them. Three modules each define their
own `ChecksumError`; four define their own `ConsentError`. Not aliases — seven distinct classes, exported
under two names from four public packages:

    >>> from alleleforge.genome import ChecksumError as G
    >>> from alleleforge.data import ChecksumError as D
    >>> G is D
    False
    >>> try: raise D("dataset checksum mismatch for gnomad.vcf")
    ... except G: ...
    alleleforge.data.registry.ChecksumError: dataset checksum mismatch for gnomad.vcf

A caller who guards a design run with the one they happened to import catches a third of the artifact-gate
surface and the rest escapes as an unrelated-looking `RuntimeError`. There is no visible edge to this: the
name is identical, the base class is identical, the docstrings are near-identical, and the scorers' own
docstrings say *"ConsentError / LicenseError / ChecksumError: From the weight gate"* as though each named one
type. Checked the four `ConsentError` docstrings before unifying — "download", "fetch", "network fetch" — one
policy in four wordings, not four policies.

`alleleforge/errors.py` now holds one class each; every module re-exports the names, so no import breaks and
`isinstance` agrees. Rewiring the re-exports made `mypy --strict` complain that a package cannot re-export an
imported name implicitly — which pushed the `__init__` files to import from the canonical module directly,
the better shape anyway.

**Lesson: duplication is usually a tidiness complaint, and this one is not — a duplicated *exception* is a
duplicated `except`, and the failure mode is that a correct-looking handler silently declines to run. Worth a
standing check: for every exception name defined more than once in a tree, confirm the copies are genuinely
different failures. Same name plus same base class plus same meaning is a bug with no symptom until the day
it matters.**

## Round 142 — the gate was built, tested, and never opened

Closed R141's sweep first: every exception name in the tree is now defined exactly once. Then took the
"implemented but nothing switches it on" tell — which has now found something in three consecutive rounds
(R136 `to_one_based`, R137 `Liftover`, R141's unreachable `except`) — and pointed it at on-disk state.

`ContentAddressedCache` has a genuinely careful integrity design: a checksum sidecar per entry, re-verified
on read, a *missing* sidecar treated as corruption rather than downgraded to an unverified read, and the
sidecar published before the payload so a concurrent reader never sees a payload without one. Someone thought
hard about this. It is gated on `verify=`, which defaults to `False`.

The library constructs exactly one cache — `PersistentEmbeddingCache` — and it took the default. So
`verify=True` occurs only in `tests/test_cache.py`. Every one of those careful behaviours has run in CI and
never once in the product.

The default is defensible in general and wrong for this cache specifically. A corrupted embedding does not
raise; it deserializes into a plausible vector, which becomes an efficiency score, which is the number a
guide is ranked on — a wrong answer with no error, the failure class this project keeps finding. And the cost
is a SHA-256 over a few kilobytes, weighed against the transformer forward pass the cache exists to skip.

One migration detail worth stating, because turning a gate on is not free. A missing sidecar is *deliberately*
an integrity failure and not a miss — otherwise `rm *.sum` defeats the gate. So flipping the flag would have
turned a user's warm cache from an earlier release into hard errors on data that is perfectly valid. The
namespace now carries a `v2` segment: old entries are simply never looked up. Inert, not fatal.

**Lesson: a safety mechanism with a flag has two implementations — the code, and the set of call sites that
pass the flag. Reviewing the first and never enumerating the second is how a well-tested gate ends up never
running. When a check is opt-in, the audit question is not "is it correct" but "who opted in", and the answer
here was: only its tests.**

## Round 143 — the token nothing read

Three negative results first, and they are worth recording because they are places I expected to find
something. Every `bool = False` default in the tree is fail-safe in the conservative direction
(`allow_network`, `calibrated`, `synthetic`), and `OffTargetResponse.from_report`'s `on_target_excluded`
default is passed correctly by its one caller. `RankingWeights` rejects non-finite, negative, and all-zero
weights, so a user cannot pass `--weights 0 0 0 0` and get an arbitrary order presented as a ranking. And
diffing the HTML and PDF renderers by the fields each reads returns the empty set in both directions — they
are genuinely in step.

Then, the missing SECURITY.md. This repository ships a web API with an auth token, downloads pinned
artifacts, and accepts signed JSON submissions from strangers; it had no stated way to report a vulnerability
privately. Writing that file honestly meant reading the actual posture rather than describing a generic one —
and reading it is what found the round's real defect.

`resolve_serve_token` refuses a non-loopback bind without a token. Good. It is called by `serve()`. And the
deployment guide's flagship command is:

    uvicorn alleleforge.web.api.app:app --host 0.0.0.0 --port 8000

as is the Dockerfile's `CMD`. Both bind the module-level `app`; neither goes anywhere near `serve()`. So the
guard does not run on the documented path — which I expected, and which is only half of it. `create_app` did
not read the environment either. Checked it directly:

    ALLELEFORGE_API_TOKEN=s3cret → POST /api/resolve with no header → 200

An operator who publishes the port and sets the variable, exactly as the variable's name invites, gets a
fully open API. The security control is not weak on that path; it is absent, and it looks present.

`create_app` now defaults `api_token` from the environment, so the variable works everywhere and
`resolve_serve_token` keeps its distinct job of *requiring* one before a public bind. The guide binds
loopback by default and documents the token form for anything else; compose maps `127.0.0.1:8000:8000`
instead of every host interface. Then SECURITY.md, describing the posture as it now actually is.

**Lesson: writing the honest version of a document is an audit. I set out to record what the security
controls are and could not do it without checking each one on the path users are actually sent down — which
is a different path from the one the control was written against. Two of the last three rounds found a
mechanism that exists and does not run; this one found the entry point that skips it. When a guard lives in a
convenience wrapper, check what the docs tell people to run instead of that wrapper.**

## Round 144 — the checker I threw away was the one that was broken

R143 ended on "when a guard lives in a convenience wrapper, check what the docs tell people to run instead."
The general form: every copy-pasteable command in the prose is a promise, and nothing checked them.

I had tried this before. In R138 I extracted the `--flags` named in string literals, compared them against a
click walk of the CLI, got a page of obvious false positives (`--region` "not a CLI option"), concluded the
traversal was broken rather than the app, and dropped it. That was the right call on the evidence and I never
found out why. It is this:

    >>> c = typer.main.get_command(app)
    >>> isinstance(c, click.Group)
    False
    >>> sorted(c.commands)
    ['batch', 'bench', 'data', 'design', 'lift', 'offtarget', 'resolve', 'verify']

A `TyperGroup` is not an instance of the `click.Group` visible from here, so an isinstance-gated walk finds
no subcommands and reports the root callback's five options as the entire CLI. Walking on
`hasattr(cmd, "commands")` gives the real tree.

With that fixed the check runs, and all 25 documented commands resolve — every subcommand real, every flag
accepted. A clean negative, which is the outcome I expected and wanted; the value is in it staying that way,
so it is now a test rather than a one-off script, sitting beside the existing command-appears-in-the-docs
check as its converse. Mutation-checked by renaming one flag in the README.

**Lesson: an audit that produces implausible results has two suspects, and I recorded the right verdict
("inconclusive, not a clean bill") without going back for the cause. Six rounds later the same question came
up and the tool was still broken. When a check is abandoned as untrustworthy, the finding is that the check
is broken — which is a bug with an owner, not a dead end. Fix it or delete it; leaving it "inconclusive"
means the next person pays the same cost.**

## Round 145 — the document I had been damaging

Went looking for my own deferrals, per R144. The standing one — `Prediction.calibrated` coerced to `False` on
an untrusted reload — is a deliberate anti-forgery design, pinned in both directions by its own tests, and
re-confirmed as contained. That is a decision, not an abandoned check; left alone.

What I found instead was a document I had been actively making worse for sixty rounds. `## [Unreleased]` held
**77** change-type headings: 36 separate `### Fixed`, 32 `### Added`, 7 `### Changed`, 2 `### Security`. Keep
a Changelog gives each release one section per type; every round of this session prepended a fresh heading
rather than merging into the existing one, which is a small, invisible-per-commit choice that compounds into a
document where *"what was fixed"* cannot be read in one place — the only question a changelog exists to
answer. A human had already been asked to clean up the thirteen that predated me. I had turned thirteen into
seventy-seven.

Consolidated to four sections, in the documented order, with all 300 bullets preserved verbatim — verified by
diffing the sorted bullet sets before and after, which is the check that makes a mechanical rewrite of a
hand-written document safe to do at all. Then pinned it, because the reason it drifted is that nothing looked.

**Lesson: I have spent sixty rounds auditing the product and never once audited my own output. Every round
edits the changelog, the round log, and the specs, and those edits get exactly the review that unreviewed
work gets. Worth adding to the rotation: run the audit on the artifacts the audit produces. The tell here was
cheap — one `grep -c '^### '` — and the defect was mine, growing by one every round, while I looked for other
people's.**

## Round 146 — the log ran backwards

R145 ended on "run the audit on the artifacts the audit produces." Ran it on this file, and it is worse than
the changelog was.

Three findings, all mine, none of them subtle once looked at:

**The order reverses.** Rounds 1–134 ascend; 135–145 descend. Eleven rounds ago I started prepending each new
entry ahead of the previous one instead of appending, and never once read the file top-to-bottom to notice
that the audit history now runs forwards for 134 rounds and then backwards. Repaired by sorting the sections;
verified as a pure reordering by diffing the sorted line multiset before and after, which is the check that
makes a mechanical rewrite of a hand-written document safe to attempt.

**Two rounds have no entry.** 50 and 71 shipped real work — the render cap exposed on both shells, and the
`REVERT` intent that the CLI offered and one incidental test line mentioned — and later rounds cite both by
number. Written now from their commit messages and labeled as reconstructions, because I do not recall them
and should not pretend to.

**One gap is not a gap.** 117 looked like a third missing entry. It is not: R116's entry covers both of that
round's commits, including the generalization from gnomAD to haplotype panels and patient VCFs, and its
lesson is the one R118 and R121 attribute to "R117". The number was skipped; the work is logged. Checking
that before writing a reconstruction is the difference between repairing a record and inventing one — the
reconstruction would have been plausible, sourced from a real commit, and false.

All three pinned: ascending order, and every number in the range resolving to an entry or to a skip recorded
with its reason (with a guard that the allowance cannot outlive the gap).

**Lesson: R145 said to audit my own artifacts and I treated that as one round's finding rather than a
standing query. The first application found a second document with two defects worse than the first's. The
general shape: a document edited a little by every unit of work, and read in full by none of them, degrades
in ways no individual diff shows — the changelog's 77 headings and this file's reversal were both invisible
per commit and obvious in one `grep`. Also: "missing entry" and "skipped number" look identical from the
gap, and only one of them is repaired by writing something.**

## Round 147 — the rules had stopped keeping up

Third pass of R145's standing query, on the third artifact every round edits: the specs. Those came back
clean — every `###` is a `Requirement:`, every `####` a `Scenario:`, no requirement without a scenario, no
duplicate titles, and the flat `Purpose`/`Requirements` shape means appending is the right place to append.
A negative, and a welcome one after two documents in a row.

The defect was one level up. `openspec/project.md` is where the audit's findings become *rules* — the file a
future contributor reads instead of 4,000 lines of log — and its conventions stopped at R128. Everything from
R134 onward existed only inside individual round entries, which is exactly the failure the file exists to
prevent: a lesson that has to be rediscovered because it was recorded somewhere nobody reads twice.

Added the seven that are genuinely actionable rules rather than findings — co-presented numbers over
different populations; an ordering as an unretractable claim; "who opted in" for an opt-in check; a guard
that the documented command routes around; a duplicated exception as a duplicated `except`; a broken checker
as a bug with an owner; and audit-your-own-artifacts, with the "missing entry vs skipped number" corollary.

Then pinned the thing that makes the file usable: every `R<n>` a rule cites must resolve to a log entry. The
check found a dangling citation on its first run — `R117`, cited by the git-amend rule, the number R146
established does not exist — which now resolves via the documented skip. Its first mutation did **not** fire:
I had restricted the check to citations inside the log's range, which quietly excused a citation to a
*future* round, the most likely typo of all. Tightened to flag anything at or above the first round.

**Lesson: a distillation is a cache, and caches go stale silently. The log grew by twelve rounds while the
rules file did not, and nothing about either document made that visible — the log looked healthy because it
was growing, and the rules file looked healthy because it was not shrinking. When one artifact is derived
from another, the check worth having is not on either one but on the *link* between them.**

## Round 148 — the version nobody would have bumped

R147 ended on: when one artifact is derived from another, check the *link*. So: enumerate the derived
artifacts. Most are already pinned, and pleasingly so — the JSON schemas against the pydantic models, the API
reference against the package, the README's command table against the CLI in both directions, the
reproducibility golden against the design pipeline, the benchmark splits by content hash, the committed
figures by a CI regeneration check. Six links, six guards.

The unguarded pair is the one that leaves the repository entirely. `CITATION.cff` and `.zenodo.json` restate
the version, the license, the title, the repository URL, the authors and the keywords — facts owned by
`_version.py` and `pyproject.toml`, and by each other — and nothing compared any of them. `CITATION.cff`
carries `version: 0.1.0.dev0` by hand. `RELEASE.md`'s pre-flight says to bump `_version.py` and notes that
the Rust crate's version is asserted equal in the suite; it did not mention this file, and no test did
either. So the first release bumps the package and leaves the citation naming a version that never existed —
in the one artifact whose entire job is to be quoted by someone else, in a project whose stated purpose is
reproducible open science.

Pinned: version against the package, license against `pyproject` and the `LICENSE` file, title/URL/authors/
keywords between the two files. It found a live divergence immediately — the keyword lists differ by
`benchmark`, present in the Zenodo record and absent from the CFF, and Zenodo is the correct one since the
project does ship CRISPR-Bench. Added it, and added the file to the release checklist so the human step and
the automated one say the same thing.

**Lesson: the derived artifacts that go stale are the ones that leave the repository. Everything consumed by
`make ci` gets checked because a failure is felt immediately; a citation file, a package recipe, a Zenodo
record are read only by strangers, months later, and their failure mode is that someone else is wrong about
your work. Enumerate what the repository emits, not just what it builds.**

## Round 149 — the install nobody had done

R148's lesson: enumerate what the repository *emits*. The largest thing it emits is the package, and the test
suite has never once run against it — `make ci` runs from `src/` with every optional extra installed. So:
build the wheel, install it into an empty venv, and be a new user.

The wheel itself is fine, and worth recording as a negative: hatchling ships all 33 non-Python runtime files
— the CFD matrix, seventeen model cards, the benchmark splits and fixtures, `py.typed` — and a diff of the
package tree against the archive is empty. Data files resolve from the installed location.

Then I ran the quickstart the way the deployment guide writes it. `pip install "alleleforge[cli]"`, then
`aforge design …`:

    ModuleNotFoundError: No module named 'pyfaidx'

with a full Rich traceback. That is a *documented* install — the guide's table lists "CLI" and "Genome
access" as separate rows — so the first command a new user runs after the CLI install fails, and fails in the
least useful way available. The irony is that this codebase answers this question well everywhere it asks it
explicitly: *"install the 'genome' extra"*, *"install alleleforge[cas9-rs3], or use…"*. It never gets to ask.
The CLI defers its heavy imports into the command bodies, but the modules those pull in import their own
dependencies at module level, so the ImportError escapes from inside the import statement, upstream of every
guard.

`design`, `batch` and `offtarget` now translate it: the module name, mapped to the extra that installs it,
and a non-zero exit. Then installed `pyfaidx` and ran the design again from the installed package, end to
end, to confirm the whole thing actually works: one ABE candidate, real reagent, provenance written.

**Lesson: a test suite that runs from the source tree tests the source tree. Everything about how the product
is *obtained* — the wheel's contents, the extras' boundaries, the first command after the documented install
— is outside what CI can see, and it is the entire experience of every user who is not me. Build it, install
it somewhere empty, and use it.**

## Round 150 — verifying a claim I could not otherwise have believed

Continuing R149 across the other things the repository emits. Three verifications, one guard, no new defect —
recorded because "I checked and it holds" is worth as much here as a fix, and because two of these are
claims the docs make in the reader's face.

**The core install is genuinely minimal.** `pip install alleleforge` into an empty venv pulls eight
transitive packages — pydantic, pydantic-settings, PyYAML and their own deps — and no heavy stack. The
deployment guide's claim that it is "deliberately minimal … so it imports fast" is true.

One scare worth writing down: the first `import alleleforge` in that venv took **52 seconds**. It is bytecode
compilation of the whole package on a venv where `pip` did not byte-compile at install; warm imports are
79/84/94 ms across three runs. I nearly filed a performance defect on a measurement of the filesystem.

**The Docker image is complete for what it serves.** It installs `[core,variant,cli,web]` plus `pyfaidx` and
`pyliftover` by name rather than the whole `genome` extra, so `cyvcf2` and friends are absent — which is a
deliberate slimming of heavy C extensions, and the VCF fast path has an explicit guard with the right
message. The web app has no module-level genome import, so it starts without a reference and returns 503
until one is configured, exactly as documented.

The guard is on the claim most easily broken by accident. One top-level `import numpy` in any module the
package `__init__` chain touches makes the core install fail on a clean machine, and no test in this suite
would notice, because CI installs every extra — the same blind spot R149 walked into. A subprocess probe now
imports the package in a clean interpreter and asserts none of nineteen optional roots got loaded.

**Lesson: a property that only holds in an environment CI never constructs needs a test that constructs it.
"No optional dependency is imported at module level" is invisible to every test in an environment where all
of them are installed and importable — the assertion has to be about `sys.modules` in a fresh interpreter,
not about behaviour. When a promise is about what is *absent*, the test has to be about absence too.**

## Round 151 — the two absence claims

R150's lesson: a promise about what is *absent* needs a test about absence. This project makes two such
promises, both about privacy, both stated in the README, the deployment guide, and the served page itself.

**"No outbound network call during a design request."** This one is tested, and I wanted to know whether the
test works rather than that it exists. It patches `socket.socket.connect` and asserts nothing connected —
which is the right shape. My first mutation did not fire: I injected a connection into `create_app`, which
runs at fixture setup, before the patch is installed. Moving it into the design handler — inside the request,
which is what the claim is actually about — failed the test immediately. The project's most load-bearing
privacy guarantee is genuinely enforced. A negative result I am glad to have checked rather than assumed.

**"The served frontend loads no third-party scripts."** This one was not tested at all. It holds today —
every `src`, every `<link href>`, all four `fetch` calls are same-origin relative paths — and it is one CDN
font from being false. The failure would be silent, invisible in review to anyone not thinking about it, and
the harm is specific: a lab opens this page while pasting patient variants into it, and a third-party request
leaks the fact and timing of every visit before it leaks anything worse.

The guard scans the served assets for off-origin targets in the positions a browser fetches *on its own* —
`src`, `srcset`, `<link href>`, CSS `url()` and `@import`, `fetch`, `XHR.open`, `WebSocket`, `Worker`. An
`<a href="https://…">` is explicitly allowed: a link the user clicks is navigation, not a load, and a rule
that forbade it would be wrong in a way that invites someone to weaken the whole check later. Mutation-checked
against an injected CDN script tag, a Google Fonts stylesheet, an analytics `fetch`, and a CSS `@import` —
all four caught.

**Lesson: for an absence claim, "there is a test" and "the test would catch it" are much further apart than
usual, because such a test passes in exactly the same way whether it is watching the right thing or nothing
at all. The socket test looked fine and my first attempt to break it succeeded — not because the test was
weak, but because I broke the wrong thing. Mutate at the point the *claim* is about, not the point that is
easiest to reach.**

## Round 152 — four correct guards and no mechanism

R151's lesson — mutate at the point the claim is about — turned into a sweep of the safety gates. Three clean
bills, each verified by breaking the gate and watching the suite:

* **Consent.** `artifact_download_permitted` forced to `True`: **7** failures, across all three registries and
  the config. Nothing downloads without the caller's say-so, and that is enforced.
* **Checksums.** All three `_verify_sha256` comparisons neutered: **8** failures, including the
  re-verify-on-cache-read path. An unverifiable artifact really is refused.
* **Split leakage.** The train/val/test disjointness check disabled: caught, by a direct test.

The fourth claim did not survive. `openspec/project.md` lists "CI stays weight-free" as a *non-negotiable
design principle*, and the marker documents itself as doing it — `"real_weights: tests that require
downloading real model weights (opt-in, skipped in CI)"`. CI runs a bare `pytest`. There is no
`-m "not real_weights"` anywhere, and no conftest hook. What actually keeps real weights out of CI is that
each of the four marked tests opens with its own hand-written skip:

```python
if importlib.util.find_spec("lightgbm") is None or ...:
    pytest.skip("cas9-rs3 extra not installed")
```

Four guards, all correct, written four times. The fifth `real_weights` test — added by someone reading a
marker whose description says the marker handles this — downloads real model weights in a CI job.

The root conftest now skips both opt-in markers unless their environment variable is set. `native` is
deliberately excluded: it has a dedicated CI job selecting it with `-m native`, which this would silently
turn into a no-op — the sort of collateral a centralizing change invites. Pinned with a throwaway suite run
under the real conftest, asserting both halves, because an opt-in that cannot be opted into is just a
deletion. Marker descriptions updated to name the variable rather than to describe a behaviour they do not
implement.

**Lesson: "documented, correct, and repeated by hand at every site" is the state a policy is in just before
it fails. All four guards here were right; the defect was that there were four. When a principle is called
non-negotiable, find the single place that negotiates it — and if there is no such place, that is the
finding.**

## Round 153 — the citation that stayed in the docstring

R152's lesson pointed at the other non-negotiable principles: for each, find the single place that enforces
it. Most hold. Principle 2 (no bare floats) has `BareFloatError` and `ensure_prediction`; principle 5 has
`scripts/reproduce.py`; principle 7 is `make ci`. Principle 8 — *cite everything: every dataset, model, and
scoring function carries a citation and a version, in code and in output provenance* — has a test I wrote in
an earlier round covering datasets and model cards.

It covers two of the three nouns. **Scoring function** was not checked, and does not hold.

The citations are there — `offtarget/scoring.py`'s module docstring names Hsu et al., *Nat Biotechnol* 2013
and Doench et al., *Nat Biotechnol* 2016, with a note that the CFD matrix was cross-verified against CRISPOR
and CRISPRitz. They are in code, as the principle asks. They are not in the output. A real report carries:

    offtarget_scorer: 'CFD'   offtarget_matrix: 'doench-2016-cfd'

which encodes the paper in a slug and cites nobody, while the same report's provenance lists three heuristic
models each with a full citation, because those come from registry cards and a card requires one. The
off-target score is the number a reviewer is most likely to ask the provenance of, and it was the single
attribution that did not travel with the result.

Added the citations as data keyed by `ScoreMethod`, surfaced on the report, both renders, and the flat export
(schema 3 → 4). Two things went wrong, and both are the point of the round:

**My first version returned `None` for every real report.** I keyed the lookup on the `ScoreMethod` enum
(`"cfd"`), and an `OffTargetReport` stores the scorer's *display name* (`"CFD"`). So the citation existed, in
a dict, that nothing could reach — the exact failure the change was written to fix, reproduced inside the
fix. It was caught by the one line in the new test that exists for this: `assert cited, "no candidate carried
a scorer citation — the check would be vacuous"`. Without that guard the test passes on an empty list. The
lookup now resolves display names off the scorer classes themselves, so renaming one cannot break the link.

**I reverted my own work with `git checkout`.** `project.md` has carried a rule against exactly this since
R96. I used it to undo a mutation on `html.py` and silently lost the renderer edit I had made minutes before.
The only reason it surfaced is that the full suite ran afterwards and a test that had just passed in
isolation failed. The rule now records that it has happened twice, and adds the tell: *a test that passes
alone and fails in the full run right after a mutation loop — suspect the restore, not the test.*

**Lesson: a principle with three nouns needs three checks. The test for principle 8 read as complete —
"datasets and models, cited and versioned" — and stopped one noun short of what the principle says, in a
place no one would look because the test's name promised coverage. When a stated rule enumerates, make the
test enumerate from the *rule*, not from the implementations you happen to think of.**

## Round 154 — enumerating from the rule

R153's lesson, applied to itself. That round found a test for an eight-word principle that checked two of its
three nouns; the file it lived in has the same shape one level up. `test_stated_principles.py` is named for
*the principles* and its docstring says it "pins the mechanically checkable ones" — and it contained three
tests for eight principles, with no record of which five were unaccounted for or why.

Checked the rest by hand first, which is the part worth keeping. Principle 2 ("no bare float; every
prediction ships an interval, a method tag, a calibrated flag and an OOD flag") is structurally satisfied:
`Prediction` requires `interval` and `method` and defaults both flags, and `ensure_prediction` /
`BareFloatError` reject a bare float at the scorer boundary — four nouns, all four enforced by the type. 5
and 7 are `scripts/reproduce.py` and `make ci`. 1 is structural. 4 ("wrap, don't rebuild") is a judgement
about whether a new model fills a genuine coverage gap, and no assertion decides that; 6 ("three audiences,
one core") is not checkable as stated, and its nearest evidence is the cross-surface parity tests that live
with each surface.

So the deliverable is not a new assertion about the code — it is that the *list* is now the source of the
check. The test parses the numbered principles out of `openspec/project.md` and requires each to name its
evidence: a test in this module (which must exist), or the reason it cannot be mechanised. A ninth principle
added to the list fails the suite until someone writes down how we know it holds. Mutation-checked both ways.

Recording the honest limit: this asserts that we have written down how we know, not that the principles are
true. Four of the eight rest on structure or judgement rather than on an assertion, and saying so in a file
that a reader will take as coverage is the whole point.

**Lesson: the fix for "a test that covers a subset while reading as complete" is not more tests — it is to
make the *enumeration itself* the thing under test, with an explicit, reasoned entry for every member,
including the ones that cannot be checked. Then the gap is a failure rather than an absence. That is the
third time this session the same shape has worked: documented skips in the round log, `_SKIPPED` for cited
rounds, and now evidence-per-principle.**

## Round 155 — the row that was not there

Back to the product after several rounds on process. Built a 6 kb contig with an editable ABE site and two
deliberate near-identical decoys, ran a real population-aware design through the CLI, and read the rendered
HTML the way a bench scientist would.

Most of it holds up, and two recent rounds show their work in it: R153's citation is on the scoring-basis
line (*"CFD / doench-2016-cfd + doench-2016-seed-tolerance-approximation — Doench et al., Nat Biotechnol
2016"*), and R136's coordinate labelling turned my own mistake into a clear error — I passed `chr7:3003`
meaning a 0-based offset and got *"reference mismatch at chr7:3002: asserted ref 'A' but reference has 'T'
(wrong build?)"*, which is the 1-based `chrom:pos:ref>alt` boundary doing exactly what it should.

Then the outcome table:

    allele      probability   intended
    A6G         0.288
    A5G;A6G     0.192
    wildtype    0.192
    showing 3 of 8 predicted alleles (0.67 of the probability mass)

Nothing in the `intended` column. The full distribution puts the requested `A4G` **seventh of eight at
0.048** — outside the top three, so it was simply not shown. A scientist reading the table that answers
"what will happen to my cells" sees three plausible outcomes, none of them theirs, and must notice a separate
`P(intended) = 0.05` line elsewhere on the page to understand that their edit lives in the 33% the caption
politely calls "the rest".

This is R49's finding one level down, and R49's own lesson names it: *"a truncation is a claim about what
does not matter, and it is wrong exactly where the product's value is concentrated. When adding any 'show the
top N', ask what the tail is for."* R49 applied it to the candidate list, keeping Pareto-front members
through the cap. The allele table has the same cap and the same promise living in its tail — a bystander-heavy
base editor puts the intended edit outside the top few *routinely*, not exceptionally.

The intended allele now always survives the cap, and the shown-mass arithmetic follows the rows shown. The
table now reads `A4G | 0.048 | ✓` and `showing 4 of 8`.

**Lesson: a lesson recorded against one truncation does not transfer to the others by itself. R49's rule was
written down, in this file, in the imperative — and the identical cap one call-frame away kept its naive
form for a hundred rounds. When a fix ends in a general rule, spend the extra five minutes grepping for the
other places the rule already applies; the round that writes the rule is the cheapest time to apply it.**

## Round 156 — running R155's rule on the rest of the codebase

R155 ended on: when a fix produces a general rule, grep for the other places it already applies, because the
round that writes the rule is the cheapest time to apply it. Ran that on the rules already in `project.md`,
and this round is what came back — three clean bills and one missing guard.

**Other truncations.** R49 and R155 fixed the candidate cap and the allele cap. The third list a reader could
be shown a slice of is the off-target sites — and that would be the worst of the three, because a dropped
site is a hidden hazard rather than a hidden option. It is not capped anywhere: the CLI lists every nominated
site, and the report renders none individually. Clean.

**"After adding a field to a model, grep for the model's other constructors."** I added
`offtarget_scorer_citation` in R153 and changed `outcome_top`'s construction in R155, without doing this.
Checked: `CandidateReport` and `DesignReport` each have exactly one production constructor, in the builder.
The rule held by luck rather than by my following it, which is worth writing down as plainly as a defect.

**The missing guard.** `project.md` also says: *"A test that iterates `Model.model_fields` instead of naming
fields covers the fields that do not exist yet."* `Provenance` has one — it is what makes the footer's
hand-enumeration checkable — and so does `OffTargetReport`. The two models a *reader* reads, `CandidateReport`
and `DesignReport`, did not. Both are currently clean, including the two fields I added; but "clean because I
checked once, by hand, after the fact" is the state every recurring defect in this log started from.

Added it. Static and deliberately weak: it asserts each field is *referenced* by one of the three renderers,
not that it is well-placed. It catches the one failure that keeps recurring — a field nothing reads — and
carries the now-familiar documented-exception map so a genuinely internal field can be excused with a reason
rather than silently.

**Lesson: "the rule held" and "I followed the rule" are different findings, and only the second one is a
process working. Two of this round's three clean bills were places where I had already violated the
procedure and got away with it. A conventions file is only load-bearing if something checks it; the ones here
that are checked (`Provenance`'s field coverage) have never been the source of a defect, and the ones that
are advice have been the source of several.**

## Round 157 — "no actionable candidate" is not an answer

R155's run left a loose end I did not pull: the menu said *"prime: eligible but no actionable candidate
enumerated"* for a trivial A>G, and I moved on. Pulling it.

The behaviour is correct. Prime found nothing because every protospacer in range places its nick too far from
the edit for a synthesizable RTT — I first assumed "edit 5' of the nick", and the tally says that accounts for
8 rejections against 360 for RTT range. My assumption was wrong, which is the point: if I cannot infer the
reason from the report while holding the code open, a bench scientist has no chance.

And the reasons are not interchangeable. *No PAM in range* means try another PAM or another chemistry. *Edit
5' of every nick* means try the other strand. *RTT out of range* is closer to a genuine dead end. *TTTT in the
spacer* is a Pol III terminator and says nothing about the locus at all. One sentence — "no actionable
candidate" — collapses four different next steps into a shrug, on the chemistry the project leads with.

The enumerator now counts why each protospacer was rejected, into an optional mapping. Opt-in matters here:
`project.md`'s rule is that anything added inside a hot scan costs per call, and this one is a dict increment
per *rejected* candidate, taken only when a caller asks. The designer asks, and renders it only when the
vertical came back empty — so the normal path pays nothing and the empty path explains itself.

Two things worth recording about the process. The designer-level note initially had no test: my first
mutation (blanking the reason) passed the whole `tests/design` suite, because the only test I had written was
at the enumerator. A tally that reaches no reader is the exact defect this round is about, reproduced one
layer up — the second time in five rounds that I have built an honesty mechanism and nearly failed to
connect it. And the reproducibility gate fired on the changed rationale and **named the changed value**,
which is R140's work paying for itself: the diff showed the added sentence rather than two hashes, and one
look confirmed the change was intended before updating the golden.

**Lesson: an honest "nothing found" still owes the reader the reason, and the code almost always knows it —
it is sitting in the `continue` statements, thrown away one branch at a time. A search that rejects
candidates in a loop can always say what it rejected them for; the only real cost is deciding to carry it.**

## Round 158 — the siblings

R116's question, which this log keeps finding useful: after fixing something, which siblings did I just skip?
R157 gave prime a reason for its empty results. Cas9 and the base editor have the same silent-`continue`
loops.

The base editor's are the more valuable, because one of them is not about the locus at all. *No deaminase in
the panel installs this substitution* means base editing is the wrong chemistry for this edit and no amount
of looking elsewhere in the genome will help; *the target base is outside every activity window* means try an
editor with a different window; *no PAM in range* means try a different PAM. Reporting "no actionable
candidate" collapses a fact about the edit into a fact about the search.

Before writing the third copy of the tallying helper I moved it into `enumerate/_reasons.py` and rewired
prime onto it — `project.md`'s rule is to read the existing implementation before writing a local version,
and I was about to become the person that rule is about. Each enumerator keeps its own reason *labels*, in
its own words; the shared module owns only the counting and the rendering.

Two process notes. Generalising the empty-tally string from "no protospacer was examined" to "no candidate
was examined" broke the test I had written the round before — correct, and caught immediately. More
usefully: the designer wiring for the base editor **silently never got applied**. An earlier edit script
raised partway through, after printing progress for the step before the failure, and I read the success line
and moved on; `git status` not listing `designer.py` is what caught it, two steps later. `_run_base_editors`
builds its own `_run_chemistry` call, so nothing about the prime wiring reaches it and no test would have
noticed until I wrote one.

Both verticals now report:

    - base_abe: eligible but no actionable candidate enumerated — no PAM match at this offset (44)
    - prime: eligible but no actionable candidate enumerated — no PAM match at this offset (226)

**Lesson: a multi-file edit script that fails partway leaves the tree in a state where everything compiles,
every test passes, and one of the changes is simply absent. `git status` at the end of a change is not
bookkeeping — it is the only thing that notices a step that never ran. Compare the files you *intended* to
touch against the files that changed.**

## Round 159 — 0 candidates or 190, depending on a flag nobody could reach

Finishing R158's sweep. The Cas9 enumerator turned out not to have the same shape: its scan uses positive
`if pam.matches(...)` conditions rather than `continue` guards, so there is no list of distinct rejection
reasons to tally. Forcing the pattern there would have been a refactor of a hot loop for a single reason.
Recorded as a negative — and then the sweep found something better one level up.

`enumerate_cas9` falls back to **SpCas9-NG** (`NG`) and **SpRY** (`NRN`/`NYN`) when no `NGG` guide is
actionable. Both are published, widely used PAM-flexible variants; both are implemented and tested here;
`design_cas9` exposes both as parameters. `design()` — the unified entry point behind the CLI, the web API
and the cohort path — passes neither and accepts neither. So the capability was reachable only by calling the
lower-level vertical directly from Python, which is R137's shape exactly.

The size of it, at a locus with no NGG in range:

    default          → 0 candidates, "eligible but no actionable candidate enumerated"
    --allow-ng --allow-spry → 190 candidates

A scientist reading the first line concludes Cas9 cannot touch their locus. The tool knew otherwise and did
not say. Both flags now reach the CLI, off by default — an NG guide is a different reagent with different
specificity, so it is offered rather than assumed — and an empty Cas9 vertical names the variants it did not
try, which is the form its structure supports.

**Lesson: "the sibling does not have this defect" can be the wrong conclusion drawn from the right
observation. Cas9 genuinely lacks the multi-reason structure the other two had, and I nearly stopped there —
the actual defect was one frame up, in what the unified entry point declines to forward. When a sweep clears
a sibling, check the layer that calls it before closing the question.**

## Round 160 — what the shells decline to forward

R159's lesson said to check the calling layer before closing a question. The mechanical form of that is a
parameter diff, so I ran one: `design()` against the three verticals below it, and against the two shells
above it.

Below: clean. Every parameter the verticals accept, `design()` forwards.

Above: three gaps, and the third is mine from one round ago.

* **The trained prime model.** The CLI has `--trained-efficiency`, `--trained-outcome` and
  `--trained-base-outcome`. It has nothing for prime, while `design()` accepts `prime_efficiency_scorer` and
  `DeepPrimeAdapter` sits in the registry with a card. Three trained-model opt-ins, one missing, on the
  chemistry the project leads with.
* **`--allow-ng` / `--allow-spry` on the web API.** I added them to `design()` and the CLI last round and
  did not look at the other shell. R159's own lesson, one round old, applied to me.
* (`build`, `clinvar`, `hgvs` and friends turned out to be genuine non-gaps — the CLI resolves the variant
  before calling `design()`, and the web API does it server-side.)

The durable part is not the two flags. It is that the parity is now a test: every `design()` parameter must
be forwarded by each shell or recorded with the reason it is not. Writing those reasons out was itself
worthwhile — the web API's file-backed exclusions (`gnomad`, `haplotypes`, `patient_vcf`, `encode_tracks`)
are a deliberate refusal to accept client-supplied filesystem paths on a server, and that reasoning now sits
next to the check rather than in a commit message from twenty rounds ago.

**Lesson: "library is truth, the shells are thin" is a claim about a boundary, and boundaries are exactly
where a parameter goes missing without anything failing. Three shells and one core means three chances to
forget, each invisible from the others — and the round that fixes one is the round most likely to create the
next, because the new parameter only gets added where you were already looking.**

## Round 161 — the third shell

R160 pinned parity for two shells and named the risk in its own lesson: three shells and one core means three
chances to forget. The third is the cohort path, so I went looking there before anything else.

`design_many` itself is clean — it takes a `design_kwargs` passthrough, so no parameter can go missing by
construction. The gap is in the CLI command above it. Diffing `aforge design --help` against
`aforge batch --help`:

    in design, not in batch: --allow-ng --allow-spry --cell-context --chemistry --format --out
                             --render-candidates --trained-base-outcome --trained-efficiency
                             --trained-outcome --trained-prime

Three of those are output shaping and belong to `design` alone — `batch` writes a directory and a manifest,
not one rendered document. The other eight are design options, and the cohort is precisely where they matter
most: it is the run someone starts and walks away from. A user could not select a trained model for a whole
VCF **by any means**, config file included. `--chemistry` and `--cell-context` were subtler — batch read them
from the config file and forwarded them correctly, so they were honoured if you knew to write TOML and
invisible from `--help`, which is a parity gap that looks like a feature to whoever wrote it.

All eight added, and the parity pinned with the same documented-exception shape as R160's.

One thing worth recording plainly. The helper that reads a subcommand's options needs to walk the Typer tree,
and I wrote `assert isinstance(sub, click.Command)` — the exact trap R144 diagnosed and wrote into this log
and into `project.md`, where a TyperCommand is not an instance of the visible click classes. It failed
immediately, so it cost a minute rather than six rounds. But knowing the rule, having written the rule, and
still reaching for `isinstance` says something about how much a written lesson actually protects you: it
turns a silent wrong answer into a loud one, which is most of the value, and it does not stop you making the
mistake.

**Lesson: when a lesson names a risk in the abstract ("three chances to forget"), the next round should spend
its first five minutes on the specific instance the lesson predicts. R160 wrote that sentence and stopped at
two shells; the third had eight missing options waiting. A lesson that is not immediately cashed out is a
prediction nobody acted on.**

## Round 162 — the request is the disclosure

Started the web app and used it, which I had not done this session. The UI works; R157's prime diagnosis
reaches the browser; the report renders. Then I read the DOM rather than the page, and found this:

    scriptSrcs: ["https://cdn.plot.ly/plotly-2.35.2.min.js", "(inline 450 chars)"]
    sandbox:    null
    plotlyInFrame: "object"

Every rendered report pulls Plotly from a CDN. The README, the deployment guide and the served page itself
all promise *"no outbound network call"* and *"the served frontend loads no third-party scripts"* — and the
frontend embeds the report in an **unsandboxed, same-origin** iframe, so that third-party script runs with
the application's privileges. `plotlyInFrame: "object"` is the proof the request actually went out.

This was not an accident, which is the interesting part. `report/html.py`'s docstring defends it: *"the
Plotly library is pulled from its CDN (a static script, never sequence data)"*. And a test **pinned** it —
`assert PLOTLY_CDN in html`. So the repository contained two tests asserting opposite things about the same
page, both passing, because R151's guard scanned `web/frontend/` and the report is generated somewhere else.
I wrote that guard two rounds ago and scanned a *directory* when the claim is about a *surface*.

The reasoning in that docstring is the flaw worth naming: "never sequence data" answers a question nobody
asked. A request to a CDN from a clinician's browser at the moment they analyse a patient variant discloses
that it happened, to whom, and when, before it discloses anything else. The payload is not the point.

The fix used what was already here: `alleleforge.viz.svg`, a dependency-free SVG renderer written for the
docs figures, with escaping and color validation already in it. Both charts are now inlined SVG; a rendered
report contains **no script element at all**, which is a stronger property than the escaping tests it
replaced were defending — those tests protected a `<script>` payload against a hostile ancestry label, and
there is now no script element to break out of. Verified live in the browser: zero scripts, zero off-origin
requests, chart present.

**Lesson: a guard scoped to a directory tests the directory. R151's check passed while the exact thing it
forbade was being emitted by a file one package over, because I defined its scope by where files live rather
than by what reaches the user. When writing a guard for a claim about "the page", enumerate everything the
page is assembled from — and when a docstring argues *for* the thing a headline promise forbids, that is
not a nuance, it is two documents disagreeing where only one is read.**

## Round 163 — the rest of what the page is assembled from

R162's lesson said to enumerate everything the page is assembled from, so I did the enumeration properly
this time instead of stopping at the defect I had found.

The PDF writer is clean — no URI actions, no external references, nothing fetched. Recorded.

The frame is not. `<iframe id="report" title="Design report" hidden>` — no `sandbox`. The report is
server-generated HTML built from user-supplied strings (the variant, ancestry labels, chemistry names), and
`srcdoc` in an unsandboxed frame runs with the *application's* origin. Everything in that report is escaped
and, as of last round, it contains no script element at all — so this is not a live exploit. It is the
difference between "an escaping bug in the renderer would be a report defect" and "an escaping bug in the
renderer would be an application compromise", and the frame was on the wrong side of it.

Sandboxed with `allow-popups allow-popups-to-escape-sandbox` — everything denied except a link opening in a
new tab, since the report carries one external link to JBrowse. That link also gained
`target="_blank" rel="noopener noreferrer"`, because a sandboxed popup that can reach `window.opener` gives
back some of what the sandbox took away.

Verified in the browser rather than by reading: the report renders, `contentDocument` is now `null` from the
parent (opaque origin), and `performance.getEntriesByType('resource')` shows no off-origin request.

**Lesson: two rounds in a row found the same class of thing — not a wrong computation but a wrong *context*
for a correct one. The CDN script and the unsandboxed frame are both about where code runs and what it can
reach, and neither is visible from any amount of reading the Python. The browser's own view (the DOM, the
resource timeline, `contentDocument`) is the only place these show up, and it took starting the server to
look. For a project that ships a web surface, "run it and inspect the page" is a distinct audit lens from
"read the renderer".**

## Round 164 — making the promise a control

R162 found the report fetching a CDN script; R163 sandboxed the frame it ran in. Both are fixes to
*instances*. The structural question is why either was possible, and the answer is in the response headers:

    HTTP/1.1 200 OK
    server: uvicorn
    content-type: text/html; charset=utf-8

That is all of them. No `Content-Security-Policy`, no `X-Content-Type-Options`, no `Referrer-Policy`, no
frame controls. The project's promise that the frontend loads no third-party scripts was carried entirely by
prose and by whoever last read the renderer — which is exactly how it came to be false for however long that
Plotly tag had been there.

Added a fixed header set. The clause that matters is `script-src 'self'`, with no inline and no `eval`
allowance; inline *styles* are permitted because both the shell and the report carry a `<style>` block, and
that is the half that does not matter. The rest is ordinary hardening: `object-src 'none'`, `base-uri 'none'`,
`form-action 'none'`, `frame-ancestors 'none'`, `nosniff`, `no-referrer` (a local deployment's URL is not
JBrowse's business), `X-Frame-Options: DENY`.

The part worth verifying rather than assuming is that this reaches the *report*, which is injected as
`srcdoc` rather than fetched. A `srcdoc` frame inherits its parent's policy, so it should — and it does. I
injected `<script src="https://cdn.plot.ly/plotly-2.35.2.min.js">` into a probe frame in the running app and
checked the browser's own network log:

    read_network_requests(urlPattern="plot.ly") → No network requests recorded.

So R162's defect is now impossible rather than merely fixed: reintroducing that script tag into the renderer
produces a blocked load, not a silent third-party request.

**Lesson: fixing an instance and installing the control are different pieces of work, and finishing the first
makes the second feel done. Two rounds removed a CDN script and sandboxed a frame without either asking why
the browser had been willing to fetch from a CDN in the first place. When a promise is enforced by "someone
would notice", the fix is not a better reviewer — it is to move the promise somewhere that refuses.**

## Round 165 — measuring the thing that is blocked

The README's roadmap has exactly one track marked "not started": R6, the v1.0 release criteria. Everything
else is "in progress" and blocked on real weights, real corpora, or a posted preprint. So R6 looked like the
only unblocked work left, and it is not — its five criteria are themselves gated on R0/R1/R2/R5.

What *is* unblocked is that nothing measures them. `SPEC_V2.md` lists five conditions and the only way to
answer "how close are we" was to read five bullet points and estimate. That is the shape R156 named: a
checklist nothing checks. And it matters more for a blocked criterion than an unblocked one, because a
blocked item and a forgotten item look identical from the outside for as long as nobody looks.

The measurement, which I had to get right rather than merely produce:

    [open] R0     1/12 model cards with a source URL pin a checkpoint hash; 1/8 datasets
    [open] R1+R5  0/5 benchmark datasets are real corpora
    [MET ] R2     4 test module(s) exercise the native path
    [open] R5     the calibration study runs end to end — over synthetic inputs
    [open] R5+R0  draft present; DOI not recorded in CITATION.cff

Two honesty problems in my own first draft, both of the kind this report exists to avoid. It counted all 17
model cards as needing a pinned hash and reported **1/17** — but five are heuristic baselines with no
artifact to download and nothing to pin, so the honest denominator is the twelve that name a source. And its
R2 evidence line claimed **16** native parity modules, because it grepped for the substring `native`, which
matches any test whose prose contains the word; there are four, found by the marker. A readiness report that
overstates its own evidence is worse than no readiness report, so both are now pinned by tests.

Also pinned: the report must have one criterion per bullet in `SPEC_V2.md`, so a sixth condition added to the
spec fails the suite until it is measured. And every unmet criterion must name what blocks it — "not met" and
"not met because the upstream artifact has not been frozen" are different facts, and only one of them is
anyone's to act on.

**Lesson: "blocked" is a claim with a shelf life. Four of these five have been blocked for the whole session
and are stated as blocked in the README, which is honest — but nothing would have noticed the day an upstream
artifact was frozen or a corpus became available, because the claim lived in prose that only changes when
someone remembers to change it. Measuring a blocked thing is not wasted work; it is how you find out it
stopped being blocked.**

## Round 166 — grading myself generously

R145's standing query is to audit the artifacts the audit produces, and the newest artifact is one round old:
the readiness report. Reading its R2 check against the bullet it claims to measure —

    SPEC_V2: "The native bwt/kmer/haplotype kernels are on their hot paths with
              parity tests **and a recorded speedup** (R2)."
    my check: met = bool(parity)

It printed **MET** on half the criterion. The verdict is correct — `scripts/native_speedup.py` exists, the
README cites its numbers — but I did not check that, and the one criterion my report graded as passing is the
one it graded least carefully. That is not a coincidence: the criteria I expected to be open got scrutiny
because I was writing down why they were blocked, and the one I expected to pass got a single `bool()`.

Both halves are graded now, and the general form is pinned: each criterion's summary must name every conjunct
its spec bullet names, so a criterion cannot be silently narrowed to the part that passes.

The check also surfaced something I deliberately did **not** decide. R2 is described in three places: its
`SPEC_V2.md` header says "◐ in progress", all four of its deliverables underneath say "(◐ landed)", and the
README table says "in progress". Either the track has scope nobody wrote down, or it is finished and two
documents are stale. Declaring a roadmap track complete is a release-scope judgment that belongs to the
maintainer, not to an automated pass, so it is flagged with the evidence rather than resolved.

**Lesson: a check is least rigorous exactly where it returns the answer you expected. Four criteria I
believed were blocked got carefully sourced evidence; the fifth, which I believed was met, got one boolean —
and it was the only one where being wrong would have been an overclaim rather than an understatement.
Reviewing a report's *passing* rows is worth more than reviewing its failing ones.**

## Round 167 — scope, not mutations

R166's lesson was that a check is least rigorous where it returns the expected answer. The generalisation:
mutation-checking proves a guard detects *the mutation I chose*, not that its **scope** matches the claim. R162
is the proof — the frontend guard passed its mutation while missing the report entirely, because I had scoped
it to a directory.

So I re-read my own guards for scope rather than for correctness, and the shell-parity check was scoped to
`design()`. The off-target engine — the project's differentiator — had no parity check at all. Diffing
`search()` against both shells:

    search() accepts, CLI never forwards: cache, genome_index, pam, scorer, spacer, use_fm_index
    search() accepts, web cannot request:  … scorer, cache, genome_index, use_fm_index …

`spacer` and `pam` are positional, fine. The real one is **`scorer`**: three specificity scorers are
implemented, carded and cited, and selectable only by importing the class. MIT was unreachable from every
shell — and so was the Cas12a analog, which is a different nuclease's scoring sitting in the package with
nothing able to ask for it. The report has always *named* which scorer produced its numbers; the user could
not choose.

Exposing it found a second defect immediately, which is the argument for exposing things. `--scorer mit` on a
20-nt spacer failed with **"MIT score requires 20-nt spacers"**. The spacer is 20 nt. The message is about the
*alignment*: a bulge changes the length, and MIT is undefined for a gapped alignment, so the default bulge
budget kills it partway through the scan with a complaint about an input that is already correct. Now refused
before the scan, naming the flags that fix it, and the underlying error names the alignment.

The remaining gaps — the cross-run off-target cache and the prebuilt whole-genome FM-index, both R4
deliverables, both library-only — are now *recorded* with reasons rather than silent. That is the honest
state: they need a path option and a session to hold an object, which is a design decision, not an omission I
should make unilaterally at the end of a round.

**Lesson: a guard has two properties and mutation testing only checks one. "Does it fire when the thing it
watches breaks" is not "does it watch everything the claim covers", and the second is where the misses live —
R162's directory-scoped scan, and this round's `design()`-scoped parity check that left the differentiator
unguarded. After writing a guard, state the claim in one sentence and ask what else that sentence covers.**

## Round 168 — five hundred rows that say `ok`

Ran the cohort path end to end and read its outputs as a user, which I had not done — R134 exercised resume,
not the artifacts. Four variants, one deliberately bad:

    chr7:3004:A>G  ok  best=base_abe  eff=0.20 [0.05,0.35]  n=1  !gc-out-of-band…
    chr7:3010:T>A  ok  best=-  eff=-  n=0
    chr7:9999:A>G  error  ValueError: reference mismatch …
    exit=0

Two defects, and the second is the one I nearly missed because it is an absence.

**The `n=0` row says nothing.** Three rounds ago I taught the verticals to explain an empty result, and the
single-variant report now prints the full reason — which chemistries were routed out, which rejected every
protospacer and for what. The cohort summary keeps eleven fields about the *recommended candidate* and none
about why there isn't one. This is the R138 pattern, and it is worse here than anywhere: a cohort is the one
surface where a reader cannot re-run the item by hand, because there are five hundred rows and forty of them
say `ok, n=0`. The reason now travels, flattened onto one line so it survives a TSV cell.

**`exit=0` with a failed item.** Per-item isolation is a real feature and I want to keep it: the run
completes, the manifest is whole, one bad variant does not abandon the other four hundred. But that is an
argument about *continuing*, not about what to report at the end. A 500-item run where 200 errored exited
successfully, so nothing driving this — a script, a CI job, a `&&` — could tell. Every sibling command in
this repo already signals through the exit code. Two existing tests pinned the old contract on listings that
deliberately contain a bad variant; both updated, with the reason.

**Lesson: "the run completed" and "the run succeeded" are different facts, and a tool that isolates failures
is under more obligation to distinguish them, not less. Isolation makes the failures survivable and therefore
easy to stop reporting. Anything that continues past an error should be asked separately what it returns.**

## Round 169 — the word for a bug

R168 ended on: anything that continues past an error should be asked separately what it returns. The design
path continues past an error too — `_run_chemistry` catches per vertical, so one broken chemistry does not
lose the menu. So I asked what it reports, by making a vertical raise:

    - prime: skipped (RuntimeError: boom: a real defect)

"Skipped" is the word a chemistry gets when it legitimately does not apply. A crash gets the same one.

The mechanism was there and correct — `_EXPECTED_DESIGN_FAILURES` exists precisely to separate the two, and
its comment says a real bug must not be *"silently swallowed behind an 'eligible but empty' note"*. The list
contained `RuntimeError`, which is how most Python defects reach a boundary, so the promise was defeated for
the commonest case by its own allow-list.

It was there for a reason, and finding the reason is what made the fix safe: `ConsentError`, `ChecksumError`,
`LicenseError` and `CardError` are all `RuntimeError` subclasses, and six adapters raise a bare `RuntimeError`
to mean "this optional dependency is not installed". Catching the base class was the shortest way to let all
of those degrade gracefully. R141's unification made naming them individually possible; the six bare raises
became a new `MissingDependencyError`, which is still a `RuntimeError` so no existing handler breaks.

The exclusion matters as much as the inclusion. `CacheIntegrityError` and `FMIndexIntegrityError` are also
`RuntimeError` subclasses, and they mean corruption or tampering — R142 turned the cache's verification on
precisely so those surface. Degrading them to "skipped" would have quietly undone that, and an allow-list
written by exception *type* rather than by *meaning* is how that happens without anyone deciding it.

One existing test simulated "model checkpoint unavailable" by raising a bare `RuntimeError` and asserting
"skipped" — the same conflation, encoded. The scenario is right; it now raises what the real code raises.

**Lesson: an allow-list of exception types is an allow-list of *meanings*, and the two drift apart as soon as
one type carries several meanings. `RuntimeError` meant "a dependency is missing" at six call sites and "a bug"
everywhere else, and the list could not tell. When catching by type, check what else in the codebase raises
that type — and when a base class is caught, what its subclasses mean.**

## Round 170 — the sibling I skipped one round ago

R169's lesson said: when catching by type, check what else raises that type. Run as a sweep over every broad
`except` in the tree, it lands immediately on two handlers in the CLI:

    except RuntimeError as exc:  # e.g. a VCF input but cyvcf2 is not installed
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.UNAVAILABLE)

One wraps the patient-VCF reader, the other wraps the *entire cohort run*. Both translate the exception into
"a feature is not installed" and exit `UNAVAILABLE`. So a genuine defect inside `iter_vcf`, or anywhere in
`design_many`'s machinery, was reported to the user as an installation problem — advising them to install
something that was already installed, which is worse than a traceback because it sends them somewhere wrong.

Narrowing them needed the conversion R169 started, and checking that turned up the real finding of this
round: **R169 converted six missing-dependency raises and left three.** The six were all under `scoring/`,
which is where I was looking; the VCF reader, the Cas-OFFinder adapter and the Parquet export were not. So
narrowing the handler would have *broken* the cyvcf2 path — the exact case its comment names — because the
raise it was written for had not been converted. R158's "which siblings did I just skip?" question, asked one
round too late again.

Three sites converted. `_native.py`'s version-mismatch `RuntimeError` is deliberately left alone: a native
extension built against a different version is a broken build, not an absent package, and telling someone to
install something would be the same mistake in a new place.

The durable part is a check rather than a lesson: any `raise RuntimeError` whose message contains "install",
"not on PATH", "requires the optional" or the like now fails the suite. That is the check that would have
caught R169's miss on the day it happened.

**Lesson: a conversion sweep is only as complete as the directory I happened to be reading. Twice now
(R158, R170) the missed siblings were the ones outside the package I had open — and both times the next
round found them by accident, while narrowing something that depended on the sweep being finished. When a
change has the form "convert every X to Y", the commit is not done until a check enumerates X.**

## Round 171 — reading the leave-behind

The PDF is the artifact that travels: printed, mailed, stapled to a protocol. I had checked it for external
references (R163) and never actually read one. So I rendered one and read it.

Most of it is good, and this session is visible in it — R157's prime diagnosis, R153's scorer citation,
R155's intended allele shown at p=0.048 marked `(intended)`, R136's coordinate note in the provenance
footer. Then the ranking line:

    ABE8e sgRNA on + strand; P(exact)=0.05 … [eff 0.20 [0.05, 0.35], clean 0.05, safe 0.00, simple 0.90]

**`safe 0.00`** — on a candidate the same page marks `recommended` and `Pareto-optimal`. The safety objective
is at its floor, and the caveats printed above it are about spacer GC content and bystander bases. Nothing on
the page says why safety is zero. The reason is two lines up: `off-target sites: 2 (specificity 0.376)`, one
of them scoring **1.000** — a perfect match elsewhere in the genome.

The only off-target caveats were `offtarget-not-searched` and `population-offtarget`. There was **no flag for
a high-scoring site**. A guide whose search ran and found a plausible cut somewhere else got a lower ranking
number and no label — and the ranking is a comparison, so when it is the only candidate it is still returned
`recommended`, with the hazard visible only to a reader who knows that `safe 0.00` and `specificity 0.376`
are the same fact.

Checking the siblings found the second half. cas9 and the base editor emit `population-offtarget`; prime does
not — and the reason is not an oversight in a list, it is that prime's `_flags` receives a **boolean**
`run_offtarget` rather than the report. The information never reached the flag builder, so no amount of
reading that function would show what was missing.

One shared helper now, used by all three, with the score carried in the flag so the reader judges rather than
trusting the band. The R98 guard caught me immediately for adding a hazard flag with no caveat text behind
it, which is the check working as intended.

**Lesson: a number at its floor is a claim, and nobody reads it as one. `safe 0.00` was correct, derived
correctly, printed honestly, and consumed correctly by the ranking — and it still failed to warn anyone,
because a reader scans the section headed CAVEAT. When a value is at the extreme of its range, ask whether
anything says so in the register a reader is actually reading.**

## Round 172 — the other number at its floor

R171's lesson: when a value sits at the extreme of its range, ask whether anything says so in the register a
reader is actually reading. The same PDF has a second one, on the line above the off-target hazard:

    P(intended) = 0.05

Of everything this reagent produces, 5% is the edit that was asked for. It is the number the whole design
exists to serve, and it had no caveat at *any* value.

Getting this right meant not inventing a threshold. "Low `P(intended)`" needs a cutoff nobody can defend —
0.05 is disastrous for a therapeutic and unremarkable for a screen. But the data already makes a comparison
that needs no cutoff: **is the single most likely outcome the requested edit?** In this report it is not —
`A6G` at 0.288 is a bystander-only edit and the requested `A4G` is seventh at 0.048. That is a fact about the
reagent, not a judgement about how small a probability is too small, and it is the one a bench scientist
needs before ordering oligos. The flag carries `P(intended)` so the reader sizes the gap themselves.

The wiring repeated R171's root cause exactly, which is why it is worth recording twice. Neither `_flags` in
cas9 nor in prime received the outcome — same as neither receiving the off-target report last round. A flag
cannot be forgotten from a list it was never able to compute, and reading the flag builder shows nothing
missing; the absence is in the *signature*. Two rounds, two hazards, one shape.

Also worth noting: my first test fixtures were rejected by `EditOutcome`, which validates that its allele
probabilities sum to ~1.0. The model defended its own contract against a sloppy test of mine.

**Lesson: when a caveat needs a threshold, look for a comparison instead. A threshold is a number someone has
to defend and everyone has to trust; a comparison — "X is more likely than Y" — is derived from the data and
survives disagreement about what counts as bad. The two hazards this round and last both turned out to have
one available, and only one of them needed a band at all.**

## Round 173 — "spec defaults"

R172 ended on preferring a comparison to a threshold. The obvious follow-up is the thresholds that already
exist, so I listed every constant in the tree whose name suggests a judgement and read what each says about
itself.

Most are fine, and some are exemplary. `CLOSE_NICK_NT` spends five lines explaining that it is "a
deliberately conservative floor well inside that, not a fitted threshold", that it drives an annotation only,
and that turning nick distance into a score would need calibration data the project does not have.
`OOD_MIN_HALF_WIDTH` derives its value from an inequality. Someone took this seriously.

Then:

    #: Report any site scoring at or above either threshold (spec defaults).
    DEFAULT_CFD_THRESHOLD = 0.20
    DEFAULT_MIT_THRESHOLD = 0.10

"Spec defaults" reads as though a specification somewhere derived them. These are the most consequential
numbers in the off-target engine: a site below them is not deprioritised, it is **absent** from the report.
`DEFAULT_MAF_THRESHOLD` and `GC_BAND` were the same — a description of what they do, nothing about what kind
of number they are.

The failure here is one-directional, which is what makes it worth a round. A reader who assumes a number is
sourced does not question it; a reader told it is a project choice can decide whether it suits them. Each now
says so, along with the fact that lowering it only ever adds sites — the direction of the error matters more
than the value.

What I did **not** do is cite anything. Each of these plausibly has literature behind it, and asserting a
source I have not checked against the paper is precisely the failure this labeling exists to prevent — the
same judgement as the epegRNA motifs and the PE3 threshold before it. Flagged for a human, with the note that
a citation satisfies the new test as readily as the current wording.

**Lesson: "(spec defaults)" is the kind of parenthetical that answers a question by appearing to. It names no
spec, cites no source, and reads as authority — and it sat above the two numbers that decide what a safety
report contains. When a comment explains a constant, check whether it explains where the *value* came from or
only what the value does; those are different sentences and only one of them is provenance.**

## Round 174 — zero as a placeholder

R173 asked whether a constant's comment explains where the *value* came from. The same question, asked of the
model cards' `metrics` field, has a sharper answer.

Most of what those cards report is descriptive and honest — parameter counts, cell types covered, context
windows. Three report a *performance* number:

    spearman_validation: 0.0  # populated when CRISPR-Bench scores it (Phase 14)
    spearman_validation: 0.0  # not fitted/scored; transparent geometry prior

The comments are correct and they are in the YAML, which no consumer reads. `card.metrics` returns
`{'spearman_validation': 0.0}`, and a card is precisely the artifact meant to be read *instead of* the source.
So the shipped claim is that these models have zero rank correlation with the truth — and 0.0 is not a neutral
placeholder for a correlation, it is the worst attainable value. On the `rule-set-3` card, which describes a
published model with real numbers in its citation, the card asserted the model has no predictive value.

This project already wrote the rule, in its own cohort summariser: *"Defaulting an unmeasured axis to it makes
'we did not look' indistinguishable from 'we looked and it is clean', on the one axis where that confusion is
dangerous."* Same repository, same principle, opposite direction — here the placeholder is not reassuring but
damning, which is why it survived: nobody worries about a number that understates.

The key is gone. The two baselines already said what they are in `known_failure_modes`, so nothing was lost
there; `rule-set-3` did not, and now states that AlleleForge has not independently scored it — *"the card
reports no accuracy metric because none has been measured here, not because it measured zero."* The guard
rejects any metric whose name is a performance measure and whose value is exactly 0.0.

**Lesson: a placeholder survives in proportion to how flattering it is *not*. R171's `safe 0.00` and this
`spearman 0.0` are the same defect and both went unnoticed for the same reason — a number that makes the
project look worse reads as modesty rather than as a bug. Check the pessimistic placeholders too; they are
just as false, and nobody is motivated to find them.**

## Round 175 — the sweep that mostly came back clean

R174's lesson — a placeholder survives in proportion to how *unflattering* it is — as a sweep over every
field defaulting to an extreme of its scale. Two clean bills and one real find, which is the honest shape of a
well-worked seam.

**`subthreshold_score_sum = 0.0`** is the dangerous direction: zero means "no hidden risk below the reporting
cut-off", the reassuring extreme on a safety axis. It is written at exactly one place, always, and every
merge path uses `model_copy` rather than rebuilding field by field — the R-era fix for `_merge_offtarget`
still holding. Clean.

**`outcome_shown_mass = 0.0`** likewise: it is set alongside the alleles it summarises, and R155 made its
arithmetic follow the rows actually shown.

**`progress: float = 0.0`** is the find, and it is not about the default. The field takes three values —
`0.0` queued, `0.1` running, `1.0` done — and the status endpoint returned a bare `dict[str, Any]`, so it
arrived at a client with no description and no OpenAPI schema. A client that renders it as a percentage shows
**10% for the whole of a cohort run** and then jumps to 100%. The number is not wrong; its *shape* is
misrepresented, which is the same defect as a placeholder wearing the clothes of a measurement.

A process note worth keeping. My first mutation of the fix — deleting `response_model=JobStatusResponse` —
left the test passing, and I nearly recorded that as a weak test. FastAPI infers the schema from the
**return annotation**, so removing the keyword mutated nothing. Changing the annotation failed the test
immediately. A mutation that does not mutate looks exactly like a test that does not test.

**Lesson: verify the mutation, not just the test's reaction to it. "I broke it and the test passed" has two
readings and I have now hit the wrong one twice (R151's socket patch, this). Before concluding a guard is
weak, confirm the thing you edited is actually load-bearing for the behaviour you meant to break.**

## Round 176 — the claim the project is named for

R175 came back mostly clean, which the log's own history says means rotate the query. So: an area I had not
opened at all in ninety rounds — `scoring/uncertainty.py`, where "honest uncertainty" stops being a principle
and becomes arithmetic.

The implementation is good. Split conformal is textbook-correct, the OOD path refuses to *narrow* an interval
it is not allowed to calibrate, and the isotonic and evidential paths are careful. One branch is not:

    rank = min(math.ceil((n + 1) * self.level), n)
    # ... "too few points to strictly guarantee, fall back to the largest residual"

The fallback is right — the largest residual is the most conservative finite scale. What it guarantees is
`n/(n+1)`. Three calibration points and a 0.95 request:

    interval_level=0.95   calibrated=True   notes=()

That is a 75% interval labelled 95%, carrying the flag this project treats as *"the coverage was earned"*,
with nothing said. The comment in the source knew; the artifact that leaves the process did not — and this is
the module the whole project is named for. A strict 0.95 needs 19 points; the calibration study runs on
single-digit synthetic sets.

Intervals now carry the level they earn, plus a note naming the shortfall and the size required, and
`min_calibration_size` is public so a caller can size a set *before* fitting rather than discovering it after.

I then got the helper wrong in a way worth recording. `ceil(level / (1 - level))` is the obvious closed form
and it is wrong in binary floating point at exactly this project's default level: `0.8 / 0.2` is
`4.000000000000001`, which rounds to 5 and overstates the requirement. Solved by searching the actual
condition instead — cheap, exact, and it fails the parametrised test at 0.8 and 0.9 when reverted to the
algebra.

**Lesson: a comment that acknowledges a limitation is not a disclosure — it is a note to whoever is already
reading the source, which is nobody at the moment the number is used. Every honest sentence in that function
was present and correct, and none of it was attached to the object that travels. Ask where a caveat *lives*,
not whether it was written down.**

## Round 177 — bounding the previous find

R176 found a real defect in `scoring/uncertainty.py`, which makes the neighbouring code
worth reading rather than assuming: a module that mislabels one guarantee is a module
where the *shape* of that mistake might repeat. Two candidates, both clean, both now
pinned rather than left as a check I did once.

**The OOD detector on a degenerate reference.** Its threshold is a quantile of the
reference's own nearest-neighbour distances, so with one or two points it collapses.
The question is which way. Measured: a single point gives threshold 0.0 and declares
everything OOD; two identical points the same; two distinct points admit only inputs
within their separation. In every case a far input is refused. It errs toward "I do not
vouch for this", which is the direction a safety flag has to fail in, and the opposite
of R176's conformal shortfall where too little data produced a *stronger* claim.

**The isotonic calibrator.** It returns plain floats, never `Prediction` objects, so it
cannot mint `calibrated=True` on thin data at all — `Prediction.calibrated_by` is the
only path to that flag and isotonic never calls it. The design already prevented the
failure I went looking for.

Both are now tests. A verification done once during an audit is worth about as much as
a comment: it describes a moment, and the thing it describes can change the next day.

**Lesson: after a find, read its neighbours — but expect most of them to be clean, and
write the clean ones down as tests rather than as prose. R176's defect and R177's two
non-defects are the same question asked three times ("what does this claim when the data
is too thin?"), and the value of the two negatives is that they now stay negative.**

## Round 178 — fixing the shell instead of the core

Rotating again, to the population/haplotype modules — the differentiator, and code I had audited *around*
without opening. `_strengthens` turns out to be carefully reasoned: an alt hit is nominated when it is created
or beats the reference on *either* score or edit count, explicitly as the safety-maximizing union, with the
reasoning written down. Good code.

But it calls `scorer.score(...)` on bulged hits, and R167 established that the MIT scorer cannot score a
gapped alignment. R167 refused that combination — **in the CLI**. So:

    search(spacer, pam, reference=ref, scorer=MitScorer(), dna_bulges=1)
    → ValueError: the MIT score is defined only for an ungapped 20-nt alignment;
      this one is 19 nt

The library, the cohort path and any future web caller all still walked into it, and the message is about the
*alignment* — a reader holding a valid 20-nt spacer has no way to connect it to the bulge budget they set.
I had spent several rounds finding capabilities stranded in the library and reachable from no shell; this is
the mirror image, and I created it two rounds ago by putting a rule where I happened to be typing.

Moved into `search()`, and the CLI's copy deleted rather than left as a second implementation of the same
rule — `project.md`'s standing complaint about local versions of things that already exist.

**Lesson: a validation belongs at the narrowest point every caller passes through, and "where I noticed the
problem" is almost never that point. I found this one from the shell, so I fixed it in the shell; the
question that would have caught it is the same one shell-parity asks in the other direction — not "can every
caller reach this capability?" but "does every caller reach this guard?"**

## Round 179 — the same question, one round later

R178's lesson ran as a sweep: which validations live in a shell that every caller should reach? The CLI's
`_validate_regions` is the next one, and its own docstring explains why it matters — *"a silently dropped
region means the search covered less than was asked for, and a smaller search reports fewer off-targets, the
direction that reads as safer and is not."* That reasoning is right and it protected one of three callers.

From the library:

    KeyError: "unknown contig 'chrNOPE'"

against the CLI's version, which names the offending contig, lists what the reference does have, and says
what the consequence would be. A panel built against another assembly, or against Ensembl naming when the
reference is UCSC, is the ordinary way this happens — it is the *expected* user error, and the library met it
with the least informative failure available.

Moved into `search()`. The CLI keeps an early exit — failing before a reference is loaded is genuinely better
for a shell — but it now calls the engine's check instead of holding its own copy, since two implementations
of "is this contig known" will drift and the engine's is the one the web API and the cohort depend on.

A note on my own test. The first version asserted that the CLI's source *contains* the helper's name, and it
kept passing when I replaced the call with `pass` — the import line still carried the name. A source-grep
test for "does this call that" is not a test of behaviour; rewritten to actually invoke it and assert the
refusal.

**Lesson: two rounds, two guards in the wrong place, both found by asking the same question — and the second
was findable the moment the first was fixed. A lesson gets one round of attention when it deserves a sweep.
After fixing an instance, run the query over the whole tree *before* moving on, because that is the only
moment the question is fully loaded.**

## Round 180 — finishing the sweep

R179's lesson was to run a query over the whole tree at the moment it is fully loaded, rather than finding the
next instance a round later. So: every rule the CLI enforces, listed, and each asked whether the library owns
it.

Most are genuinely CLI-shaped — file paths, option grammar (`--format requires --out`), enum parsing. One I
expected to find was already fine: `DEFAULT_REGISTRY.get("nope")` raises
`KeyError: "unknown dataset 'nope'; known: (…)"`, the full actionable message, and the CLI merely re-wraps it.

One was not. `--encode-tracks` and `--chromatin-track` "must be given together" per the CLI. From the library,
passing only the name:

    design(..., chromatin_track="DNase")   # no encode_tracks
    → 1 candidate, no adjustment applied
    → provenance config_snapshot: {"chromatin_track": "DNase"}
    → rationale: "chromatin track 'DNase' was supplied but covers none of the candidate loci"

Three separate misstatements from one missing guard. The provenance records a chromatin-aware run that was
not. The rationale asserts the track "was supplied" when nothing was. And it blames *coverage*, sending a
reader to inspect a track file that does not exist — the note itself is R118's work, correct for the case it
was written for and wrong for this one, because nothing distinguished "supplied and covers nothing" from
"never supplied at all".

Refused in `design()` now, where the cohort and the web API pass too.

**Lesson: three rounds of this question produced three findings, and the third was the only one I got to by
enumerating rather than by stumbling. The enumeration also produced a clean bill I would not otherwise have
recorded — the dataset lookup — which is worth as much, because it is the difference between "I checked" and
"I happened not to trip over it".**

## Round 181 — the sequence someone orders

Rotating to the highest-stakes output in the product: `report/oligos.py` produces the actual DNA a lab buys.

The construction is correct, and I checked it by hand rather than by reading — three spacers through
`sgrna_oligos`, overhangs stripped, bottom strand compared against the reverse complement of the top core.
`CACC`/`AAAC` per lentiGuide, the duplex anneals, the citation is on the scheme. No defect.

What the check surfaced is what happens *around* it. For a spacer not beginning with G the scheme prepends
one, because U6 needs it — so the ordered duplex encodes **21 nt** while every number on the page was
computed for the 20-nt spacer. The project knows: `SgRnaOligos.g_added` records it, and `no-5prime-g` is
deliberately classified descriptive rather than a caveat, with the comment "the cloning scheme prepends the
U6-start G automatically". That reasoning is sound.

But the fact travels unevenly. The HTML dumps the whole oligo record as JSON, so `g_added: true` is in there
somewhere. The PDF formats the block by hand — `top`, `bottom`, the prep note — and omitted it. The PDF is
the printable leave-behind; its own docstring says it "must carry the exact oligos to order… not just point
at the electronic report". It carried the exact oligos and not the one sentence explaining why they are
longer than the guide that was scored.

The note now names the prepend, both lengths, and the spacer the numbers belong to.

**Lesson: a hand-formatted view and a serialize-everything view drift, and the hand-formatted one is usually
the one people read. The HTML "renders" `g_added` only in the sense that a JSON blob contains it — which
satisfies a field-coverage check and no reader. When two surfaces render the same object by different
mechanisms, the field-by-field one is where a fact goes missing.**

## Round 182 — the half that cannot edit

R181's lesson said the hand-formatted view is where a fact goes missing, and the guard I had built in R156
covered the report models and not the oligo ones. Extending it found something much worse than the missing
sentence that prompted it.

`SgRnaOligos.donor` reached no renderer. For a precise Cas9 edit the repair template *is* half the reagent —
`oligos_for` pairs them deliberately, and the test that pins the pairing says outright that "returning only
the guide would hand the bench the half that cannot edit". The printable order sheet then did that: the guide
duplex, the prep note, and no donor sequence. Not even the word "donor". The candidate line above it reads
"+ HDR donor 100 nt", so a reader knew one existed and had no way to order it from the page they were
ordering from.

Two process notes, both about my own checking.

My first attempt to confirm the absence searched the PDF text for the donor sequence and found it — because
the fixture's donor and its spacer are both `ACGT` repeats. A coincidental match reported the bug as
absent. Re-run with a donor unlike the spacer, it is plainly missing.

Then the guard itself matched *nothing at all* under pytest while working standalone — a regex built by
f-string interpolation. I spent several minutes assuming the path resolution was wrong before replacing it
with plain substring checks. A checker that silently finds nothing looks exactly like a clean bill, which is
the failure mode this whole guard exists to prevent, reproduced inside it.

**Lesson: when confirming a bug's *presence*, a search that succeeds is not evidence — it may have matched
something else. I nearly closed this as a non-finding on a fixture whose two sequences happened to share an
alphabet. Construct the probe so a coincidental match is impossible, especially when the answer you get is
the convenient one.**

## Round 183 — one block, two surfaces

The last two rounds fixed the printable sheet twice: the prepended-G note, then the HDR donor. Both were
present in the HTML, in the sense that the HTML dumps the whole oligo record as JSON — which is exactly how
they went missing from the sheet without anyone noticing. A serialized object satisfies every "is this field
rendered?" check and is not something a reader reads.

So the HTML now renders the same lines the PDF builds. One block, one implementation, and the drift that
produced two rounds of findings is gone rather than patched twice.

The round's real content is the test I wrote for it, which was wrong in the exact way R182 had just warned
about. I asserted `"HDR donor" in page` — and it passed with the JSON dump restored, because the candidate
summary line above the block already reads *"+ HDR donor 100 nt"*. A search that succeeded, on the wrong
part of the page, one round after writing down that a search that succeeds is not evidence.

It only surfaced because I checked the mutation had actually applied (R175's rule) rather than accepting a
passing test as a weak one. Two process rules from the last eight rounds, both needed, both in the same five
minutes. The assertion is now scoped to the `<details>` block it is about.

**Lesson: the two failure modes compose. "Verify the mutation applied" and "verify the match is where you
think it is" catch different halves of the same illusion — a green test after an edit that did nothing, and a
green test after an edit that did something the assertion could not see. Neither alone is enough, and I have
now hit each of them within a round of writing them down.**

## Round 184 — the returns before the loop

Rotated to the input boundary and drove the resolver through its accepted forms — SNV, insertion, deletion,
MNV, delins, lower-case bases, an empty alt. Most behave, and two are worth recording: a lower-case reference
allele resolves correctly, and `A>` normalises to a left-anchored `TA>T` deletion, which is the VCF
convention and right.

One does not. `chr7:3004:A>A` — an edit that changes nothing — resolves cleanly, and the design reports:

    - prime: eligible but no actionable candidate enumerated — no candidate was examined

That is my own empty-tally placeholder from R157, and it is useless here. The enumerator knows exactly what
is wrong; the line that refuses it reads `if start_allele == desired_allele: return []  # nothing to write`.
R157 taught the enumeration *loop* to explain itself and I never looked at the three returns above it. A user
who typos a variant, or asks for a 60-base insertion prime editing cannot write, gets the placeholder rather
than the sentence sitting in the comment beside the return.

All three now name themselves. Checking them found a second, smaller thing in my own new text: the
"edit too large" branch trips on a long reference span *or* a long desired allele, and I had written "replaces
more reference bases", which describes an insertion of sixty bases as replacing more than one. Reworded.

**Lesson: an early return is a branch with a reason, and a mechanism that explains "why nothing was found"
has to cover the returns that happen before the search starts. I built the tally around a loop because the
loop was where I was reading — the same mistake as putting a guard in the shell where I noticed the problem
(R178). Both times the fix was one frame up from where I was looking.**

## Round 185 — the roads not taken

Swept the sibling enumerators for R184's silent early returns, immediately rather than a round later. cas9
has none — its scan returns whatever it finds. The base editor has one (`variant_class is not SNV`), and it
is unreachable from the design path because routing already excludes base editors for a non-SNV, with a
reason. Clean bill, and the check that produced it surfaced something one level up.

Routing prints `base_abe=no, base_cbe=no, prime=yes` and — when at least one chemistry *is* eligible — stops
there. The per-chemistry rationales exist; they were shown only for an empty menu, on the reasoning that
"an empty menu is the one case where the yes/no summary tells the reader nothing they can act on". That
reasoning is half right. `base_abe=no` is least actionable precisely for the reader who *needed* a base
editor — someone avoiding a double-strand break — who now has a prime candidate and no statement of why the
chemistry they wanted declined.

Making it always-on immediately showed why it had not been: the SpCas9 rationale is **540 characters**, a
full paragraph on why HDR is a last resort, and repeating it in every report drowns the result. The
reproducibility gate caught the change and printed the new rationale in full, which is how I saw the size of
it rather than discovering it later in a rendered report.

So: first sentence beside a real menu, full text where nothing is eligible and that text is the content.
162 characters instead of 540, and the eligibility clause survives.

**Lesson: I nearly reverted this outright when the first version made every report worse — and "the
information is valuable but this presentation is not" is a third option that is easy to skip past under a
binary framing. The gate showing me the *actual new output* is what made the middle path visible; without
it I would have shipped the paragraph or dropped the feature.**

## Round 186 — the ingest boundary

Rotated to the loaders that parse user-supplied files, and fed the gnomAD one deliberately broken rows:
negative frequencies, frequencies above 1, `NaN`, `inf`, zero and negative positions, empty and non-ACGT
alleles, lower-case bases.

It holds up. Every out-of-range frequency is refused with a message naming the offending field and the locus.
Non-sequence alleles (`*`, `<DEL>`) are skipped deliberately, with a comment noting that the ClinVar and
dbSNP loaders skip them identically — "the three loaders agree on what a usable row is", which is the kind of
consistency that is invisible until it is absent. A wholly-unusable file surfaces through
`sources_considered` as `gnomad: 0`, the "supplied and covered nothing here" signal from R116. Clean bill.

One property is correct in a way that would not survive a plausible tidy-up. `NaN > 1.0` and `NaN < 0.0` are
both False, so the obvious spelling —

    if af > 1.0 or af < 0.0: raise ...

— admits `NaN`, which then compares False against every MAF threshold and *silently drops the variant from
the search*, on the axis where a silent drop reads as safety. The validator is written `not 0.0 <= af <= 1.0`,
and the negation catches it. Nothing tested that distinction, and this project has already paid for it once
in `RankingWeights`, where a non-finite weight poisoned the composite the ranking sorts on.

So: pinned, for gnomAD and for the haplotype panel that feeds the same ancestry stratification. Rewriting the
check to the fragile form fails the test, which is the whole point of having it.

**Lesson: some code is correct because of how an expression is *shaped*, not because of a decision anyone
recorded. `not 0 <= x <= 1` and `x > 1 or x < 0` read as synonyms and differ on exactly one input. Those are
worth a test even when nothing is wrong today, because the next reader will see two spellings of the same
idea and pick the one that reads better.**


## Round 187 — a `NaN` threshold, reachable from the command line

R186 ended on a lesson about expression *shape*: `not 0 <= x <= 1` and `x > 1 or x < 0` read as synonyms and
differ on exactly one input. This round swept the tree for the fragile spelling. Every hit was on an integer —
mismatches, bulge budgets, array indices, sequence lengths — where `NaN` cannot arrive. A clean bill.

So the query rotated from *where is the spelling* to *where can a user put the value*. Three CLI options take a
float with `min=0.0, max=1.0`, and Click's range check is that same pair of comparisons:

    aforge offtarget ... --cfd-threshold -1    -> Usage error
    aforge offtarget ... --cfd-threshold 2     -> Usage error
    aforge offtarget ... --cfd-threshold inf   -> Usage error
    aforge offtarget ... --cfd-threshold nan   -> 3 site(s), worst score 1.000

Accepted. What it *did* then depended on nothing but the direction of the consumer's comparison, and the two
consumers were written in opposite directions:

* `if cfd < cfd_threshold and mit < mit_threshold: continue` is a **skip** test. `NaN` skips nothing, so every
  site was reported — three where the real threshold gives two — and the report's own provenance line read
  `sites reported at CFD >= nan`, naming a cutoff it was not applying. Over-reporting is the safe direction;
  claiming a threshold you are not applying is not.
* `max_af(populations) >= maf` is an **include** test. `NaN` includes nothing, so `--maf nan` produced a
  report with **zero population off-targets**. Measured on a fixture whose common variant creates a
  perfect-match PAM: `maf=0.001` finds it, `maf=nan` finds nothing, no error, no warning.

The second is the class this project keeps rediscovering — a real safety input inert on the axis it governs,
with a green suite (R10, R11) — so the fix refuses the input rather than picking a direction for it. The guard
lives in a small shared module and is called at the narrowest point every caller reaches, per R178/R179: in
`search()` for all three fractions, and in `enumerate_population_sites()` for `maf`, because that function is
exported and is where the mask actually happened. `inf` is caught by the same check: it is orderable, so the
shell already refuses it, but nothing stopped a library or web caller passing it to mean "report nothing".

All three guards were mutation-checked: dropping either call, or removing the offender's name from the
message, fails the new tests.

**Lesson: a validation that is *reachable* is worth more than one that is thorough. R186 found the fragile
spelling by reading code and concluded, correctly, that nothing was wrong. The same property was one
command-line flag away from silently emptying the population-safety section of a report. Sweep the input
surface, not only the source.**


## Round 188 — the report never said which chromosome

R187 ended on "sweep the input surface, not only the source." The obvious next boundary was coordinate
convention: VCF is 1-based inclusive, BED is 0-based half-open, internal hits are 0-based, and an off-by-one
in a printed locus sends a lab to the wrong base. The inputs turned out to be in good shape — every parser
converts on read, and an earlier round had already labelled `--region` and `--variant` in the CLI help.

So the query rotated to the egress. `GenomicInterval.to_one_based` is the declared converter for I/O
boundaries and has no callers in `src/` outside its own definition, which an earlier round had noticed and
answered by labelling the convention: the report's provenance block says "coordinates 0-based half-open." The
question nobody had asked was what coordinates it was describing. Rendering both fixture reports and searching
the entire page for a contig token:

    [prime_menu]    contig tokens in page: []
    [ancestry_menu] contig tokens in page: []

Not one. SpCas9 printed `cut 117` inside the reagent line — a bare integer with no chromosome. Prime editing
printed no genomic coordinate at all: five candidates differing only in RTT length, none saying where the edit
lands. Base editing gave a protospacer-relative window. The provenance block was carefully labelling the
convention of coordinates the report did not have.

`CandidateReport.locus` now carries `chr11:100-120 (+), cut 117` — read from whichever of the three
chemistries is placed, `None` when none is — and reaches the HTML page, the printable PDF and a new `locus`
column in the flat export, which a pipeline previously could not join to anything genomic. Four mutations, all
fatal, including dropping the PDF render specifically: R183's lesson is that the printable sheet is where a
field silently goes missing, and the assertion had to be scoped past the PDF's paren escaping to be real.

Then the README contradicted the fix. Its coordinate cheat-sheet had one row reading `HGVS (g.),
human-readable reports | 1-based`. HGVS is 1-based; the reports are 0-based half-open and say so themselves. A
reader trusting the table would read the new locus as 1-based inclusive and land one base off — precisely the
failure the locus exists to prevent. Row split, and pinned against `COORDINATE_NOTE`, because the table and the
note live in different files and had already drifted apart once.

**Lesson: labelling a convention is not the same as checking there is anything to label. The earlier round
added a correct, well-reasoned note about coordinates the report was not printing, and the note's presence is
what made the absence invisible — a reader sees a coordinate statement and assumes coordinates. When a fix is
a *statement about* the output, verify the output it describes actually exists.**


## Round 189 — the smaller search read as the safer guide

R188's lesson was that a *statement about* the output is worth nothing until you check the output it
describes exists. The natural next target was the other direction of the same idea: statements that exist and
are incomplete. `PROVENANCE_FOOTER_OMITTED` is a curated list of provenance fields the footer deliberately
skips, each with a reason, and it has exactly one entry — `config_snapshot`, excused as "rendered inline
beside the results."

The snapshot holds eight keys. `build_report` reads two of them (`intent`, `weights`). The other six —
`populations`, `run_offtarget`, `offtarget_regions`, `cell_context`, `chromatin_track`, `settings` — are read
by no renderer at all, so the footer skips them on the strength of an inline render that does not happen.

`offtarget_regions` is the one that matters, and its own comment in `designer.py` says why: *"A restricted
scan reports far fewer sites than a genome-wide one, and without this the two results are indistinguishable —
'0 off-targets' would read the same whether every contig or a 100 bp window was examined."* Written down,
recorded in provenance, and then not shown.

Measured over a two-contig reference holding the same locus twice:

    chr2 only  -> 1 site, specificity 0.468, searched 140 bases
    whole ref  -> 2 sites, specificity 0.305, searched 280 bases

    both -> 'up to 4 mismatches, 1 DNA / 1 RNA bulges; sites reported at CFD >= 0.2 or MIT >= 0.1'

Identical. `OffTargetReport` already carried `searched_bases`; `search_description()` mentioned it only when
the *resolved* fraction fell below 99%, and both of these resolved fully. So the field whose docstring says a
reader "cannot compare two reports without them" was omitting the setting that separated 0.468 from 0.305 —
in the direction where the narrower search, the one that nominates fewer off-targets, reads as the safer
guide. Scoping to a panel is not an edge case; the `--region` help calls it what usually makes a run
practical.

The extent now leads the description. Two follow-ons fell out of doing it:

* The fixture the HTML and PDF render tests share had `searched_bases` at its default of 0, so it printed
  "over 0 bases" beside a table of two nominated sites. The field has a default, which means a report
  deserialized from before it existed arrives the same way — so 0 with sites attached now says the extent is
  *unrecorded*, not zero. A stated zero invites precisely the comparison this change exists to enable.
* Three existing assertions pinned the old string. Two rounds of loosening them to accommodate the shifting
  PDF line wrap was the wrong instinct: the fixture was wrong, not the assertions. Giving it a real extent let
  all three tighten instead — the PDF now asserts `search: over 248,956,422 bases` glyph-for-glyph.

**Lesson: when a fix makes an existing assertion fail and the obvious repair is to weaken it, check whether
the fixture is the thing that is wrong. Weakening an assertion to fit a degenerate fixture spends a real
check to keep a fake one, and the second time I reached for it was the signal.**


## Round 190 — the allowance that excused eight things by rendering two

R189 fixed one omission and left a thread. `PROVENANCE_FOOTER_OMITTED` is the report's honesty mechanism: the
footer is a curated summary, and every field it skips must be listed there with a reason, so an omission is a
decision rather than an accident. It had exactly one entry — `config_snapshot`, excused as "rendered inline
beside the results."

The snapshot holds eight keys. `build_report` reads two.

The method that settled it was not reading code. Render a report, vary one setting, and look at what a reader
would actually see. Two traps showed up immediately, and both would have produced a wrong answer:

* **A page that differs proves nothing.** Varying `cell_context` "changed the page" — the only differing
  fragment was the footer timestamp. Varying `populations` also "changed the page", because the *results*
  changed; nothing said which setting produced them. That is R189's finding restated: a difference in output
  is not a disclosure of input.
* **A name that appears proves nothing either.** `"K562" in page` was True for `cell_context="K562"` — and
  equally True for `cell_context="HEK293T"` and for no context at all. Both strings live in a model card's
  known-failure-modes text. R182's coincidental-substring trap, caught only by checking the negative case.

With those controlled, three keys reached no reader:

**`populations`.** Requested `afr, eas, sas` with no gnomAD and no haplotypes: `unbacked_populations` came
back `()`. The engine computed it with a trailing `if backed else ()` — deliberate, with a comment deferring
the no-source case to "the R75 case, warned elsewhere." Elsewhere is `_warn_if_ancestries_unbacked`, in the
CLI, printing to the terminal. Its own docstring names the danger precisely: an empty breakdown "reads like
'no ancestry-specific risk found' rather than 'nothing was searched'." So the warning existed, was correct,
and was in the one place that does not survive: not the HTML a collaborator opens, not the PDF, not the TSV,
and not reachable at all from the library or the web API. The two cases differ in how a user *fixes* them,
not in what the report has to *say*.

**`settings.maf_threshold`.** The cut-off that decides which population alleles enter the scan, one step
earlier than the reporting cut-offs the description already named. One 2% PAM-creating variant:

    maf=0.001 -> 1 site,  specificity 0.500
    maf=0.05  -> 0 sites, specificity 1.000

Identical descriptions on that axis, and the reassuring one is the one you get by tightening a threshold. The
inert-source note made it worse: "supplied but contributing nothing *in this region*" blamed the locus for
what the caller's own threshold had done. Both now name the cut-off; a reference-only scan still names none,
because a provenance line that is always present teaches a reader to skip provenance lines.

**`cell_context`.** Reaches a reader only through the distribution check — an unrecognized value flags `ood`,
a recognized one changes nothing, and the efficiency is not cell-adjusted without ENCODE tracks. That is a
real route, so it is recorded as one rather than fixed into something it is not.

`CONFIG_SNAPSHOT_ROUTES` now records all eight, each verified by varying the setting and reading the page, and
a test fails when a key is added without a route. Writing that comment was itself the round's sharpest moment:
the first draft claimed "cell_context -> named beside the efficiency it adjusts", which the K562 check had
already disproved. I had reached for a tidy sentence about output I had not looked at — the exact failure R188
was about, one round later, while writing the fix for it.

The `populations` fix broke a test that pinned the old behavior outright: `assert none_given.
unbacked_populations == ()`, with the comment *"that case has its own warning, and two warnings for one
situation is worse than one."* The principle is right and the premise was not — the other warning is the
CLI's, printed to the terminal, so the report carried zero warnings rather than one. On the CLI path the two
now co-exist and are not duplicates: one tells the person at the keyboard how to fix the run, the other tells
whoever opens the HTML months later that an empty ancestry breakdown means nothing was searched. The
assertion was inverted with that reasoning written beside it, rather than deleted.

**Lesson: the honesty mechanisms need auditing on the same schedule as the code, and by the same method. An
allowance list, a coverage exception, a documented skip — each is a claim, each is written once and read
forever, and each is exactly the kind of thing that is true when written and quietly false three features
later. Two of the last three rounds found a defect not in the product but in the thing meant to prevent one.
And when a correct-looking decision cites a mechanism elsewhere — "warned separately", "rendered inline",
"covered by the other test" — the citation is the part to go and check.**


## Round 191 — the scoped run that scanned everything

Two allowances audited first, both clean: the 46 `pragma: no cover` markers each carry a reason and the
logic-based ones hold (`_nice_max`'s fallback really is unreachable — `10 ** floor(log10(v))` guarantees the
`10.0` step catches); `_OLIGO_NOT_IN_PDF`'s claims that `rtt`, `pbs` and `motif` are "encoded in the ext
duplex that is actually ordered" are already asserted in `test_oligos.py`; and `aforge verify` was found to be
exemplary — it already distinguishes "provenance is complete" from "artifact bytes were re-hashed" and says
so in both directions, including the `--cache-dir`-given-but-nothing-hashed case. Negative results, recorded.

The query that paid was the one my notes call the highest-yield in this project: take `design()`'s parameter
list and check it against each shell. Run against the web API it found a gap *inside* the API —
`DesignRequest` carried `offtarget_regions`, `cell_context`, `allow_ng` and `allow_spry`; `BatchRequest`
carried none of the four, all of which `aforge batch` has had all along. So the most expensive path was the
one that could not be scoped, and a cohort — the setting where a variant with no actionable NGG guide is
*certain* to appear — could not offer the fallback built for exactly that case.

Wiring them through took minutes. The test written alongside them is what mattered, because one assertion in
it went beyond "the field is accepted" to "the value reached the engine": a region naming a contig the
reference does not have, which `search()` refuses by name. It did not fail. The whole cohort ran, genome-wide,
and reported success.

The region was never reaching the engine at all — and not because of the web API:

    design(..., offtarget_regions=[chr2:0-50])
      provenance snapshot : 50 bases
      actually searched   : 140 bases (the whole contig)

`design()` forwards `offtarget_regions` to `design_base_editor` and **not** to `design_prime` or
`design_cas9`. All three accept the parameter. Two call sites omitted it. So the restriction was inert for the
two most-used chemistries, while the snapshot recorded it as applied — the run slower than asked for on the
axis where the `--region` help says scoping "is usually what makes a run practical", and the artifact claiming
a scope that never happened. Against a real hg38 that is the difference between a panel scan and an
impossible one, silently.

Nothing could see it. The parameter existed end to end, every signature accepted it, the suite was green, and
the one input that would have raised — an unknown contig — was swallowed because it never got far enough to be
refused. R189's `over N bases` is what finally made it visible: without a number for the extent actually
searched there was nothing to compare the snapshot against.

Then the regression test reproduced the bug inside itself. Deleting the prime wiring failed it; deleting the
**nuclease** wiring left all six tests green, because the fixture variant only ever yielded prime candidates
and the per-chemistry loop had one chemistry to iterate. The file is now parametrized over three scenarios,
one per vertical, each with a guard asserting it really produces the chemistry it claims — and each of the
three wirings now kills exactly three tests when removed.

**Lesson: a defect that is per-branch needs a fixture per branch, and "iterate over whatever the fixture
produced" is not that — it is a loop that silently has one element. Mutate each site separately, not the
feature as a whole: mutating "the region wiring" would have looked fine, because one of the three sites was
enough to fail the tests I had.**


## Round 192 — the forwarding matrix, and what it does not show

R191 found `offtarget_regions` reaching one vertical of three. The obvious next question is whether anything
else is. So: parse `designer.py`, collect the keyword arguments at each vertical call site, and cross them
against each vertical's signature.

Clean. After R191's fix every parameter a vertical accepts is passed to it (`intent` and `resolved` flag as
"dropped" only because they are positional). A negative result, and a cheap one — the check is a dozen lines
of `ast` and it is now the kind of thing worth keeping in mind rather than repeating by eye.

The finding was in the cells the matrix marks "n/a" — not a parameter dropped, but one a vertical never had:

    option            cas9   prime   base_ed
    cell_context        NO     yes        NO
    chromatin_track     NO     yes        NO
    encode_tracks       NO     yes        NO

`--cell-context` is offered unconditionally on `aforge design`, and is consumed by prime editing alone. What
the other two chemistries then report is worse than nothing:

    cell_context='not-a-real-cell-line'
      prime          -> ood flag, in_distribution=False
      cas9_nuclease  -> no flag,  in_distribution=True
      base_abe       -> no flag,  in_distribution=True

Both `True`s are honest. `context_in_distribution` checks the *guide* context — no ambiguous base, long enough
for the head to read — and the codebase is careful that it is never hardcoded. That is precisely what makes it
misleading here: the flag is a real measurement on a real axis, sitting next to a supplied input it has
nothing to do with, in a column a pipeline filters on. Ask for K562, get `in_distribution: True` beside a
nuclease candidate.

The fix is a declaration, following the `chromatin_track` precedent three lines above it in the same function.
It would have been easy, and wrong, to "fix" this by wiring a cell-context OOD check into the nuclease and
base-editor scorers: they have no cell-context training distribution, so any check I invented would be a
number with nothing behind it — the failure this project exists to avoid. Naming the gap is the honest move
and the smaller one. The CLI help and both web request models also claimed the context "flags **every**
efficiency prediction out-of-distribution", which was simply false; they now name the chemistry that consumes
it.

One test in the new file pins the misleading state itself — `in_distribution is True`, no `ood` flag, note
present. If a cell-context distribution is ever wired into those scorers, that test fails, which is the right
moment to revisit the note rather than leave it describing something no longer true.

**Lesson: an audit that compares two lists finds what is missing from one of them, and is blind to what is
missing from both. The forwarding matrix came back clean; the defect was in a column the matrix printed as
"n/a" and moved past. When a check reports no findings, ask what shape of defect it was structurally incapable
of seeing.**


## Round 193 — 1,400 lines of claims that nothing checked

R192's lesson was to ask what a clean check was structurally incapable of seeing. Applied to myself: every
audit this session has compared code against code. The README is 1,400 lines of specific, checkable
assertions about behavior, and I had only ever corrected the ones I happened to trip over — the coordinate
row in R188, and nothing systematic.

Three checks, two mechanical:

* **Commands.** All eight the README documents exist. Clean.
* **Flags.** 53 distinct `--flag` strings; 51 exist. The other two rounds of "missing" were docker's
  `--build`, ruff's `--check`, pytest's `--nbmake`/`--no-cov`, uvicorn's `--port`, maturin's `--release`,
  mypy's `--strict`, and three markdown anchor links that look like flags. Clean, and now recorded by owner
  so the list cannot quietly absorb a real stale flag.
* **"Every `design()` capability is reachable from the CLI."** Verified parameter by parameter. True.

The finding was the one non-mechanical claim: `--cell-context` "raises the out-of-distribution flag on
**every** efficiency prediction". That is R192's falsehood, in the fourth place it lived. R192 corrected the
CLI help and both web request models *in the same round that discovered it* and missed this one. Care did not
scale to four copies of a sentence; a test does.

Then the tests I wrote to prevent that had the same disease twice over:

* The command check filtered candidate names against the real command list before reporting them missing —
  so it could only ever report names that were already real. Empty by construction. It passed against a
  README that invoked `aforge validate`, and I only found out because M3 of the mutation run did not fire.
* The claim check searched line by line for a sentence my own edit had just re-wrapped across three lines. It
  matched nothing and passed. Same shape as the regex-in-an-f-string from R182: a checker that silently finds
  nothing looks exactly like a checker that finds nothing wrong.

Both now assert they parsed something before asserting anything about it, and the vacuity guard is itself
mutation-checked — breaking the parser fails the test rather than passing it.

**Lesson: a test that filters before it asserts can be empty by construction, and that is invisible in a green
run. Every extraction-based check needs a floor — "I found at least N of these" — asserted before the real
assertion, and the floor needs its own mutation. Three of this session's checks have now failed this way; it
is the default failure mode of writing a test *about* a document rather than about code.**


## Round 194 — the checks that pass by finding nothing

R193 ended with three of its own checks having been empty by construction. That is not a
mistake to be more careful about next time; it is a shape, and shapes can be searched for.

The shape: a test whose assertions are *all* "this derived collection is empty" —
`assert not broken`, `missing == []` — over a value produced by scanning something, with
no positive assertion anywhere. An extraction that finds nothing satisfies every one of
those perfectly.

A first pass flagged 127 tests, which is a detector saying "a list comprehension appears
here" and nothing more. Narrowed to the actual shape it gives 18, and the ones that
matter are the checks that scan a *surface* — prose, a signature, a set of model fields
— and report that nothing is missing from it.

Measured rather than argued. Neutralizing `_prose_files()` so the corpus is empty:

    5 of 6 tests in test_readme_documents_the_cli.py still passed

including "every local link in the prose resolves" and "every module path the prose cites
is importable". Both had been checking zero links and zero modules, and would have gone on
doing so silently after any rename of `docs/`, any reformat that broke a regex, any move of
the README.

Floors added to five checks — the two prose scans, the docs cross-reference scan, both
shell-parity parameter sets, and the cohort/design parity check written two rounds ago,
which had the same defect the moment it was written. Each floor is mutation-checked by
neutralizing its extraction, which is the only way to know a floor is load-bearing rather
than decorative.

The convention is recorded in `project.md`, because this is a habit rather than a fix: the
next check of this kind will be written next round, and the rule is what carries.

One note on the fix's own dogfooding: writing the convention cited R194 before this entry
existed, and `test_every_round_cited_in_the_conventions_exists` failed immediately. A guard
written five dozen rounds ago catching the round about guards is the argument for all of
them.

**Lesson: when a defect turns out to be a shape rather than an incident, stop fixing
instances and go looking for the shape. The search cost twenty minutes and found four more
of the same defect in checks that had been green for months — and the ones it found were
older and more load-bearing than the ones that prompted it.**


## Round 195 — the re-run that reported success by doing nothing

Two queries. The first was R187's shape (a range check that admits NaN) taken to the web boundary, and it came
back clean: pydantic's `ge`/`le` rejects NaN and infinity where Click's does not, and the one unbounded field
— `DesignRequest.weights`, which has only a length constraint — is caught a layer down by `RankingWeights` and
surfaced as a specific 422 (`weight efficiency must be finite`, `weight safety must be non-negative`, `ranking
weights cannot all be zero`). No 500, no traceback. Recorded as a negative result.

The second was durable state under failure, and the cohort manifest had two.

**A resume skipped what failed.** `_read_done_ids` collected every item id the manifest mentioned, and the
manifest records failures too. So:

    run 1: total=2  succeeded=1  failed=1     (exit non-zero)
    run 2: total=0  succeeded=0  failed=0     (exit 0)

Scaled up: a cohort of 10,000 finishing with 200 errors skips all 10,000 next time and reports a clean, empty
run. "Re-run until it passes" works, by doing nothing, and the only way to retry the 200 is to delete the
manifest and lose the 9,800. Resume exists to avoid recomputing *results*; an error is not one, and these fail
at variant resolution before any search, so retrying is nearly free.

**A truncated last line crashed it.** An append interrupted mid-write leaves exactly that, and `json.loads`
raised `JSONDecodeError` — from the one code path whose entire purpose is recovering from an interrupted run.
There is a sibling test tolerating *blank* lines, so malformed lines had been thought about and the wrong case
handled. Only the final line is forgiven now; a bad line in the middle still raises, naming it, because that
means a corrupt or hand-edited manifest where skipping would silently recompute or silently drop.

The existing test pinned the old behavior outright (`second.total == 0 and second.skipped == 3`, commented
"everything already recorded" — descriptive, not a justification), and a third assertion further down had to
move with it: with the failure retried, a run adding one new item now does two items, not one.

A footnote that belongs to R194. Three mutation runs in this round reported "no tests ran" and I nearly read
that as "the mutation survived". The harness put two test paths in a shell variable and used it unquoted —
which word-splits in bash and **does not in zsh**, so pytest was handed one nonexistent path. A mutation
harness that silently checks nothing is the same defect as a test that silently checks nothing, one level up,
and the only reason it was caught is that R194 had just made the shape familiar enough to distrust.

**Lesson: "resume" and "retry" are different promises, and a manifest that records both outcomes invites
conflating them. Any skip-list built from a log of *events* needs to filter on the outcome, not the presence
of a record — and the direction of the mistake was, again, the one that looks like success.**


## Round 196 — unique per process, shared per thread

R195 found that a truncated manifest line comes from an interrupted append. The obvious neighbour: an
interrupted append is one way to get a torn write, and *concurrency* is the other. `design_many` takes
`max_workers`, and `aforge batch` exposes it.

The manifest itself is clean, and deliberately so — `_record` is called from the main thread inside the
`wait()` loop, so worker threads only compute and every append is serialized by construction. A negative
result, and a design decision worth noticing rather than re-deriving.

The per-item menu write was not. `_atomic_write_text` is careful in every respect but one:

    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")

Unique per *process*. It runs inside `_design_one`, which runs in a worker thread, so every thread in a
parallel cohort shares that name — and two items with the same id resolve to the same output path and
therefore the same temp path. A variant repeated in a VCF is ordinary.

Both threads write one file and both rename it. Measured with two threads released from a barrier onto the
same path:

    FileNotFoundError: ... 'item.json.65108.tmp' -> 'item.json'

The first `os.replace` moves the shared temp away; the second finds nothing. In a cohort that lands in the
`except Exception` branch and is recorded as "unexpected FileNotFoundError (likely a defect)" — against an
item whose data was perfectly fine. Other interleavings leave the two payloads mixed in one file, in the
export the module docstring calls lossless.

The fix is the name, not the mechanism: temp-file-plus-`os.replace` is correct, the UTF-8 pin above it is
correct, and the comment explaining why a plain `write_text` is unsafe is correct. Everything about that
function had been thought through except which scope the uniquifier needed.

Worth saying plainly: only one of the four new tests fails against the old name. The content-corruption case
is genuinely timing-dependent and cannot be pinned deterministically; the crash can, so the crash is the
detector and the other three are guards on properties that must hold once it is fixed.

The sweep for the shape came back clean, and pointedly so. `cache.py` writes its temp files with
`f"{os.getpid()}.{uuid.uuid4().hex}"` — the correct scope, with a concurrency test beside it — and
`cas_offinder_adapter.py` uses `NamedTemporaryFile`, unique by construction. `cohort.py` was the only
instance, and it was written as though the one two directories away did not exist.

**Lesson: `os.getpid()` in a temp-file name reads as "make this unique", and it is — at the wrong scope. When
code moves under a thread pool, every process-scoped identifier in it silently becomes shared, and nothing at
the call site says so. The sweep found no second instance but did find that the right pattern already existed
elsewhere in the tree: the defect was not ignorance of the rule, it was a second implementation of something
already solved. That is worth checking for first, and it is cheaper than the audit that finds it later.**


## Round 197 — the verdict a machine reads

R195 turned on a re-run exiting 0 when it had done nothing. Exit codes are the
machine-readable verdict — what a CI job branches on — and they had never been audited as
a surface of their own.

`aforge offtarget` over a truncated reference, a contig header with no bases, which is
what an interrupted download leaves:

    0 site(s), worst score 0.000, specificity 1.000
      search: ... NO SEQUENCE WAS SEARCHED — the reference or region scope yielded no
      bases, so this is not a clean result, it is an empty one
    exit=0

The human is told exactly what happened, in words the project chose carefully. The
pipeline sees a spotless guide. Same defect as R190's ancestry warning: the disclosure
exists and lives on the one surface that does not reach the consumer who acts on it.

What makes this round's find sharper than most is what the existing test said. It pinned
`assert result.exit_code == 0`, four lines under its own comment:

    # ...that path is asserted separately below because it is the dangerous one: it
    # returns a *result*, and the most reassuring one the system can produce.

The hazard was seen, named precisely, and then pinned as the expected behavior. Two cases
in the same test — an empty file and a VCF passed as a FASTA — already exited
MISSING_DATA; only the one that produces a plausible-looking answer exited 0. All three
now agree, which is what makes the fix small: nothing about the output changed, only the
status that says whether to trust it.

The `--json` payload had the matching gap. Its `search` block listed the budgets and
cut-offs and not the extent, so a machine consumer could not distinguish a genome-wide
scan from a 140-base one — R189's finding, one surface over and still open, because R189
fixed the human line and the payload is assembled separately. It now carries
`searched_bases`, `resolved_bases` and `maf_threshold`, and the test that pins the block
does so by exact equality, so the next field cannot be added to one and not the other.

**Lesson: a caveat is only as good as the narrowest surface it reaches. This project keeps
finding the same disclosure written once, correctly, on one of three surfaces — terminal
but not report (R190), human line but not payload (R197), report but not exit status. The
question to ask of any new caveat is not "is it true" but "which of the three consumers
sees it": the person reading, the artifact they hand on, and the program that branches.**


## Round 198 — a small round, and four things that were already right

R197's lesson was to ask which of three consumers sees a given caveat — the person reading, the artifact they
hand on, the program that branches. Swept the codebase for warnings that reach only the terminal, and the
sweep came back nearly empty: there are exactly two, and R190 had already given the ancestry one a report-side
counterpart. The other is an unknown key in a run-config TOML, and it turns out to be adequately mitigated —
every config key resolves to a *default* when mistyped, and the defaults are the conservative choice on every
safety-relevant one (`maf_threshold` falls back to 0.001, admitting more population variants, not fewer;
`run_offtarget` falls back to running the search). R189 and R190 also now print the effective thresholds in
the search description, so a reader comparing them against their config sees the discrepancy.

So the round went looking at `aforge lift`, never examined in this session, where a wrong answer means
designing a guide at the wrong place in the genome. Four things checked, three of them clean:

* The output round-trips: `str(GenomicInterval)` produces `chr1:100-120(+)` and `GenomicInterval.parse`
  accepts it, strand included. The documented promise holds — and was untested, so it is now.
* `UNMAPPED` is printed rather than dropped, and the run exits non-zero. Both hold; both now tested.
* `lift_interval` is rigorous: it rejects unmapped bases, cross-contig spans, mixed strands, and any length
  change, and it sorts positions so a minus-strand mapping does not invert the span.
* The per-base scan is justified in a comment by "the lifted intervals here are short (guides/windows,
  ~20-200 bp)" — and `aforge lift` hands it arbitrary user-supplied loci. Measured before claiming anything:
  0.7 s per megabase, linear. A whole-chromosome lift takes about three minutes. Slow, not broken; no fix.

What was wrong was the docstring, which describes lifting "the first and last bases independently". The code
lifts every base, and the comment below it explains that an endpoint-only check passes a *balanced* interior
gap — a source deletion and target insertion of the same size — leaving the endpoints mapped and the length
unchanged while the interior maps to nothing. That change is tested
(`test_liftover_balanced_interior_gap_returns_none`, with a better explanation than the docstring above it).
Only the docstring lagged, and it lagged in the rare direction: it *understates* the guarantee, so a reader
auditing for that hazard concludes it is present and either distrusts the tool or writes a redundant guard.

**Lesson: a round whose main finding is a stale docstring is a cheap round, and worth saying so plainly rather
than dressing up. The four negative results are the actual product here — `lift` is in good shape, and now
three of its documented promises are pinned instead of merely true. Verifying a suspicion costs little; the
measurement that killed the performance hypothesis took two minutes and stopped a fix that would have been
solving nothing.**


## Round 199 — the number you cannot improve by looking away

First, the project's own answer to "what is left": `scripts/release_readiness.py` reports 1 of 5 v1.0 criteria
met and every open one blocked outside this repository — real checkpoint hashes, real benchmark corpora, a DOI
minted on the first tagged release. There is no unblocked release work to pick up, which is why the audit
continues rather than a feature.

`viz/svg.py` came back clean, and interestingly so. Colors are the one caller-controlled value that reaches an
SVG *attribute*, where the text-node escaper does not apply, and the module says so in a comment naming the
R12 injection class — then validates them in `__post_init__` on both dataclasses that carry one. Every other
attribute interpolation is numeric or a constant. A defended surface, with the defense wired.

The finding was an invariant that held and was not pinned. `specificity_score` is
`1 / (1 + Σ reported + subthreshold_score_sum)`, and the tail term exists so the reporting cut-off decides
what is shown rather than what is counted. Measured across the range:

    cfd_threshold  n_sites   Σ shown   subthr tail   specificity
              0.0        5    3.6143        0.0000      0.216718
              0.5        4    3.2125        0.4018      0.216718
              1.0        1    1.0000        2.6143      0.216718

Exactly invariant, with the tail absorbing exactly what leaves. Every piece of that was unit-tested — the
formula includes the tail, merging two nick reports sums it, the engine produces a non-zero one — and the
property those pieces exist to produce was not tested anywhere.

Worth pinning because the failure has a direction and a very short path to it. Drop the tail from the formula
and raising `--cfd-threshold` makes the aggregate safety number go *up*: a guide is made to look more specific
by asking to be shown less, using a flag on every command. So the property is pinned twice — as the equality
that actually holds, and separately as the inequality that showing less must never score better. Both
mutations (removing the tail; halving it) are caught by the inequality, which is the one that would still
mean something if the tail ever became approximate.

**Lesson: unit-testing every ingredient of an invariant is not testing the invariant. Each of the three
existing tests was correct and none of them would have noticed the property disappearing, because each
checked a term rather than the relationship between them. When a formula has a part whose whole purpose is to
make some other quantity *not* matter, the test to write is the one that varies that quantity.**


## Round 200 — the quantities that are supposed not to matter

R199's lesson, applied as a query: when a formula or a flag exists so that some other
quantity has *no* effect, the test to write is the one that varies that quantity. Two
candidates, both documented, neither checked.

**The render cap.** `--render-candidates` caps the drawing, and three separate places say
so — the CLI help ("the json/tsv exports are never capped"), the web request model, and a
comment in the API handler. Nothing tested it. A prime design yields about ninety
candidates; a leak would write three of them to the JSON a pipeline consumes while only
the HTML mentions the other eighty-seven. It holds, and now fails if it stops.

**Worker count.** A parallel-vs-sequential equivalence test already exists and is good —
it compares per-item status and summary. It does not pass `output_dir`, so the files on
disk, which are the actual deliverable of a batch run, were outside it. That is also
exactly the surface R196's temp-file collision lived on.

And the first version of that new test did not catch R196's bug either. Three distinct
variants never collide on an output path, so restoring the old process-scoped temp name
left all four tests green. The trigger needs a **repeated** item — which is ordinary in a
VCF, and is the case the fix was written for. Caught only because the mutation run was
done properly: M1 fired, M2 did not, and the docstring I had already written claimed the
test protected exactly the property M2 was proving it did not.

That is the second time in three rounds that a regression test written for a specific bug
failed to reproduce that bug (R191: a per-vertical defect and a fixture exercising one
vertical). Both times the mutation run was the only thing that said so, and both times the
fix was to make the fixture contain the shape the bug needed rather than to weaken the
test.

**Lesson: writing the regression test after the fix means never seeing it fail for the
right reason. The mutation is not a formality at the end — it is the only evidence that
the test and the bug are about the same thing, and a docstring asserting the connection is
worth nothing next to a mutation that demonstrates it.**


## Round 201 — the round where the tests were already better than I was

Continuing R200's query into the ranking, the product's core output. `--max-per-chemistry`
caps how many candidates each chemistry keeps, and the cap is applied after the composite
sort, so it should return a *prefix* of the uncapped ranking.

The first thing found was a gap that was not one. `test_cap_is_per_chemistry` counts the
survivors and never checks *which* survived — a cap keeping the worse candidate of each
chemistry passes it. That looked like the R199 shape exactly. It is not, because
`test_cap_keeps_composite_best_not_local_proxy_best` sits fifteen lines above it and
proves the property with a sharper fixture than the one I wrote: a candidate that tops the
local efficiency proxy while being dangerous and dirty, against the composite winner. My
addition was redundant, so it was deleted rather than left as noise.

The prefix property is genuinely distinct and worth pinning — "the top three" must mean
the first three of "all of them", not three of them. And the test I wrote for it was
vacuous in the now-familiar way: the fixture listed candidates in descending efficiency,
so capping *before* the sort keeps exactly the same ones and the test passes either way.
Mutating the ranker (moving the sort after the cap) fired the pre-existing test and not
mine. Scrambling the fixture order made it load-bearing; it now fires too.

That is three rounds running where a new test failed to detect the defect it was written
for, each caught only by mutating. The pattern in all three is the same and worth naming
precisely: **the fixture was built from the happy path**. Three distinct item ids where
the bug needs two identical ones (R200); one vertical where the bug is per-vertical
(R191); already-sorted input where the bug is a sort-order swap (here). Building a fixture
from what the code does, rather than from what the bug needs, produces a test that agrees
with the code by construction.

Then the gate failed on a test written *last* round, which had passed three times in
isolation: `KeyError: unknown contig 'chr2'` from three of four items in a parallel
cohort. Reproduced at 3 failures in 15 isolated runs.

Not a bad test — a real race, and one the tree already knew about. `design_many`'s
docstring states the precondition plainly: the FASTA "must already carry its `.fai`
index, so the concurrent first-opens read it rather than racing to build it", with the
remedy in parentheses. The CLI honors it (`_load_reference` opens the reference before
handing out the factory) and the older cohort fixture honors it by pre-building the
sidecar, with a comment calling it "the factory contract". My fixture did not, so the
workers raced, and pyfaidx reported a half-written index as a missing contig.

The remedy the docstring asks every caller for is one line, so `design_many` now does it
itself: open the factory once before starting the pool. Measured: 2 failures in 20 runs
without it, 0 in 20 with. The older fixture's manual pre-build was then removed — it had
become the workaround for a contract that no longer exists, and leaving it would mean no
test exercises the path a caller actually takes with a fresh FASTA.

**Lesson: a documented precondition whose violation is a *race* is a bad trade. It fails
non-deterministically, only under parallelism, and here it reported `unknown contig` —
naming the one thing that was not wrong. When the docstring's own remedy is a single line
the library could run itself, the precondition should not exist. And the second lesson,
cheaper: when an audit finds a gap, look fifteen lines up before filling it. Two of this
round's findings dissolved on contact with tests that were already there and better, one
survived only after a mutation showed the first version of it was worth nothing, and the
real defect arrived from a direction nobody was auditing — a flaky test I had written
myself the round before.**


## Round 202 — the cohort that was smaller than the file

The ingest boundary, on the reasoning that a dropped input is a shorter list and a
shorter list never complains. `iter_vcf` drops three kinds of row and dropped all three
without a word:

    6 VCF rows in -> 2 design requests out

    chr1:100 A>G          kept
    chr1:200 A>G  LowQual dropped   (soft-filtered, the default)
    chr1:300 N><DEL>      dropped   (symbolic ALT)
    chr1:400 A>[<DUP>,T]  kept T    (one ALT dropped, one kept)
    chr1:500 A>*          dropped   (spanning-deletion star allele)
    chr1:600 A>G[chr2:900[ dropped  (breakend)

Every one of those drops is right — none names a designable substitution, and a guide
designer has nothing to say about a breakend. What was wrong is that a real VCF carries
all three routinely, so `aforge batch cohort.vcf` designs over a cohort smaller than the
file, reports success, and leaves the two numbers unconnected. The user who notices has
to diff a line count against `total`.

Counted now, by reason, with the line printed only when something was actually dropped.
The reasons stay separate because their remedies differ: a soft-filtered call may want
`pass_only=False`, a structural variant wants a different tool entirely.

The interesting case is `chr1:400`, and it is what settled the wording. It is neither a
clean row nor a lost one — it came through **incomplete**. A summary reading "N of M rows
yielded nothing" is false about precisely the row a reader most needs to see, so the count
is of drops rather than of rows. The first version of the summary line said the row thing,
and produced "5 of 6 VCF rows yielded no design request" for the example above, which is
wrong twice over: four rows yielded nothing, and the fifth drop was an ALT.

**Lesson: I wrote a misleading summary line inside a round whose subject was misleading
summary lines, and caught it only by printing it and reading it. The rule that keeps
holding across this whole log is not "think harder about the wording" — it is *run the
thing and look at the output*, which has now caught more defects than reading the code
has, including several of my own from the same hour.**


## Round 203 — a round with no findings, and what that is worth recording

R202 found a silent drop at one ingest boundary, so this round swept the others. Nothing
to fix. Written down because the next session should not re-tread these, and because
"checked and sound" is only useful if it says what was checked.

* **`--regions-bed`.** Fails loudly on a malformed line (`IndexError`/`ValueError` →
  exit MISSING_DATA) and skips only blank, `#`, `track` and `browser` lines, which is the
  BED spec. No silent drop.
* **The variant list.** Skips blanks and `#` comments; anything else reaches the cohort
  and fails as a per-item error that is reported and, since R195, retried on resume.
* **The gnomAD sites reader.** Raises when the header is missing. Silently skips symbolic
  and spanning-deletion alleles — correct, and already summarized at the point of use by
  `sources_considered`, which counts what the source actually contributed in the searched
  region. Considered adding a parse-time counter on R202's principle that "correct to
  drop" is not "fine to drop silently"; judged not worth it, because the existing count
  covers the consequence and a second number for the same fact is noise. Recorded rather
  than done, so the reasoning is available if someone disagrees.
* **`is_sequence_allele`.** Case-insensitive (`.upper()`), so a soft-masked lowercase
  allele is not silently discarded — the failure I went looking for. Its docstring also
  explains why the three loaders skip rather than abort: one symbolic row in a real
  ClinVar release would otherwise lose every record after it.
* **The prime enumerator.** The area I expected to be weakest, having previously hidden a
  hardcoded `- 1` and a frame-shifted window. `test_rt_product_installs_the_intended_edit`
  is a real simulation: six edit classes (SNV, MNV, insertion, deletion, delins, large
  deletion) crossed with both intents and both strands, asserting the reverse-complemented
  PBS+RTT product appears verbatim *and uniquely* in the edited genome, computed in the
  pegRNA's own coordinate frame. Stronger than what I was about to write.

**Lesson: five probes, five clean. That is the finding. Sixteen rounds in, the areas
reachable by the queries this session has been running are genuinely well tended, and the
honest report is that the yield has dropped rather than that more rounds would keep paying
at the earlier rate. Worth saying plainly, because a log of rounds that only ever records
defects reads as a codebase that is only ever broken.**


## Round 204 — the bounds that bounded the wrong thing

A query family not used before: which collections and strings in a request payload have no
upper bound. The answer was almost none — `MAX_BATCH_VARIANTS`, `MAX_REGIONS`,
`MAX_POPULATIONS`, `MAX_SPACER_LEN` and the rest are all there, and someone clearly went
through this once. Exactly one string field had escaped: `intent`, a plain `str`, while
every sibling was bounded.

Bounding it changed the response size by three bytes.

    intent, unbounded  -> HTTP 422, 100146 bytes
    intent, max 128    -> HTTP 422, 100149 bytes

Because FastAPI's default validation error carries the offending `input` verbatim. The
bound decides what is *accepted*; the rejection is what carries the value back. Checked
across the other fields and it is systemic — `variant` bounded at 8192, `spacer` at 512,
`cell_context` at 128, all four answering a 100 KB value with a 100 KB error.

So the fix belongs on the handler, where it covers every field on every model and the ones
not written yet: trim the echoed `input`, keep `loc`/`msg`/`type` because that is what
makes a 422 actionable, and leave short values alone so a caller still sees their own typo.
100 KB responses become about 360 bytes.

The mutation run then caught the test for that last property. `MAX_ECHOED_INPUT = 2` left
every test green, because the "short value is still shown" test sent a *misspelled intent*
— which is well under the length bound, so the model accepts it and the domain rejects it
on a different path that never reaches the truncation at all. The test was exercising a
route it did not name. Rewritten against the helper directly; both it and the list-trimming
case now fail when the trimming changes.

**Lesson: a bound is not a budget. Four separate length limits were all correct, all
enforced, and none of them constrained the thing an operator would care about, because the
expensive path was the *rejection* rather than the acceptance. Worth asking of any limit:
what happens on the branch where it fires.**


## Round 205 — profiling, after concluding there was nothing left

The previous round ended by reporting that the audit's yield had fallen and that
everything else was blocked outside the repo. Both halves were true and the conclusion
drawn from them was wrong: "this query family is exhausted" is not "there is no work".
Two veins had been dismissed without being looked at.

The docs one came back clean, and pleasantly. `docs/` does not mention the PAM fallbacks,
the search extent or the render cap — but it is deliberately thin, with the README as the
reference, so a missing mention is not a defect. What matters is whether it says anything
*false*, and the one place it makes a behavioural promise —

    an off-target report ... labelled reference-only when you do not [supply a source],
    because an empty ancestry breakdown means *not measured*, not *clean*

— was **false until R190** and is true now. The documentation was ahead of the code and
the code caught up.

The performance vein was real. Profiling a 2 Mb scan:

    501,262 calls  _best_ungapped
    10,526,502     the genexpr inside its sum()      <- largest single cost

`_best_ungapped` priced all twenty positions and then compared against the budget. Its
immediate neighbour, `_best_with_removed_base`, already stops its prefix pass the moment
the budget is blown, and explains in its docstring why that is safe and why it matters
("on a random window that is after a handful of bases"). The technique was known, written
down, and sitting ten lines below the function that did not use it.

Measuring it honestly took longer than fixing it, and the first three attempts disagreed:

    cross-process, min-of-5      ungapped +16%   default +10%
    interleaved in one process   ungapped +40%   default +12%
    isolated microbenchmark      +60% at max_mm=4, +51% at max_mm=6

The 40% was contaminated — the same "old" implementation timed 6.5s there and 1.5s
across processes — so it was discarded rather than reported. What is defensible: the
function is about 60% faster at the default budget, and a whole scan is 10-16% faster
depending on bulge configuration, because the function is one part of the work. The
project's own note warns that cross-run timings are not baselines; this round is the case
that warning was written for.

The reproducibility golden is unchanged, which is the real proof of equivalence, and a
randomized differential against the naive full-count definition now pins it.

**Lesson: "the yield of my current method has fallen" is a statement about the method. I
had been running one query family for eighteen rounds and mistook its exhaustion for the
absence of work — while a 60% win sat in the innermost loop of the hot path, and the
technique to find it was already written in the docstring of the adjacent function. When a
vein runs dry, change the instrument before concluding the mine is empty.**


## Round 206 — the next hot spot, and a table that had to be guarded

Re-profiling after R205 moved the leader board. `_best_with_removed_base` is now the
largest self-time (1.70s of a 3.0s scan, a million calls) — it is already carefully
optimized, with a documented two-pass prefix/suffix decomposition, so it is left alone
for now. The cheap win was one line below it in the profile:

    4,000,002 calls   types/sequence.py:142(<genexpr>)

A dict lookup per base, building whole-contig reverse complements. `str.translate` does
the same thing in C: **96% faster, 27x**, verified identical on plain ACGT and on the full
IUPAC alphabet.

The interesting part is why it needed a test rather than just a benchmark. `translate`
leaves an *unmapped* character unchanged, where `_COMPLEMENT[base]` raised `KeyError`. So
the substitution is equivalent only while every base a `DNASequence` can hold has an entry
in the table — and the consequence of that ceasing to be true is not an exception, it is a
reverse complement with an uncomplemented base in it. Silent, and wrong in a sequence
someone orders.

The two sets are equal today (`ACGTRYSWKMBDHVN`, both). `test_every_validated_base_has_a_complement`
is what keeps them equal, and the mutation for it is the real one: adding `U` to
`IUPAC_ALPHABET` and nothing else fails the suite instead of silently passing uracil
through. This is R199's shape used deliberately rather than found by accident — the
optimization has a precondition, so the precondition gets the test.

Across R205 and R206 a default 2 Mb scan went 2.62s -> 1.90s, 27%, golden unchanged.

Also, a process note. The first attempt at this patch did not apply — the anchor placed
the translate table *above* the dict it is built from — and the verification I ran
afterwards passed anyway, because it compared the new implementation against the naive
one and both were the old code. `git diff --stat` was empty and I nearly missed it. The
project's rule "verify the mutation, not just the test's reaction to it" has a twin:
verify the *patch*, not just the test's reaction to it.

**Lesson: an optimization that replaces a raising lookup with a forgiving one has bought
speed with a silent failure mode. That trade is usually right and always worth naming: the
question is not "is it faster" but "what did the old code refuse to do that the new code
will do quietly", and that answer is the test.**


## Round 207 — a measured dead end in the remaining hot spot

After R205 and R206, `_best_with_removed_base` is the largest single cost in the scan:
1.70s of 3.0s, 1,002,524 calls (two per PAM-positive anchor, one per bulge direction —
the caller guards both correctly, so none of those calls is waste).

The function is already carefully optimized: both passes stop the moment the budget is
blown, and the search range is bounded from both ends. What remains per call is two
21-element list allocations, and the measurement that made them look worth attacking:

    20000/20000 calls return None (100.0%)   on random sequence

Every one of those million calls allocates two lists and throws them away. Three variants
were written and each checked against the current implementation over 60,000 randomized
shapes and budgets before being timed:

    variant          random (all reject)   survivors   mixed
    bound-first             +25.9%          -64.7%     +6.6%
    rolling, no lists       +24.2%          -52.7%    +11.4%
    one list, rolled suffix +14.6%          -36.5%     +0.9%

All three buy the reject path with the survivor path, because a survivor makes the
bounding passes run to completion and then pays for the accumulation again. **Not
shipped.** The reject path dominates on random sequence, but the survivors are where the
scientific output is — a real off-target, a repetitive region, a segmental duplication —
and I cannot measure a realistic survivor rate without real genomic sequence, which this
repo deliberately does not ship. Optimizing for the synthetic distribution while
pessimizing the meaningful one, on an assumption I have no way to test, is a bad trade
made confidently.

Where the remaining win actually is: this is interpreter overhead on a million calls of a
twenty-element loop, and the project already has a Rust kernel doing the FM-index search,
k-mer seeding and haplotype walking. This function is the obvious next thing to move
across, and that is a change for someone with the toolchain built (`pip install maturin`,
then `maturin develop`), not a Python micro-optimization.

**Lesson: a 100%-of-calls measurement is not a 100%-of-cases measurement. "Every call
returns None" was true of the benchmark and false of the workload that matters, and three
variants were written before that distinction surfaced. Ask what the distribution looks
like where the answer is interesting, not only where it is common — and when the
distribution cannot be measured, that is itself the reason not to ship.**


## Round 208 — the kernel the previous round pointed at

R207 measured three Python rewrites of `_best_with_removed_base`, shipped none of them,
and said where the remaining win actually was: interpreter overhead on a million calls of
a twenty-element loop, in a project that already has a Rust crate doing the FM-index,
k-mer seeding and haplotype walking. Both `cargo` and `maturin` are present here and the
crate was already built, so that was a recommendation I could act on rather than defer.

`rust/src/align.rs` implements the same two-pass prefix/suffix decomposition, wired
through the crate's existing conventions: a `native_align_available()` probe, a dispatcher
that resolves the symbol **once at import** (an availability check inside a million-call
loop would eat the win), and `_python_best_with_removed_base` kept as the fallback.
Measured end to end on the same 2 Mb reference:

    python  min=2.031s   1 site, spec 0.586837
    native  min=1.155s   1 site, spec 0.586837     +43.2%

Identical results, and the reproducibility golden is unchanged. Across R205, R206 and this
round the same scan went 2.621s -> 1.155s, 56%.

The kernel found a bug in the function it was copying. The Python documented a
precondition — `longer` is exactly one base longer than `shorter` — and never checked it.
Violated, it raised `IndexError` for most shapes, and for a **two**-base-longer input it
silently returned a wrong alignment: `("ACGTAC", "ACGT")` gave `(0, "ACGTC")`. Unreachable
from the scan, which slices the window to exactly `n + 1`. But writing a second
implementation forced the question "what does this do off its contract", and the honest
answer was three different things depending on how far off you were. Both paths now
refuse, which is also what makes the parity claim true *everywhere* rather than only on
the inputs the caller happens to produce.

That the edge cases were in the parity test at all is why it was found: the randomized
generator only ever produces well-formed pairs, and it passed. The eight hand-written
shapes at the bottom of the file are the ones that failed.

**Lesson: porting a function to a second language is a specification exercise. The
translation cannot inherit "whatever the original happens to do off its contract" — it has
to decide — and every place the two implementations disagree is a place the original was
relying on its callers rather than on itself. Three rounds in this log found bugs by
writing a second implementation of something (the pysam differential, R205's naive
comparison, this one); it is a more reliable instrument than reading the code.**


## Round 209 — the command that could not read its own output

`aforge design --out X` writes the result to `X` and a `X.provenance.json` sidecar
holding the run's `Provenance` block. `aforge verify` is the command that, in its own
words, turns provenance from a record into a checkable contract. Handing it that sidecar
printed:

    error: not a valid result JSON: 1 validation error for RankedMenu
    candidates
      Field required

It only ever parsed a full `RankedMenu`. That is not a cosmetic gap in a niche path: for
`--format tsv`, `html` and `pdf` — three of the four output formats — the sidecar is the
*only* machine-readable provenance the run leaves behind, so the contract was
unreachable for every one of them. And the error pointed at the wrong thing. Nothing is
wrong with the sidecar; the file named in the message is the file the tool just wrote.

The fix is small because every check `verify` performs reads `prov` and nothing else —
completeness, and the `--cache-dir` re-hash of pinned checkpoints and datasets. The menu
was only ever an envelope. `verify` now tries `RankedMenu` and falls back to `Provenance`,
and the two paths reach a byte-identical `--json` report on the same run, which is the
property the test pins rather than "it exits 0". Widening the input must not widen it to
anything, so a file that is neither shape is still `USAGE` and now names both shapes; a
menu whose `provenance` is `null` is still `UNAVAILABLE`, not mistaken for a bare block.

This is the memory's own query — *audit the honesty mechanisms* — run against the one
surface that had not been pointed at itself. It was found by running the product, not by
reading it: the tsv run was a spot-check of an output format, and `verify` on the sidecar
was the next thing a user would obviously type.

A process note worth more than the fix. The first patch applied cleanly and the tests
still failed with the *old* error text. The venv here is an editable install of the main
checkout, not of this worktree, so `pytest` had been importing the unmodified package all
along — including the baseline suite run. `PYTHONPATH=$PWD/src` fixed it. R206 recorded
"verify the patch, not just the test's reaction to it"; this is the same lesson from the
other side. There the patch had not applied and the test passed. Here the patch applied
and the test failed. Both times the thing being tested was not the thing being edited,
and both times the tell was a result that did not move when it should have.

**Lesson: a green suite in a worktree proves nothing until you have confirmed which copy
of the source the interpreter is importing. `pip install -e` pins a path, and a worktree
is a different path.**


## Round 210 — the warning that pointed at a flag nobody has

`--region`'s help, identical on `design`, `batch` and `offtarget`, said the locus is
0-based half-open, "NOT the 1-based form a genome browser shows (unlike `--variant` and
`--pop-freqs`, which take 1-based VCF positions)".

Neither flag exists. The variant is a positional argument, and the population
allele-frequency file is `--gnomad`. `docs/data.md` repeated both names, and a comment in
`tests/report/test_builder.py` cited them as the reason its assertion was there.

This is not a typo in decoration. Mixing the two conventions moves a locus by one base,
which is how a scan silently covers the wrong window, and this sentence is the only place
the tool warns about it. A reader who took the advice went looking for `--pop-freqs`,
found nothing, and was left with a warning they could not act on. `--help` is where a CLI
user looks first, and it was the surface nothing checked.

Two more things fell out of writing the check. `lift`'s docstring says its output pipes
back into "the same locus form `--region` accepts" — true, but `lift` has no `--region`,
so the reader has to already know which command does. And the R209 entry immediately
above this one introduced a fourth, naming `--format` and `--out` in `verify`'s help,
where they belong to `design`. Both are now qualified (`design --region`), which the
check accepts precisely because it resolves a qualified mention against *that* command.

The fix is the check, not the four sentences. `test_help_text_names_real_flags` walks
every command and asserts that every long option named in any of its help strings is
either its own or explicitly qualified by the command that has it. What is actually true
of the inputs also got written down while it was in hand: `--gnomad` and `--patient-vcf`
are 1-based, and `--haplotypes` — the one user-supplied file whose base was never stated
anywhere — is 0-based, in its span *and* in the `pos` of each `chrom:pos:ref>alt`.

The walk needed a guard of its own. The first version tested `isinstance(cmd,
click.Group)`; Typer builds a `TyperGroup` that is not a `click.Group` subclass, so it
descended into nothing, collected one command, and passed. Seventeen tests where there
should have been seventeen was not the tell — "2 passed" was. A test that walks a tree
needs an assertion that it reached the leaves, and there is now one.

**Lesson: `--help` is documentation that ships inside the binary, and it drifts exactly
like a README does — except no build step reads it. Cross-references in it are the
brittle part, because renaming a flag fixes the definition and leaves every sentence that
mentions it. Prose about flags can be checked mechanically against the flags; do that
rather than proofreading it.**


## Round 211 — the setting that was documented and ignored

`docs/deployment.md` tabulates the `ALLELEFORGE_*` variables a deployer sets. The first
row was the reference build, as `ALLELEFORGE_REFERENCE_BUILD`. The `Settings` field is
`reference`, so the variable the software reads is `ALLELEFORGE_REFERENCE`:

    ALLELEFORGE_REFERENCE_BUILD=mm39  ->  Settings().reference == 'hg38'
    ALLELEFORGE_REFERENCE=mm39        ->  Settings().reference == 'mm39'

No warning, no error. A deployer who sets the build from the documentation gets hg38 and
believes they have mm39, and every coordinate downstream is then interpreted against the
wrong genome. This is the shape the log keeps returning to — a real input inert on the
axis it names, with nothing anywhere saying so — and it reached the config table because
`env_prefix` derives variable names from field names, so renaming or naming a field never
touches the prose that documents it.

The same table omitted `ALLELEFORGE_ALLOW_NETWORK`, the switch governing whether the
library may reach the network at all, and listed the cache directory under `XDG_CACHE_HOME`
alone when `ALLELEFORGE_CACHE_DIR` takes precedence and is what `--cache-dir` exports.

`test_documented_env_vars_are_read` is R210's query one surface over: prose that names an
interface can be checked against the interface. A name is honored if it is a `Settings`
field under the prefix or if `src/` hands its literal to `os.environ`; anything the docs
name that is neither fails. Because "honored" is derived rather than listed, three of the
names are also exercised for real — set the variable, assert the setting moved — so the
derivation cannot drift into agreeing with a table that is wrong.

Writing the scan cost one false accusation worth recording. Its first `os.environ`
pattern captured `[A-Z_]+`, which does not match a digit, so `ALLELEFORGE_PRIDICT2_REPO`
and `ALLELEFORGE_PRIDICT2_PYTHON` were reported as documented-but-unread when both are
read a line apart in `pridict_engine.py`. A checker that names innocent surfaces gets
switched off, and the failure mode is quiet: had those two been the *only* hits, the
obvious response would have been to delete two correct lines of documentation. The three
"is not vacuous" assertions in this file and the last are cheap next to that.

**Lesson: a settings framework that derives environment-variable names from field names
has moved the name out of the code and into a convention, and a convention cannot be
grepped for by the person editing the field. Every derived public name — env vars, CLI
flags, JSON keys — needs a test that walks from the docs back to the definition, because
nothing else will.**


## Round 212 — the endpoint that was on one table and not the other

`docs/api/web.md` heads a table "Endpoints" and lists nine. The app serves ten.
`POST /api/batch` — cohort design over a variant list, per-item summaries and
provenance, a failed item isolated rather than failing the run — was missing from the
page a reader reaches from the documentation navigation. The README's copy of the same
table has it, which is how the gap survived: each document is right about what it says
and wrong only by comparison, and nobody diffs two tables in two files.

An undocumented endpoint is not a broken one. The route works, its tests pass, and every
gate in `make ci` was green over it. That is the whole reason this class needs a check
rather than a proofread: there is no failure to notice.

`test_the_docs_list_every_endpoint` is R211's check run in the opposite direction.
R211 asked whether every documented name is real; this asks whether every real name is
documented. Both are needed and they catch different things — a name that goes nowhere,
and a capability nobody can find. It normalizes `{...}` away, so the docs' `/api/jobs/{id}`
matches the route's `/api/jobs/{job_id}`: the parameter's name is an implementation
detail, and a check that fails on it would be turned off within a round.

Confirmed by mutation rather than by its own green: deleting the row that had just been
added fails exactly the one surface, and only that surface.

**Lesson: when the same table exists in two documents, one of them is already out of
date. The fix is not to reconcile them but to derive the check from the code both are
describing — then a third copy costs one line in a parametrize instead of a fourth
opportunity to drift.**


## Round 213 — a config file that could not be written in TOML

R209's query was "for every artifact the tool writes, feed it back to the tool that
consumes that kind of artifact". A design result records a `config_snapshot` in its
provenance, the docs say a run is "re-derivable from its config plus seed", and
`--config` takes a run-config TOML. So: turn the snapshot into a TOML file and hand it
back.

    AttributeError: 'list' object has no attribute 'split'

`weights` is on `_RUN_PARAM_KEYS`, so `_load_config` accepts it with no typo warning and
passes it to `_parse_weights`, which only ever handled the CLI's
`"eff,clean,safe,simple"` string. A TOML array crashed. A TOML table crashed. The table
is not a hypothetical spelling — it is exactly how `provenance.config_snapshot` records
the weights, so the user most likely to write it is the one reconstructing a run from its
provenance, which is what provenance is for.

Then the documented example found the second one. Writing a run-config block for
`docs/api/cli.md` — the file was referenced as `run.toml` in three places and its
contents shown nowhere — and running it produced the same traceback from `populations`,
where the flag takes `afr,eur` and TOML naturally writes `["afr", "eur"]`. Same
mechanism, one key over: **every whitelisted config key whose flag is a comma-separated
string had this defect**, and the whitelist is what suppresses the warning that would
otherwise have been the only sign.

Both now take either spelling, a malformed one is a usage error naming what was expected
rather than a traceback, and the three weight spellings are pinned as producing the same
run. The documented TOML block is extracted from the markdown and executed by a test, not
proofread — it is a config file, and a config file that has never been fed to the program
is a guess.

One detail worth keeping. `populations` reaching the search is not directly observable in
the menu; what proves it parsed is that the reference-only ancestry warning fires. The
honesty mechanism turned out to be the assertion.

**Lesson: a whitelist of accepted keys is a promise about a type as much as a name.
`_load_config` said "this key is known" and then handed it to a parser that knew one
encoding of it, so validation ran and told the user their file was fine two lines before
the program crashed on it. Whenever the same knob exists as a flag and as a config key,
the config file's own native type is a case the parser must handle — the flag's string
form is the special case, not the general one.**


## Round 214 — two genomes, one provenance

Continuing R213's round trip, the question became what provenance actually pins. Two
designs, same variant, same flags, two different reference FASTAs:

    a.fa   0 off-target sites   specificity 0.879
    b.fa   1 off-target site    specificity 0.468

    provenance identical: True

Byte for byte, timestamp aside. And `aforge verify` called both "provenance is complete
and consistent". The block recorded `reference_build: "hg38"` — a *label*, which stays
`hg38` whatever FASTA is handed to `--reference-fasta`. `_collect_datasets` does record
the reference, but only when it carries a `DatasetVersion`, which a registry-resolved
build has and a local FASTA does not. The ordinary, documented way to supply a genome
left the genome unnamed, and the reference is the single largest determinant of an
off-target result.

`config_snapshot.reference` now records a descriptor in the shape `offtarget_regions`
already established: build label, contig count, base count, and a content hash of the
canonicalized `name:length` list, read from the `.fai` so the cost is O(contigs) rather
than the size of the FASTA. `ReferenceGenome.contig_lengths()` is the new public
accessor for that.

What it deliberately does not do is hash the bases. Hashing three gigabytes per run is
not a thing this tool can do on every design, so the descriptor pins the reference's
*shape*, and two FASTAs with identical contig names and lengths and different bases are
indistinguishable to it. That limit is in the record itself — `"pins": "contig names and
lengths, not the bases"` — and in the rendered footer, because a digest that quietly
overclaims its own reach is precisely the failure this project spends its time
preventing. A weaker pin that says what it is beats a stronger-sounding one that does
not.

**The project caught this change before the suite finished.**
`test_config_snapshot_reaches_a_reader` failed with "config_snapshot keys with no route
to a reader: ['reference']". Recording a fact is not showing it, the footer's omission
list is only allowed to skip `config_snapshot` because every key is rendered where it
takes effect, and adding a key without a route would have quietly widened that
exemption. The footer now reads:

    reference build hg38 (1 contig, 140 bases, shape 379efc3d — pins contig names and
    lengths, not the bases)

That guard was written in an earlier round for exactly this, and it is the first time in
this log that an existing mechanism, rather than a new query, found the round's mistake.

**Lesson: an identifier that the caller chooses is not an identity. `reference_build`
looked like provenance for four hundred kilobytes of README because it is a real field
holding a real value — but nothing in the system ever checked it against the bytes it
named, so it recorded an intention. When auditing a provenance block, do not ask what it
contains; ask which two runs it can tell apart, and construct the pair.**


## Round 215 — the same question, asked of the other inputs

R214's query was "which two runs can this record tell apart?", so it got asked of every
user-supplied source in turn. gnomAD: pinned by content hash, clean. Haplotype panel:
pinned, clean. Patient VCF: versioned `n=1` — a count, so two patients are
indistinguishable — but that is a **deliberate** decision with its reasoning in the
code beside it ("fingerprinting the file itself would put an identifier for a person's
genotypes into a report meant to be shared"), and it is the right call. Not a finding.

The ENCODE accessibility track was the one that fell through.

    d1.bg (signal 0.9)  ->  efficiency 0.484
    d2.bg (signal 0.1)  ->  efficiency 0.457
    provenance identical: True        datasets: []

`_collect_datasets` is explicitly handed `encode_tracks` alongside the haplotype panel
and the patient variants, and `_attach_source` tags the other two. The ENCODE loader
was the only one that never called it, so the design side was looking for a descriptor
the CLI never attached. The snapshot recorded `chromatin_track` — a *name* — which is
`reference_build` from the previous round, one input over: a value the caller chose,
standing in for the data it refers to.

Running the case found a second defect the query would not have. `--chromatin-track`
naming a track absent from the file raised `KeyError` inside the chemistry, which
caught it as a decline reason:

    prime: skipped (KeyError: "unknown track 'track'; known: ()")
    wrote w.json      EXIT=0      candidates: 0

An empty menu, a success exit, and the cause buried in a rationale paragraph.
`_load_encode_tracks` exists precisely to stop a silently-unapplied chromatin
adjustment — its docstring says so — and it checked that the two flags were given
together while never checking that the name resolved. **A guard covered the typo it was
written for and not the adjacent one.** The name is now checked where it is supplied,
and the refusal lists the names the file does contain.

The way that surfaced is worth recording, because it was luck dressed as method: the
first bedGraph fixture had a track literally named `track`, and the parser drops lines
beginning `track`/`browser`/`#` as UCSC directives. My fixture was wrong, the run
produced zero candidates and exit 0, and chasing *my* mistake is what exposed the
program's. A file that parses to no tracks at all is now refused too, naming why.

**Lesson: a validation function is a claim about a set of failures, and the set is
almost always smaller than its docstring implies. `_load_encode_tracks` promised that a
half-supplied chromatin adjustment could not be silently ignored, and delivered it for
one of the two ways to half-supply one. When reading a guard, do not check that it does
what it says; enumerate the ways the input can be wrong and find which ones it misses.**


## Round 216 — the web API answered a question it was not asked

The web is one of the three audiences and the shell I had never actually driven, so
this round drove it: health, resolve, design, batch, jobs, offtarget, data, bench. Most
of it is in good shape — the R214 reference descriptor reaches the API, and
`/api/offtarget` already returns `on_target_excluded`, which is the disclosure the CLI
prints in words.

Then, against the README's own claim that "everything that is *data* rather than a
path … is available over HTTP":

    POST /api/offtarget {"spacer": ..., "scorer": "cfd-cas12a"}   ->  200
    effective_matrix: doench-2016-cfd

`OffTargetRequest` had no `scorer` field, and pydantic's default for an unknown key is
to **ignore** it. The client asked for the Cas12a analog and was served the SpCas9 CFD
matrix, with a 200 and no mention of the substitution.

`pam` *is* settable over HTTP, which makes it worse than a missing feature. A Cas12a
search was already reachable — `pam: "TTTV"` — and its result came back labelled
`doench-2016-cfd`, the published, cross-verified matrix, where the CLI labels the same
run `cas12a-analog-approximation (unvalidated)`. Not a missing capability: a **wrong
honesty label**, on the surface where a number is most likely to be consumed by a
machine that will not read a caveat.

`scorer` is now a field, resolved through the same `scorer_for` the CLI uses, so an
unknown name is a 422 listing the valid ones and the Cas12a label follows the choice.

The silence is the more general defect, so **every API request model now forbids
unknown fields**. `populatoins`, `intnet`, `buidl` were all 200s describing a run the
client had not asked for; each is now a 422 naming the offending key. That is four
models, not one, because the ignore-by-default was never a decision anyone made about
`OffTargetRequest` — it was pydantic's default sitting under all of them.

One more thing the round confirmed rather than fixed: `--scorer mit` with bulges
enabled refuses, with a reason ("the MIT score is undefined for bulged alignments"),
and that refusal survives the HTTP boundary as a 422 instead of becoming a 500. Pinned,
since it was the one path where a library-level `ValueError` could have escaped.

**Lesson: a schema that ignores what it does not understand answers a different
question than the one it was asked, and returns 200. Where the extra field names a
scientific choice — a scorer, a threshold, a model — the client then attributes the
server's answer to their own request. Forbidding unknown fields is not strictness for
its own sake; it is the difference between "I did not do that" and silence.**


## Round 217 — the differentiator had the only uncaught parser

This round fed each user-supplied file format a malformed version of itself. The
honesty machinery came out well: a gnomAD file whose ancestry column is misspelled
produces the full "requested but not examined … absence from the breakdown means 'no
data', not 'no risk'" disclosure, which is exactly right. The haplotype loader names
the missing column and prints the expected header. BED and bedGraph surface a caught
`ValueError` and exit 3.

`--gnomad` raised `KeyError: 'af'` as a bare traceback.

    chrom  pos  ref  alt          (a row with its trailing columns lost)
    KeyError: 'af'

`zip(header, cols, strict=False)` truncates silently, so a short row simply lacked the
keys the parser then indexed, and `_load_gnomad` catches `(OSError, ValueError)` —
`KeyError` is neither. Of the five formats, the one with the raw traceback was the one
that makes the scan population-aware, which is the capability the whole project is
built around. A truncated download of a real gnomAD slice is not an exotic input.

The fix follows the haplotype loader, which was already the right shape, and separates
three cases wanting three different answers: a header missing a core column (nothing in
the file is usable — print what is expected), a row that cannot supply the core columns
(name the line and the field count, so a truncated file can be found), and a header
naming the same column twice (`dict(zip(...))` kept the last silently — two frequencies
for one ancestry have no single meaning). A row that omits only *trailing population*
columns stays legal, because a ragged tail is ordinary and an absent per-population
value was already treated as absent.

The duplicate-column case is the one worth noticing. It never crashed and never
warned: `afr` twice, at 0.08 and 0.99, and the scan quietly used 0.99. Refusing it is
not defensive programming, it is declining to pick one of two answers on the user's
behalf.

**Lesson: when one member of a family of loaders is unguarded, it is not random which
one. Look for the format that arrived first, or the one nobody hand-edits — and then
check whether it is also the most important. Here it was both, and the exception type
was the tell: every sibling raised `ValueError`, so the `except` clause that had been
written once and copied everywhere silently did not apply to the one that raised
`KeyError`.**


## Round 218 — the spreadsheet was the one surface with no caveat

R217's query — "when one member of a family is unguarded, which one?" — asked of the
renderers. Four of them serialize the same `DesignReport`:

    0-based                            tsv:.  html:Y  pdf:Y  json:Y
    reference build                    tsv:.  html:Y  pdf:Y  json:Y
    must be experimentally validated   tsv:.  html:Y  pdf:Y  json:Y

`build_report` puts `RESEARCH_USE_DISCLAIMER` on the report; `report_to_tsv` was a
header and one row per candidate, and emitted none of it. So the format a scientist
opens in a spreadsheet and forwards to a colleague showed efficiencies, specificities
and genomic loci with nothing saying they are uncertain computational predictions,
against which genome, in which coordinate convention. The README even claimed the
convention was "stated in the report's own provenance block" for the TSV — which has no
provenance block, and whose `.provenance.json` sidecar carries no coordinate note
either.

This is the third time the log has caught the TSV specifically. `test_the_flat_export_
carries_what_makes_its_numbers_readable` was written for the same shape one layer up:
"the HTML and PDF renders have carried the specificity, the scoring basis and the search
settings since each was added; the TSV — the format something automated actually reads —
carried none of them". Per-candidate context got fixed then; the whole-document context
did not, because it was never anywhere in the file to fix.

The notes now lead the file as `#` comment lines, which is what VCF, GTF and bedGraph
do. The column header remains the first non-comment line, so a comment-skipping reader
gets a byte-identical table — checked with polars rather than asserted, by parsing the
file twice and comparing the frames.

**This changes an output format, which is a user-visible decision and worth naming.** A
reader that skips nothing now sees a different first line. Three things make it the
right trade: the export has always led every row with `schema_version` precisely so a
consumer can detect drift (now 6); the project is pre-1.0 and its cardinal rule is that
no surface shows a number without its caveat; and six of its own tests assumed line 0
was the header, which is the honest measure of the blast radius — small, and all inside
this repo.

**Lesson: "which renderer is missing this?" is a question worth asking on a schedule,
not once. A fix lands in the render the bug was noticed in, and the family drifts again
the next time a fact is added — this round's missing facts include one added two rounds
ago. The durable version of the check is a table of fact x surface, which is what the
top of this entry is.**


## Round 219 — making the previous round's lesson a test

R218 ended by saying the durable form of "which renderer is missing this?" is a table
of fact x surface. Writing that table found the remaining hole on the first run:

    fact                 html    tsv   json    pdf
    disclaimer              Y      Y      Y      Y
    coordinates             Y      Y      .      Y
    reference identity      Y      Y      Y      Y
    build / seed / models   Y      Y      Y      Y

`report_to_json` — the machine-readable export a pipeline consumes — states **no
coordinate convention at all**. Its `locus` is a formatted string
(`chr2:43-63 (+), nick 60`), and the `Provenance` model it embeds has no coordinate
note, because that note lives in `provenance_lines()`, a render helper the JSON never
calls. Every locus in the document is 0-based half-open; a genome browser reads the
same digits as 1-based inclusive, which is the whole reason the note exists.

`DesignReport.coordinate_system` is now a field rather than a sentence, because the
consumer of this surface is a machine and making it grep prose for the convention is
the same mistake in a smaller font. It reaches `/api/design` for free.

The table also corrected two things I had measured wrong before writing it down. The
PDF looked like it was missing the reference shape; it was not — the text is there and
merely wrapped across a line, so the needle has to be short. And the "reference
identity" fact has two encodings — eight hex characters in the prose renders, the whole
hash in the JSON — so the check keys off the run's own digest rather than a literal.
**A fact x surface table is only as good as its needles, and a needle tuned on one
surface will libel another.**

The omission list is the mechanism that makes this last: a render that legitimately
should not carry a fact has to say so, with a reason, in `OMITTED`. It is empty today.

Two more of the project's own guards then caught the fix, which is the third time in
this stretch. `test_every_report_field_is_rendered` refused a `DesignReport` field no
renderer reads — true, because the JSON serializes every field wholesale and names
none of them — so the omission is recorded with its reason, and `COORDINATE_SYSTEM` is
now the single constant the slug and the prose sentence both come from, with a test
that they still agree. And `test_committed_schemas_match_the_code` required the
exported JSON Schema to be regenerated, which is how a new public field reaches the
documented contract rather than only the code.

**Lesson: when a round ends by naming the general form of its bug, write that form as
a test in the next round or the naming was decoration. The check took twenty minutes
and found a real gap before it had ever run in anger — which is the argument for it,
because the gap it found had survived every round that looked at the JSON export
directly.**


## Round 220 — the cohort summary was outside the table

R219's fact-by-surface check covers the four renders of a `DesignReport`. A cohort
summary is not one of them, so running `aforge batch` and asking the same question
found the same hole one artifact over:

    not a medical device     sum.tsv:.   item.json:.
    0-based                  sum.tsv:.   item.json:Y
    reference identity       sum.tsv:.   item.json:.
    build / seed             sum.tsv:.   item.json:Y

`--summary-tsv` is the file a whole-cohort run is read through and the one that gets
forwarded — one row per patient, with efficiencies, specificities and off-target
counts — and it carried none of the five. It now leads with the same `#` note block
the per-design export got in R218.

Building those notes exposed the second half. `CohortRunReport.provenance` is a plain
dict the cohort runner assembles by hand rather than the `Provenance` a menu carries,
and it records `reference_build` — a *label* — and nothing about the genome. That is
R214's finding, still standing in this path six rounds later, and it stood because the
fix landed on the object the cohort does not use. The run header now carries the same
`_reference_snapshot` descriptor the per-item menus do.

Then the parallel path printed:

    # reference build None

Under `--max-workers` the reference is opened per worker, so there genuinely is no
run-wide genome to name — `_build_name` returns `None` on purpose, with a comment
saying why. But `None` in a report reads as a missing value rather than a located one,
which is the failure this project spends its rounds on. It now says that each item's
own result records the genome it used, which is both true and actionable.

**Lesson: a check is scoped to a type, and the drift happens in whatever is not that
type. R219's table walks `DesignReport` renders; the cohort summary is assembled from
dicts by a different module and was therefore invisible to it. When a guard is keyed
on a class, the next question is which artifacts do the same job without being that
class — and here the answer was the one with a row per patient.**


## Round 221 — the differentiator's own artifact was contextless

R220's lesson gave the query directly: a guard keyed on a class misses whatever does
the same job without being that class. `aforge offtarget --json` is not a
`DesignReport` and not a cohort summary, so neither check had ever looked at it.

    not a medical device   offtarget.json:.
    coordinate convention  offtarget.json:.
    reference identity     offtarget.json:.

Its *per-search* honesty is among the best in the codebase — `on_target_excluded`,
`searched_bases`, `resolved_bases`, `effective_matrix`, the ancestry stratification,
each added by an earlier round for a good reason. What it never had was
document-level context: a consumer holding the file knew every budget and cut-off and
not which genome produced the numbers. Two scans over two different FASTAs give
different specificities and, before this, indistinguishable payloads. Its `locus`
strings are 0-based half-open and nothing said so.

That this artifact is for **population-aware off-target nomination** — the capability
the project exists for — while being the last one with no provenance at all is the
part worth sitting with. Rounds attend to what they are already looking at, and this
file had been looked at often, always one field at a time.

Both shells now carry it. The CLI prints one line under the search description rather
than repeating it per site row, and the `--json` payload and `/api/offtarget` response
carry `reference`, `coordinate_system` and `disclaimer`. The HTTP surface is where it
matters most: the client cannot see the FASTA the server opened, so a build label
there is a name chosen by someone else entirely.

**Lesson: "per-item honesty" and "document honesty" are different properties and the
first does not accumulate into the second. This payload had eight carefully-added
qualifiers on its numbers and no statement of what the numbers were about. When a
surface has been improved many times in small pieces, ask what a reader needs that is
true of the whole file — that is precisely the fact no single small improvement was
ever about.**


## Round 222 — the column next to the one that was already fixed

The frontend's cohort table has a test called
`test_the_browser_cohort_table_never_shows_a_bare_estimate`, written by an earlier
round because the table rendered `0.61` with no interval. It fixed the **efficiency**
column. The column beside it read:

    worst off-target
    0.000

`worst_offtarget` alone is the most reassuring number this system can produce and the
least interpretable one. The batch response the table is built from also carries
`best_specificity` — the aggregate the whole scan is summarized by — and
`offtarget_sources`, which is `{}` when no population source contributed. Over HTTP
that is *always* the case, because no file-backed source can be supplied to a
deployment, so every cohort row in the browser was showing a reference-only result as
a clean one. The table now reads:

    worst off-target  specificity  off-target basis
    0.000             0.879        reference-only     <- in the error style

Verified in a real browser, not only by test: the SPA was served, a three-variant
cohort submitted through the form, and the rendered row read back from the DOM with
its class attributes, because "the string is in app.js" and "the cell renders" are
different claims and this file's whole purpose is the second one.

The shape is R217's again, at its sharpest. When one member of a family is unguarded
it is not random which — and here the family was the *columns of a single table*, and
the guarded one was the column somebody had already been burned by. The fix for the
efficiency column did not generalize to the row it lived in, because a fix generalizes
only as far as the sentence that motivated it.

**Lesson: the strongest predictor of an unfixed instance is an adjacent fixed one. A
test named "never shows a bare estimate" is a claim about a table; check it against
every column, not the one in the commit that added it.**


## Round 223 — a per-base Python loop over a whole contig

Profiling a 2 Mb scan after the R208 native kernel, the largest single remaining cost
was not in the search at all:

    0.272s cumulative   {built-in method builtins.all}   1 call
    0.160s              <genexpr> at _search.py:449      2,000,001 calls

`_sanitize` folds every base outside `ACGTN` to `N` so the linear scan and the
FM-index path agree about what a window holds. It did so with
`all(b in _INDEX_ALPHABET for b in seq)` and a comprehension — one pass of interpreter
overhead per character of a reference, once per sequence per `search()`, uncached,
and `search()` runs once per candidate in a design.

`str.translate` does both halves in C. The detection deletes every in-alphabet base
and asks whether anything is left. The substitution then **derives its table from the
strays themselves**, which is the part worth keeping: a character absent from the
table is by construction in the alphabet, so `str.translate` leaving it alone is
exactly right, and there is no fixed 256-entry table to get wrong on a non-ASCII byte.

Measured on the function, over its real inputs:

    2 Mb   old 59.8ms   new  3.3ms    +94.5%
    20 Mb  old 775.4ms  new 35.2ms    +95.5%   (linear, as expected)

Unlike R207, there is no distribution to trade against: clean +92%, one stray base in
2 Mb +94%, a synthetic 44%-IUPAC sequence +78%. The first draft used
`re.sub(r"[^ACGTN]", "N", seq)` for the rebuild and was **7% slower** on that last
case; deriving the table is what removed the trade rather than relocating it.

**What I am not claiming.** The end-to-end 2 Mb scan does not visibly move: 1.098s
before, 1.090s after, against run-to-run noise of ±7% on this machine. A 56 ms saving
is real and directly measured at the function, and it is below the resolution of the
harness that would have to see it. The case for shipping it is the scaling, not a
stopwatch on a toy contig — 740 ms per 20 Mb call, per candidate, per contig.

Two process notes, both mine.

I ran `git checkout -- src/alleleforge/offtarget/_search.py` to undo a deliberate
mutation and **deleted the round's optimization**, which is the exact trap this log
recorded in R96 and my own notes warn about in one line. Knowing a trap by name is not
the same as having a habit that avoids it. The patch was re-applied from the text I
still had; had it been hand-edited it would have been gone.

And the mutation itself was ill-posed. I widened `_INDEX_ALPHABET` expecting the check
on the deletion table to fail — but the table is *derived from* that constant, so both
sides moved together and the check was tautological. A guard on two things that cannot
disagree tests nothing. The check now constructs a mismatched table directly, and its
docstring says plainly that it exists for the future edit which replaces the derivation
with a written-out literal.

**Lesson: when an optimization removes a hazard by construction, the test for that
hazard has to be rewritten, not kept. I wrote a guard against divergence and then made
divergence impossible in the same patch, which left a test that passes for a reason
unrelated to the one in its name — the most expensive kind, because it will be trusted.**


## Round 224 — a fifth kernel, and two decisions the Python had never made

R223's profile named the next two costs after the contig fold: `_evaluate` (0.503s
self, 501,262 calls) and `_best_ungapped` (0.465s, the same count). `_evaluate` is the
per-anchor entry point — it does the ungapped comparison in Python and then crosses the
FFI boundary twice more, once per bulge direction, into the R208 kernel. Moving the
whole decision into Rust replaces three crossings with one and removes the interpreter
loop with them.

`rust/src/evaluate.rs`, wired through the crate's existing conventions: a
`_native_evaluate_available()` probe, a dispatcher resolved **once at import**, and
`_python_evaluate` kept as the byte-identical fallback. Measured as interleaved A/B
pairs so the figure is not one run against another run's weather:

    before  1.184s  1.287s  1.274s  1.235s  1.256s
    after   0.893s  0.923s  0.869s  0.901s  0.887s        ~28%

Specificity identical to nine decimal places in every run.

**Porting is a specification exercise, and this is the second time in a row it has
found something.** Two off-contract inputs — the scan only ever reports a PAM it found
*inside* the sequence — where the Python's accidental answer was worse than an error:

* `pam_at` past the end of `seq`: Python sliced a short window and raised `ValueError`
  from a `zip(..., strict=True)` three frames down.
* the same with an **empty spacer**: every slice is legally empty, so the ungapped
  comparison returned a *zero-mismatch hit at a coordinate outside the sequence* — the
  most confident possible answer about a protospacer that does not exist.

Both paths now return `None`. In contract nothing changes: a slice that ends at or
before the end of the sequence always yields exactly the bases asked for.

The generator is the part to remember. My first randomized differential drew
`n = randint(2, 8)` and `pam_at <= len(seq)`, ran **200,000 cases, and reported zero
mismatches** — over two implementations that disagreed on both shapes above. Widening
it to `n >= 0` and `pam_at <= len(seq) + 3` found 5,355 disagreements in the same
number of draws. A differential test is only as wide as its generator, and a generator
written after the implementation inherits the implementation's assumptions about what
inputs exist.

I also kept the shared venv out of it: the wheel is built with `maturin build` and
unpacked into a scratch directory that goes on `PYTHONPATH` for the native runs, rather
than `maturin develop`, which would have installed a worktree build into the checkout
every other session shares.

**Lesson: "200,000 randomized cases passed" is a statement about the generator, not
about the code. Before trusting a differential, ask which inputs it cannot produce —
and note that the answer is usually the inputs whose handling was never decided, which
is exactly the set a port exists to surface.**


## Round 225 — the same site, two names, depending on an unrelated flag

Running the two commands I had never run — `resolve` and `lift` — turned up something
in neither. `aforge resolve 2:71:A>C` prints `2:70:A>C`, keeping the caller's bare
contig. That is defensible on its own; what it leads to is not:

    aforge offtarget ... --reference-fasta decoy.fa
      chr2:43-63(+)   chr2:140-160(+)

    aforge offtarget ... --reference-fasta decoy.fa --region 2:0-183
      2:43-63(+)      2:140-160(+)

Same guide, same genome, same two sites. Unscoped, the contigs come from the reference
and carry its spelling; scoped, they carry whatever was typed. **The identity of a
reported site depended on a scoping flag**, so two runs over one genome produce site
lists that do not join, diff or deduplicate.

Nothing was mis-searched — `canonical_contig` reconciles the styles, which is why both
runs find both sites. What was wrong was the name written down afterwards.

Fixing only the scope would have made it worse. The candidate locus comes from the
*variant*, so a `2:71:A>C` input against a `chr2` genome would then have produced a
candidate at `2:43-63` beside off-target sites at `chr2:…` — one document, one contig,
two names. Both boundaries are fixed together: regions are renamed where they meet the
reference in `search()`, and a variant is renamed in `resolve()` when a reference is
supplied.

The rename is always **toward the supplied genome**, which is what makes it safe rather
than opinionated: a bare-named FASTA produces bare-named output, so an Ensembl-space
user is never handed `chr` prefixes they did not ask for. `resolve` without a reference
renames nothing, because there is no genome to be named after. An unknown contig is
still refused rather than quietly renamed onto a different sequence.

**Lesson: reconciliation and naming are different problems, and solving the first hides
the second. `canonical_contig` made every lookup work regardless of spelling, which is
exactly why nothing ever failed and nobody asked which spelling came out the other end.
When a system accepts several spellings of an identifier, ask what it *emits* — the
answer is usually "whichever one it happened to be holding".**


## Round 226 — a true warning nobody can act on

R225's question — "when a system accepts several spellings of an identifier, what does
it *emit*?" — asked of ancestry labels. `docs/data.md` documents three vocabularies:
gnomAD's lowercase `afr`, 1000 Genomes' uppercase `AFR`, HGDP's `africa`. A caller who
reads that page, types `--populations AFR`, and supplies a gnomAD slice whose columns
are `afr` and `nfe` gets:

    no supplied source carries data for AFR — those ancestries were requested but not
    examined, and their absence from the breakdown means 'no data', not 'no risk'

Every word of that is true, and it is the honesty machinery working exactly as designed
— the request is not silently dropped. It is also unactionable. The report computed the
set of *backed* labels in order to decide that sentence, held `{afr, nfe}` in hand, and
did not say. One case away from the answer, and the caller is left guessing whether
their file is wrong, their flag is wrong, or their locus is wrong.

`available_populations` is now on the report and named in the description. Where no
ancestry source was supplied at all it says that instead, because listing an empty set
of alternatives would read as "these exist and yours is not among them" when the truth
is that nothing was supplied — a different problem with a different fix.

**What this deliberately does not do is match the labels.** Case-folding `AFR` onto
`afr` would make the warning disappear, which is why it is tempting, and it would be a
silent substitution of one cohort's frequencies for another's. gnomAD's `afr` and 1000
Genomes' `AFR` are different groupings of different samples. Naming the alternatives
puts the choice in front of the caller; matching for them would hide that there was one.

The reproducibility golden moved for the first time in this whole stretch of rounds, and
the diff is why the check is worth having: exactly one line, `available_populations:
added ([])`, plus the digest. A new field with an empty value and not one scientific
number touched — read field by field before updating, as the log's own note requires.

**Lesson: "the tool discloses it" is not the same as "the user can act on it", and the
second is where a disclosure earns its place. A warning built from a computation almost
always has the remedy sitting in a local variable — the set that decided the warning is
usually the set the reader needs. Check what the warning code already knows before
deciding it has said enough.**


## Round 227 — three refusals out of five said what to do instead

R226's lesson generalizes: a refusal built from a closed set usually has that set in a
local variable. So: which of this CLI's closed-vocabulary refusals print it?

    --scorer nope      unknown scorer 'nope'; choose one of: cfd, cfd-cas12a, mit      ok
    bench run nope     unknown task 'nope'; known: ('be-outcome', …)                   ok
    data show nope     unknown dataset 'nope'; known: ('1000g', …)                     ok
    --intent fixit     unknown intent 'fixit'                                          .
    --chemistry PRIME  unknown chemistry: 'PRIME' is not a valid Chemistry             .

Three to two, and the two are the flags on the primary command a first-time caller is
most likely to get wrong. The chemistry message is worse than silent: `'PRIME' is not a
valid Chemistry` is pydantic's, and `Chemistry` is the *class* — a word from the
implementation offered to someone who is being asked to use a vocabulary. It also names
only the first bad value of a repeatable flag.

Both now read like the three that were already right, on the CLI and on the web API.
The HTTP surface matters more, not less: there is no `--help` on the other end of a
`422`, so a client that cannot guess the vocabulary has nowhere to look.

The count is the finding, not either message. Five instances of one rule, three
following it, written at different times by whoever last touched that path — nobody was
wrong, and the rule was never anywhere. It is now five parametrized cases in one file,
so the next closed-set input joins the list or fails.

**Lesson: when a convention is followed in most places, the exceptions are not
oversights to fix one at a time — they are evidence the convention exists only in the
heads of the people who happened to apply it. Count the instances before fixing any of
them; the ratio tells you whether you are fixing a bug or writing down a rule.**


## Round 228 — the cardinal rule, on the number it matters most for

R227's method — count the instances of a convention before fixing any — applied to
design principle 2: *"No scorer returns a bare float. Every numeric prediction ships
with a calibrated interval, a method tag, a calibrated flag, and an OOD flag."*

Sweeping every typed model for `float` fields outside a `Prediction` gave eleven hits.
Nine are correct: thresholds the caller chose, allele frequencies read from a data
source, CFD/MIT scores from a deterministic matrix (not a model, so no calibrated band
exists to report), and `Prediction`'s own internals. One is the finding.

A candidate carries three predicted quantities:

    efficiency         Prediction[float]   0.45 [0.30, 0.60]  calibrated=False
    bystander_burden   Prediction[float]
    p_intended         float               0.61

`p_intended` is the probability the edit produces the allele that was asked for. Of the
three it is the one a reader acts on, and it reached every surface as a bare number.

**It was not missing — it was discarded.** `PrimeOutcomePredictor.predict` returns a
`p_intended` that *is* a `Prediction[float]`, and `prime.py` dropped it in one line by
passing `outcome=outcome.outcome`; base editing computes `p_intended_exact:
Prediction[float]` and never put it on the candidate. Both were recomputed downstream
as a plain sum over the allele distribution. The honest number was produced, thrown
away, and replaced with a dishonest one that happened to be equal.

SpCas9 is what keeps the fix honest. Its outcome predictor makes no such prediction, so
there `p_intended` genuinely is a derived sum with nothing behind it. The rule cannot be
"always show an interval" — it is "never show a number whose status is unclear" — so
that candidate carries `None` and the renders say *derived from the outcome
distribution; no calibrated interval* rather than inventing a band. The TSV gains four
columns that are blank in exactly that case, which is the difference between "no
interval was computed" and "the interval is zero-width".

**And the change surfaced a latent defect in `verify`.** Adding a field to
`DesignCandidate` made `aforge verify` reject the tool's own primary output. The cause
was not the new field: `verify` parsed every file as a `RankedMenu`, and a
`DesignReport` had been validating as one **by structural coincidence** — the two
candidate models overlapped enough for pydantic to coerce one into the other. It was
reading a different object than the file described and only ever touching
`.provenance`, where the difference could not show. It now names all three shapes it is
given (`DesignReport`, `RankedMenu`, bare `Provenance`), and the second is pinned so it
is accepted on purpose rather than inherited from an accident.

**Lesson: a value that is computed correctly and then discarded is more dangerous than
one that was never computed, because the discard is invisible at the point of use.
`p_intended` looked like a quantity with no uncertainty available; it was a quantity
whose uncertainty had been dropped one call earlier. When a number looks unavoidably
bare, search for it upstream before concluding it has no envelope to carry.**


Each change folder contains `proposal.md` (Why / What Changes / Impact), `tasks.md` (an
ordered checklist), and `specs/<capability>/spec.md` (the ADDED/MODIFIED requirement
deltas). When a change ships, fold its deltas into `specs/` and archive the folder.
