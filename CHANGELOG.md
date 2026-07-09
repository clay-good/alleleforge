# Changelog

All notable changes to AlleleForge are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The
project is in the `0.x` series until the three launch modalities pass
acceptance.

## [Unreleased]

### Fixed

- **Off-target nomination now scores bulge-collapsed hits the same way reporting does.** Round 7
  taught the CFD scorer to fall back off the published matrix for a DNA bulge (via a `bulged`
  flag), but the population/haplotype *nomination* gate (`_reference_best` / `_strengthens`) still
  called the scorer without it — so a DNA-bulge hit was nominated on its published-matrix score
  but reported on the approximation. `_strengthens` could then judge a real population off-target
  "not stronger" by a number the report never shows, silently dropping its `POPULATION` origin and
  ancestry attribution — the exact safety signal the pass exists to produce. Both helpers now pass
  the bulge status through, matching `engine._scores`. (Round 8 integration-seam pass.)

- **An explicit `regions` scope now bounds every off-target pass.** The reference and population
  passes iterate the requested regions, but the haplotype and patient passes consumed whole
  (often chromosome-wide) panels with no region argument, so a scoped search still reported
  out-of-region hits those panels created. Nominated hits are now filtered to the requested
  regions (a no-op when `regions` is unset). (Round 8 integration-seam pass.)

- **A `genome_index` from a different assembly than the reference now fails closed.**
  `search(…, genome_index=)` never checked the persistent index was built from the same assembly
  as the passed `reference`; a mismatch anchors PAMs over the index's sequence while reading
  bases and coordinates from the reference, yielding silently wrong hits. The engine now raises a
  clear error when both builds are known and disagree. (Round 8 integration-seam pass.)

- **Coding/protein HGVS deletions no longer crash against a reference.** `_from_hgvs` built the
  reference-base accessor *before* projecting a `c.`/`p.` expression to genomic form, so the
  closure's default-argument snapshot froze the pre-projection `chrom=None`. Any coding
  deletion/dup/delins whose projector omits the reference bases (the normal biocommons `c_to_g`
  output) then hit `assert _chrom is not None` and crashed — the genomic path worked only
  because its contig is known before the closure is built. The accessor is now defined after the
  contig is resolved. (Round 7 deep-correctness pass.)

- **Design provenance now records the override scorer, not the default it replaced.** `design()`
  exposes `cas9_efficiency_scorer` / `cas9_outcome_predictor` / `base_outcome_predictor`
  overrides (the opt-in trained Rule Set 3 / Lindel / BE-DICT models) and scores candidates with
  them, but `_collect_model_checkpoints` ignored the arguments and stamped the *default* scorers'
  cards into `provenance.models`. A run overridden with trained scorers therefore recorded the
  weight-free defaults, so anyone re-deriving from the stamped provenance reproduced different
  numbers — the "menu is reproducible from its inputs" guarantee was silently false. The override
  instances' own cards are now recorded. (Round 7 deep-correctness pass.)

- **DNA-bulge off-targets are now scored and labeled with the approximation, not published CFD.**
  The CFD fallback keyed only on spacer length ≠ 20, on the assumption that a bulge-collapsed
  alignment is never 20 nt. That holds for RNA bulges (which collapse the spacer to 19) but not
  DNA bulges: a DNA bulge collapses the *target* while leaving both aligned strings at 20 nt. Such
  a hit slipped past the length check and was scored *and* labeled with the published Doench
  matrix — but that matrix is defined only for an ungapped 20-mer, so the bulge shifts every base
  3′ of it off-register. The hit's bulge status is now threaded into the scorer's fallback
  decision. (Round 7 deep-correctness pass.)

- **The cloning-oligo enzyme screen now catches a recognition site across the overhang/insert
  junction.** The Type IIS site screen ran on the bare insert body (`g + spacer`, `ext_body`),
  but the oligo that actually ligates is the assembled top strand (`top_overhang + g + spacer`).
  A site straddling the junction was never screened, so a cloning-lethal insert shipped as clean —
  the exact Golden-Gate hazard the module advertises it guards against (e.g. lentiGuide's default
  BsmBI scheme with a spacer beginning `GTCTC` reconstitutes `CGTCTC` via the `CACC` overhang, and
  the assembled plasmid is re-cut in the same one-pot reaction). The screen now covers the
  assembled strand. (Round 7 deep-correctness pass — safety-critical.)

- **Base-editor probability intervals are now clamped to `[0, 1]`.** The `_prediction` helper
  clamped the lower bound to 0 but left the upper unclamped, so a near-certain edit probability
  produced an interval upper bound above 1.0 (e.g. value 0.95 → upper 1.10). It wraps two genuine
  probabilities (`p_intended_exact`, `p_target_edited`) alongside the count-valued bystander
  burden; the probabilities now clamp with `min(1.0, …)` like every sibling scorer, while the
  count stays legitimately unclamped. (Round 7 deep-correctness pass.)

- **The T2T ambiguous-region recommendation now fires for the `GRCh38` build spelling.**
  `flag_ambiguous_regions` gated the difficult-region table and the recommendation on a raw
  `source_build == "hg38"` compare, so a legitimate `source_build="GRCh38"` query sitting in a
  flagged centromere/segdup came back with no recommendation. It now matches naming-independently
  via `assembly_matches`. (Round 7 deep-correctness pass.)

- **`ClinVarDB.in_region` now reconciles contig naming, plus periphery hardening.** `in_region`
  compared contigs by raw string, so a `chr`-named record and an Ensembl-named query interval
  silently matched nothing on the mixed-naming path; it now compares via `canonical_contig`, as
  `GenomicInterval.overlaps` does. Also in this pass: `bench run`'s human-readable line no longer
  crashes formatting an undefined (`None`) ECE (it prints `n/a`), the batch TSV export neutralizes
  tabs/newlines in a field so they can't misalign columns, and three docstrings were corrected to
  match the code (the Cas12a non-canonical-PAM 0.05 floor, an isotonic "provably reduces ECE"
  overclaim, and the Pareto front's post-cap scope). (Round 7 deep-correctness pass.)

- **The PE3b nicking guide is now templated from the edited strand, so it actually nicks only
  the edited product.** PE3b's entire benefit is that its ngRNA seed base-pairs only after the
  edit is installed — nicking only the edited strand and avoiding the concurrent-nick DSB that
  causes indels. A prior round corrected which end of the seed is measured (the PE3b *detection*),
  but the emitted spacer was still reverse-complemented from the *unedited* allele: it
  Watson-Crick matched the original target (nicking it, before/independent of editing) and
  carried a seed mismatch against the edited product — the exact inverse of PE3b. A researcher
  ordering that spacer got a guide that nicks the wrong molecule. The seed-disrupting branch now
  templates the spacer from the edited allele. (Round 5 deep-correctness pass.)

- **Variant-effect selection now reports the SO-most-severe consequence, not a tier tie-break by
  list order.** `parse_vep_response` picked the reported consequence with `max(key=impact_of)`,
  but `impact_of` is only a coarse 4-bucket tier — when a transcript lists several terms in the
  same tier, the tie fell to VEP's term order, which is not severity-sorted. So
  `[frameshift, splice_donor]` reported FRAMESHIFT instead of SPLICE_DONOR, and
  `[synonymous, splice_region]` reported SYNONYMOUS instead of SPLICE_REGION. Since consequence
  drives editing-chemistry routing, the frameshift-over-splice-donor case sent the variant to
  the wrong modality. Selection now uses a total Sequence-Ontology severity rank (derived from
  the severity-ordered `Consequence` enum). (Round 5 deep-correctness pass.)

- **Config precedence: environment variables now correctly override the config file.** The
  documented order is defaults < `config.toml` < `ALLELEFORGE_*` env vars < constructor
  overrides, but `Settings.load` passed the TOML values as init kwargs, which outrank env
  sources in pydantic-settings — so a `config.toml` value silently beat a matching env var, the
  exact inverse of the contract. This reached `seed` (load-bearing for reproducibility, stamped
  into provenance) and `allow_network` (the auto-download safety gate). A file value now yields
  to both an explicit override and a matching `ALLELEFORGE_*` env var, restoring
  env > file > defaults. (Round 5 deep-correctness pass.)

- **`ClinVarDB.get` no longer overclaims RCV/SCV resolution.** Its docstring promised to resolve
  `VCV`/`RCV`/`SCV` accessions, but the ClinVar VCF carries only the integer VariationID, so
  records are indexed solely by their reconstructed `VCV` accession. An `RCV`/`SCV` accession —
  which `ClinVarAccession` accepts and the resolver forwards — could therefore never be found and
  produced a bare "no record" miss, as if the variant were simply absent. The docstring is
  narrowed to `VCV`, and an `RCV`/`SCV` accession now raises an actionable message explaining it
  cannot be mapped from the VCF alone. (Round 4 deep-correctness pass.)

- **`bar_chart` now escapes the value suffix like every other text node.** The visualization
  spec requires the chart primitive to escape all text nodes, and every label did — except the
  per-bar value suffix, which was interpolated raw. A `value_suffix` containing markup (e.g.
  `" <units>&"`) produced malformed, non-parsing SVG. It is now escaped. (The four committed
  figures only pass `"%"`/`""`, so no shipped figure was affected — but the public primitive's
  guarantee was unconditional.) (Round 4 deep-correctness pass.)

- **The CLI now honors every whitelisted config run-param instead of silently ignoring some.**
  `_load_config` accepts a set of run-param keys without a typo warning (signalling "this is a
  real knob"), and the CLI spec promises the config file is honored — but only `intent`,
  `populations`, `chemistry`, and `weights` were actually read from it. `max_per_chemistry`,
  `no_offtarget`/`run_offtarget`, `trained_efficiency`, `trained_outcome`,
  `trained_base_outcome`, and `cell_context` were whitelisted yet consumed by nothing, so a
  config that set them changed nothing and printed no warning (worse than a typo, which at least
  warns). Both `design` and `batch` now read every run-param they expose from the config as a
  fallback (a CLI flag still overrides), and `design` passes `cell_context` through to the
  designer. (Round 4 deep-correctness pass.)

- **Parallel cohort runs now honor the bounded-memory guarantee.** `design_many` promises the
  input is consumed lazily and peak memory does not grow with cohort size, but the
  `max_workers > 1` path used `ThreadPoolExecutor.map`, which is eager: it submits one task per
  input up front, draining the entire (possibly whole-VCF) stream immediately and holding an
  O(n) list of futures — the exact OOM the guarantee exists to prevent. The parallel path now
  keeps at most `max_workers` futures in flight, pulling the next input only as each completes,
  so peak memory is O(max_workers) regardless of cohort size (the sequential path was already
  correct). Results are recorded in completion order; the manifest and resume are set-keyed on
  `item_id`, so order is not load-bearing. (Round 3 deep-correctness pass.)

- **The default Cas9 efficiency ensemble no longer mislabels itself as trained.** The
  `EnsembleEfficiencyScorer` projection heads are a deterministic pseudo-random scaffold
  (`_member_weights`, SHA-256-derived), never fitted on any activity screen — so its point
  estimate is not a trained on-target-activity prediction. But `score()` demoted the method to
  `HEURISTIC` only when the *embedder* was the CI stub; with a real backbone it emitted
  `method=ENSEMBLE` (implying a trained deep ensemble), and the model card asserted "trained on
  pooled SpCas9 screens … First-party weights" that do not exist. The label now depends on the
  *heads* being fitted (they never are in the shipped scaffold), so the method is `HEURISTIC`
  regardless of the backbone until fitted head weights are wired through the model zoo; the
  model card and docstrings now describe it honestly as an unfitted scaffold and point users to
  `rule-set-3` (a real sequence-feature heuristic) or the opt-in trained Rule Set 3 model for a
  meaningful baseline. Honest labeling over hype — no trained claim without trained weights.
  (Round 3 deep-correctness pass.)

- **The Cas-OFFinder cross-check no longer false-alarms on every minus-strand site.** The
  optional cross-check compares reference-site loci against the external Cas-OFFinder binary
  as `(chrom, position, strand)`. Cas-OFFinder reports the leftmost forward-strand coordinate
  of the whole protospacer+PAM match; AlleleForge's site locus records only the protospacer
  start (PAM excluded). SpCas9's PAM is 3' of the protospacer, so on the plus strand the two
  anchors coincide, but on the minus strand the PAM lies at the low-coordinate end and the
  protospacer start is `pam_len` bases higher — so every minus-strand reference site was off
  by the PAM length, producing a spurious two-way disagreement (and able to mask a genuine one
  that happened to line up after the 3-bp shift). `reference_loci` now shifts a minus-strand
  locus down by `pam_len` so both engines key on the same anchor. (Round 3 deep-correctness
  pass.)

- **The working-interval clamp now fires across contig-naming styles.** The spec promises the
  ±`window` interval is clamped to `[0, contig_length]` whenever a reference is available, but
  `_working_interval` gated the clamp on raw `variant.chrom in reference.contigs` membership —
  the one contig access in the subsystem that skipped the naming reconciliation. On the common
  path (a `chr`-prefixed ClinVar/dbSNP variant against the Ensembl-named built-in hg38) the
  contig is present only under its aliased name, so the guard was `False` and the clamp was
  silently skipped, leaking a working interval whose end ran past the true contig end. The
  clamp now goes through the naming-reconciling `contig_length` accessor (catching `KeyError`
  for a genuinely absent contig), so it fires under either naming style. (Round 3
  deep-correctness pass.)

- **The design report now names the off-target scoring basis (scorer + matrix).** The
  reporting spec requires every rendered report to state which scorer and specificity matrix
  produced the off-target numbers (published Doench 2016 CFD versus the labeled seed-tolerance
  approximation), so a reader can tell the scoring basis without inspecting the code. The
  builder dropped `OffTargetReport.scorer`/`score_matrix` on the way into `CandidateReport`, so
  the HTML and PDF renders — and the JSON/TSV exports — never carried it: an approximation-scored
  table was presented identically to a published-CFD one. `CandidateReport` now carries
  `offtarget_scorer`/`offtarget_matrix`, both renderers print a "scoring basis" line beside the
  off-target table, and the JSON export is lossless again. (Round 3 deep-correctness pass.)

- **The out-of-distribution flag is now computed, not hardcoded — fail-honest by default.**
  Several default scorers stamped `in_distribution = True` unconditionally: the default
  ensemble efficiency scorer with no detector wired, the prime-outcome and base-outcome
  heuristics, and — worst — the real trained PRIDICT2 path, which was *less* OOD-honest than
  the heuristic baseline it replaces. Every scorer that emits a `Prediction` now derives the
  flag from an explicit check on its own inputs: the ensemble falls back to a documented
  context check (`context_in_distribution`, N-free + minimum length) when no embedding-space
  `OODDetector` is wired; prime-outcome and base-outcome apply the analogous reagent-sequence
  check; and PRIDICT2 computes `in_distribution` from the cell line, matching the baseline's
  cell-context check. A scorer with no check defaults to `False`, never `True`. Well-formed
  reference inputs stay in-distribution, so no goldens churn; only genuinely ill-formed
  (N-bearing or too-short) inputs now flag OOD. (Completes `compute-honest-uncertainty`, now
  archived.)

- **Nuclease correction is now enumerated against the allele the target genome actually
  carries.** For a CORRECT/REVERT/INSTALL intent the patient carries the *alternate* allele,
  but `enumerate_cas9` scanned the plain reference — so it emitted guides whose PAM exists only
  in the reference (destroyed by the alt allele, so uncuttable in the patient) and missed guides
  whose PAM the alt allele *creates*. The enumerator now substitutes the carried allele onto the
  fetched window before finding protospacers/PAMs (mirroring the base-editor and prime paths),
  and `design_cas9` threads the same overlay into on-target efficiency (`guide_context`) and
  outcome (`_cut_outcome`) scoring, so the whole nuclease slice reads the carried 20-mer.
  Length-preserving substitution only — indels keep the reference frame, as the prime/base
  enumerators bail on non-single-position edits. (Part 2 of `correct-design-verticals`.)
- **An HDR donor is no longer silently re-cuttable.** `hdr_donor` returned a bare template
  carrying the corrected allele; if the repair left the guide's PAM and seed intact, the same
  Cas9 re-cleaved the corrected product. It now takes the guide it must survive and returns an
  `HDRDonor` carrying the sequence, an optional recorded `BlockingMutation`, a `recut_blocked`
  flag, and a note: it introduces a PAM-blocking mutation in a homology arm when the repair
  would otherwise be re-cut, reports that the correcting edit already disrupts the guide when no
  mutation is needed, or states plainly that no arm PAM base can block (never shipping a
  re-cuttable donor as if it were safe). (Part 2 of `correct-design-verticals`, now complete
  and archived.)
- **Per-chemistry truncation no longer prunes a composite-optimal candidate.** Each vertical
  capped its candidates on a *local* proxy (prime by efficiency, Cas9 by
  efficiency-then-off-target, base by `p_intended_exact`) **before** the global 4-objective
  ranker ran, so a candidate that would top the composite — modestly lower efficiency but far
  safer or cleaner — was pruned before the composite was computed. The cap is now applied by
  `rank_candidates` (`max_per_chemistry`) **after** the composite sort; the verticals pool all
  candidates. Off-target search already ran on every candidate before the old slice, so this
  adds no compute. (Part 4 of `correct-design-verticals`.)
- **The base-editor efficiency axis is no longer a duplicate of cleanliness.** A base-editor
  candidate's `efficiency` was set to `p_intended_exact` (target edited **and** no bystander),
  the same clean-allele probability the ranker's cleanliness term reads — so ~0.65 of the
  composite weight sat on one identical number, double-charging bystanders and understating
  activity, while Cas9 and prime put raw activity on that axis. Efficiency now reads the new
  `WindowOutcome.p_target_edited` (P the target base is edited, marginal over bystanders); the
  clean fraction stays on the cleanliness axis, so the two objectives measure distinct
  quantities like-for-like across chemistries. Base-editor rankings shift; the reproduce golden
  was re-derived. (Part 3 of `correct-design-verticals`.)
- **PE3b is now measured from the correct end of the seed.** For a frame-minus prime-editing
  nicking guide, the Cas9 seed is the PAM-proximal protospacer end (the low-genomic `proto_lo`
  boundary, adjacent to the PAM). The enumerator tested `proto_hi - edit_local <= SEED_LENGTH`
  — the PAM-*distal* half — so genuine PE3b guides were demoted to plain PE3 and PAM-distal
  edits were falsely promoted to PE3b, mislabeling the flagship's byproduct protection. The
  test is now `edit_local - proto_lo < SEED_LENGTH`, so a guide is labeled `pe3b` only when the
  edit truly falls in its seed. (Part 1 of `correct-design-verticals`; the allele-aware nuclease
  correction, base-editor efficiency axis, and composite-preserving truncation parts remain.)
- **Contig naming is reconciled at the reference boundary.** The only fetchable genomes are
  Ensembl-named (`1`/`MT`), but the ClinVar/dbSNP parsers, the difficult-region table, and the
  RefSeq resolver all use UCSC `chr`-prefixed names — so a `chr17` ClinVar lookup against an
  Ensembl-named reference hit a `KeyError`, a misleading "wrong build?" mismatch, or silently
  never fired the T2T recommendation. `BuildDescriptor` now declares its `naming_style`,
  `ReferenceGenome.fetch`/`contig_length` alias `chr17`↔`17` (and the `chrM`/`MT`/`M`
  spellings) transparently — raising an explicit `ContigNamingError` (distinct from a
  base-level mismatch) only for a genuinely irreconcilable name — and `GenomicInterval.overlaps`
  compares contigs canonically so ambiguous-region flagging fires on either naming style.
  (Part 1 of `reconcile-assembly-coordinates`.)
- **A source database's assembly is reconciled, not silently overwritten.** `resolve` stamped
  the requested `build` (default hg38) onto every ClinVar/dbSNP record unconditionally, and the
  parsers never recorded the record's native assembly — so a GRCh37 release loaded with
  `build="hg38"` relabeled every variant to hg38 with no liftover, poisoning provenance and the
  downstream VEP assembly selection. Parsers now record each record's native assembly on
  `Variant.source_assembly` (ClinVar sniffs it from the VCF header or takes an explicit
  `assembly=`; dbSNP takes `assembly=`), left unknown rather than assumed when absent; `resolve`
  raises when the requested build disagrees with a recorded source assembly instead of
  relabeling. (Part 4 of `reconcile-assembly-coordinates`, which is now complete and archived.)
- **Two silent coordinate errors in the input layer now fail closed.** (Parts of
  `reconcile-assembly-coordinates`):
  - *A wrong-build insertion passed silently.* `_left_align` re-read an indel's anchor from
    the reference before validating, so a hg19 coordinate fed as hg38 whose asserted anchor
    disagreed was accepted — the exact wrong-build case the fail-closed guarantee exists to
    catch, defeated precisely for insertions. The caller's asserted ref is now validated
    **before** re-anchoring for every indel (insertion and deletion), raising a
    reference-mismatch error on disagreement.
  - *Liftover rebuilt a span from two independent endpoints.* `lift_interval` kept one
    endpoint's strand and never compared the lifted length to the source, so a chain indel
    silently resized the interval and an inversion boundary scrambled it. It now returns
    `None` when the endpoints map to different strands or the lifted length differs from the
    source beyond a declared `length_tolerance` (default 0).
- **Benchmark results are now independently re-derivable, and a degenerate model can no
  longer win the honesty axis.** Four gaps kept a published result from confirming an
  independent re-derivation (`harden-benchmark-reproducibility`):
  - *The signature sealed volatile fields.* It hashed the wall-clock timestamp, package
    version, and config paths, so a second lab, a new release, or a different platform
    produced a different signature for a scientifically identical result. A new
    `reproducibility_digest` covers only the scientific body (metrics rounded to a fixed
    precision, model-card facts, task, split identity, dataset hash) — identical across
    releases and platforms — alongside the existing tamper signature.
  - *The `config_snapshot` was a hand-built 2-key subset.* It now comes from
    `Settings.snapshot()` like the design path, recording `interval_level` (which drives the
    ranked ECE) and every governing setting.
  - *The result bound the split version label but not its membership.* It now binds
    `split.split_sha256`, so a re-cut `v1` fold is detectable.
  - *A `{}`-everywhere scorer scored ECE 0.0 ("perfect") and won the calibration tie-break.*
    ECE and interval-calibration now return `None` (undefined) when there are no scorable
    predictions, and the leaderboard sorts an undefined ECE last — an honestly-calibrated
    competitor is never out-ranked by a model that made no real prediction. (`BenchmarkResult`
    schema bumped to v2: adds `split_sha256`/`reproducibility_digest`, allows a null metric.)
- **Cloning oligos are now guarded as a real wet-lab deliverable.** Four gaps let a
  cloning-lethal or mis-specified oligo ship as a clean, round-trip-valid reagent
  (`guard-cloning-oligos`):
  - *No Type IIS site screening.* An insert carrying its own Golden-Gate enzyme's site
    (BsmBI `CGTCTC`, BbsI `GAAGAC`, BsaI `GGTCTC`) is cut internally during assembly — the
    classic failure. Every emitted insert (sgRNA spacer, pegRNA spacer, and the RTT+PBS+motif
    extension) is now screened on both strands and carries an `internal-<enzyme>-site` warning
    naming the component, strand, and position.
  - *The U6 5' G was double-added.* A spacer already starting with `G` got a second one,
    shipping a 21-nt guide with an unintended 5' base. The `G` is now added only when the
    spacer does not already begin with one, and whether it was added is recorded (`g_added`).
  - *The PDF leave-behind omitted the oligos.* The printable report now carries each
    candidate's oligo sequences and the annealing/phosphorylation prerequisite (T4 PNK); both
    renders state the prep note, and a reagent-free candidate says so instead of omitting the
    section.
  - *The pegRNA extension overhang was uncited and self-contradictory* (docstring `CGTCTC`…
    `GTGC/CGCG` vs constant `GTGC/AAAA`). The extension overhangs are now named, cited
    `VectorScheme` fields, with the docstring, constants, and reconstruct check in agreement.
- **An out-of-distribution prediction can no longer present a zero-width, maximally
  confident interval.** OOD widening was purely multiplicative (`half *= 2.0`), so when
  ensemble members agreed exactly (`std == 0`, half-width 0) `0 * 2 == 0` left the interval
  degenerate — the opposite of the contract's "OOD widens, never narrows." An additive
  `OOD_MIN_HALF_WIDTH = 0.05` floor is now added on top of the factor, guaranteeing an OOD
  interval is strictly wider than any in-distribution interval the same head could emit and
  that a zero-width interval never survives OOD flagging. (First task of
  `compute-honest-uncertainty`; the remaining OOD-computation, trained-vs-heuristic, and
  nominal-interval-level tasks are still open.)

### Added

- **A fixed heuristic interval no longer masquerades as a measured 80% coverage.** Every
  scorer stamped a constant ±0.15 band with `interval_level = 0.80`, so a consumer
  thresholding on `interval_level` could read an unmeasured placeholder as a calibrated
  coverage. Each fixed-band heuristic prediction now carries an auditable
  `NOMINAL_INTERVAL_NOTE` ("coverage not measured"), and the count-valued `bystander_burden`
  carries a `COUNT_INTERVAL_NOTE` (its spread is not a coverage band at all). The reproduce
  golden was re-derived (the menu now carries the honest notes). (Task 4 of
  `compute-honest-uncertainty`; only task 2 — computing `in_distribution` — remains.)
- **A trained point estimate is now distinguishable from a heuristic one by the honesty
  flags alone.** The real Rule Set 3, PRIDICT2, and BE-DICT scorers ship a trained point
  with an *uncalibrated* heuristic interval — byte-identical in `method`/`calibrated`/
  `in_distribution` to a purely heuristic prediction, so a consumer could not tell a
  trained activity from a rule-of-thumb without reading provenance. `Prediction` gains
  `point_from_trained_model` (default `False`, threaded through `calibrated_by` and AND-ed
  in `combine`), set `True` on the trained Rule Set 3 / PRIDICT2 / BE-DICT paths and left
  `False` on the transparent baselines. Published JSON schemas regenerated (this also syncs
  the off-target `score_matrix` / `subthreshold_score_sum` fields). (Task 3 of
  `compute-honest-uncertainty`; tasks 2 and 4 remain.)
- **Off-target strengthening is now score-based, the aggregate covers the sub-threshold
  tail, and a frequency-aware burden joins the worst-case.** Four gaps that let the
  population/haplotype differentiator under-state risk or report an optimistic summary are
  closed (`guard-offtarget-strengthening`):
  - *Strengthening was edit-count-only.* The population and haplotype passes nominated an
    alt-allele hit only when its edit count fell, so a minor allele upgrading a weak PAM
    (`NAG`→`NGG`, CFD 0.07→0.28) at an unchanged edit count was silently dropped — a pure
    false negative. Nomination now keeps an alt hit that beats the best reference hit at
    the same placement by **either** a higher specificity score (catches the PAM upgrade)
    **or** fewer edits (catches a mismatch/bulge removal the bulge-blind CFD misses).
  - *The genome-wide `specificity_score` summed only reporting-threshold survivors*, so a
    guide with a large near-threshold tail could report the same specificity as a clean
    one. The engine now carries the best per-placement sub-threshold score into the
    aggregate (`OffTargetReport.subthreshold_score_sum`), matching the CRISPOR/Hsu sum
    over all candidate sites.
  - *CFD scored any length under a "published" label.* `cfd_score` now raises when the
    published/fixed matrix (positions 0–19) is applied to a non-20-nt alignment; the
    default `CfdScorer` falls back to the length-relative approximation for a
    bulge-collapsed/off-length hit and records the approximation as that site's matrix
    (`OffTargetSite.score_matrix`), so an off-length score is never mislabeled published
    CFD while recall is preserved.
  - *The aggregates were frequency-blind.* `OffTargetReport.expected_burden()` weights
    each site by the probability a genome carries it (reference/patient 1.0, population by
    carrying frequency), so a MAF-floor off-target and a universal one are now
    distinguishable in the summary numbers.
- **The published Doench 2016 CFD matrix is now the default off-target scorer.**
  The default `CfdScorer` used a transparent seed-tolerance *approximation*, so
  out-of-the-box CFD numbers were not the values a reviewer comparing against CRISPOR
  expects. The authentic 240-weight Doench 2016 mismatch matrix (plus its 16 PAM
  weights) is now vendored at `offtarget/cfd_matrix.json` and used by default (labeled
  `doench-2016-cfd`). It was sourced from CRISPOR and **cross-verified byte-for-byte
  against CRISPRitz** (an independent tool; max abs difference 0.0), and the conversion
  into the scorer was proven exact against the reference CFD calculator over 20,000
  random pairs — nothing fabricated or approximated. The transparent approximation stays
  available via `CfdScorer(approximate=True)`. **Off-target scores change for real runs
  with mismatched sites**: they now return published CFD instead of the approximation
  (perfect-match sites, which depend only on the unchanged PAM weights, are unaffected —
  hence the reproduce golden's only drift was the honest matrix label). Completes
  `ship-published-cfd-matrix`.
- **The recorded seed is now load-bearing.** `provenance.seed` drove no randomness: the
  only genuine stochastic step (the conformal-recalibration demo) drew from its own
  hardcoded `SEED = 20240501` duplicate, so the seed was decorative. `Settings.rng()` is
  now the single run-scoped RNG (`random.Random(seed)`) that stochastic steps draw from,
  the conformal demo takes that RNG, and its callers (`viz.figures`, `calibration_study`)
  thread `get_settings().rng()` — so changing the seed changes the output and fixing it
  reproduces byte-for-byte. Because the default resolved seed equals the retired constant,
  the committed figures and reproduce golden are unchanged. The design path still has no
  stochastic step; the seam is in place for the first one that does. (Completes
  `complete-provenance`, task 2.)
- **pegRNA candidates flag Pol-III transcription caveats.** A prime candidate whose
  spacer does not start with G (needs a prepended U6-start G) or whose GC content
  falls outside the 0.30–0.80 band now carries an inspectable `no-5prime-g` /
  `gc-out-of-band:<frac>` flag, surfacing the caveat as an annotation rather than
  silent absence. (Part of the in-progress `align-prime-coverage`, task 2.)
- **The CLI warns on unknown config-file keys.** `aforge --config` silently ignored
  any key it didn't consume, so a typo like `maf_treshold` vanished without effect.
  `_load_config` now warns (to stderr) on any config key that is neither a `Settings`
  field nor a recognized run-param knob, so a mistake is surfaced. (Part of the
  in-progress `complete-provenance`, task 4.3.)
- **The FM-index can re-verify itself against its build-time content hash.**
  `FMIndex.verify()` reconstructs the indexed text from the persisted BWT via the
  LF-mapping and re-hashes it, raising `FMIndexIntegrityError` if it no longer matches
  the `content_hash` recorded at build — an on-demand `O(n)` integrity check so a
  corrupted or tampered cached index fails closed instead of serving wrong locations.
  With this, the hash-on-read machinery, required failure-modes, and opt-in cache
  content-verify, only the maintainer release step of pinning real checkpoint hashes
  (blocked on the external artifacts) remains in `verify-artifact-integrity`.

### Fixed

- **The README states prime's supported edit classes honestly.** The routing table
  claimed prime editing handles "arbitrary substitutions / short indels," but the
  enumeration templates a single-base substitution today (routing already declines
  indels/MNVs with a stated reason). The routing table and the four-axis flagship
  section now say prime is advertised for a precise SNV only, with short
  insertions/deletions/MNVs biologically in scope but pending the variable-length RTT
  path — matching `routing.py`. (Completes `align-prime-coverage`, task 4.)
- **The CLI now honors the config file and the declared reference build.** `aforge`
  constructed `Settings(seed=…)` directly, so a user's `config.toml`
  (`maf_threshold`, `interval_level`, `cache_dir`) was ignored — the documented
  precedence was violated for the primary interface — and every reference was
  hard-labeled `hg38` regardless of `--reference`. The CLI now routes settings
  through `Settings.load(config_file=config, seed=state.seed)` so the config file's
  keys apply (and appear in the recorded settings snapshot), and labels the loaded
  genome (and its provenance) with the user's `--reference` build. (Part of the
  in-progress `complete-provenance`, task 4; the warn-on-unknown-key mode remains.)

### Added

- **Optional per-job wall-clock timeout completes the web-API hardening.**
  `JobManager` now accepts `max_job_seconds`: a job that runs past it is marked
  `ERROR` (a soft timeout — the worker thread cannot be cancelled, so it finishes in
  the background but its result is discarded and the caller sees the timeout). Off by
  default. With this and the durable-job-backend seam documented behind the
  `JobManager` interface, `harden-web-api` is complete — its size cap, in-flight cap,
  bounded job store, optional off-loopback auth, and timeout are folded into the
  `web-api` spec and the change is archived.
- **The content-addressed cache can verify payload integrity on read.**
  `ContentAddressedCache` served whatever bytes were on disk, so a corrupted or
  externally-modified entry was returned as-is. It now takes an opt-in
  `verify=True`: each entry gets a checksum sidecar on write, and reads re-hash the
  payload and raise `CacheIntegrityError` on a mismatch. Off by default (no sidecars,
  no overhead), so existing caches are unchanged. (Part of the in-progress
  `verify-artifact-integrity`, task 4.)

### Fixed

- **A code defect in a design vertical is no longer masked as "no design".** The
  designer and cohort caught every exception with a blanket `except Exception`, so a
  genuine bug (an `AttributeError`, a `TypeError`) was swallowed into a benign
  "skipped" note, indistinguishable from a chemistry that legitimately produced
  nothing. `_run_chemistry` and the cohort's `_design_one` now catch only *expected*
  design-failure types (missing model, bad input, absent optional dependency) as
  graceful degradation, and tag any *unexpected* exception as a defect ("ERROR —
  unexpected …" / "unexpected … (likely a defect)") so it is surfaced and
  actionable, while still not crashing the run. (Part of the in-progress
  `align-prime-coverage`, task 3.)

### Added

- **`aforge verify <result>` turns provenance into a checkable contract.** A new CLI
  command loads a result's ranked-menu JSON and confirms its provenance block is
  complete and self-consistent — it names every model and dataset used and carries a
  seed, version, and config snapshot — then, given `--cache-dir`, re-hashes each
  pinned model checkpoint found there against the hash recorded in provenance. It
  exits non-zero on incomplete provenance or a checkpoint hash mismatch. (Part of the
  in-progress `complete-provenance`, task 5; the reproduce-style determinism re-run
  needs the original reference and is a follow-up.)
- **Off-target reports now say which scorer and weight matrix produced the scores.**
  CFD is the number bench scientists compare against CRISPOR, but nothing in the
  output said whether a score came from the published Doench matrix or the shipped
  transparent approximation. `CfdScorer`/`Cas12aCfdScorer` now expose a `matrix`
  identity, `OffTargetReport` carries `scorer`/`score_matrix`, the engine populates
  them, and `aforge offtarget` surfaces them — so the default is honestly labeled
  `doench-2016-seed-tolerance-approximation` and the Cas12a analog is flagged
  `unvalidated`. (Part of the in-progress `ship-published-cfd-matrix`, task 3;
  defaulting to the authentic Doench matrix stays blocked on an authoritatively
  sourced, cross-verified copy. Off-target and reproduce goldens were regenerated.)
- **Provenance snapshots the full resolved settings.** `config_snapshot` was a
  hand-built subset of run parameters that could drift from the `Settings` that
  actually governed a run. It now also embeds the full resolved settings via the
  new `Settings.snapshot()` (seed, reference, interval level, MAF threshold,
  network policy — minus the volatile per-machine `cache_dir`), so a result is
  re-derivable from what governed it. (Part of the in-progress `complete-provenance`,
  task 3; the load-bearing seed/RNG, CLI/web config-file honoring, and `aforge
  verify` remain open.)

### Fixed

- **Prime enumeration no longer emits an untranscribable pegRNA.** A protospacer
  containing a `TTTT` run is a Pol III terminator: transcription from a U6 promoter
  stops early, so the pegRNA is a dead reagent. `enumerate_prime` now filters any
  candidate whose protospacer carries a `TTTT` terminator. (Part of the in-progress
  `align-prime-coverage`, task 2; the 5'-G/GC-band annotation and per-candidate
  rejection-reason surfacing remain open.)
- **The web API bounds request size and the job store.** `POST /api/batch` accepted
  a `variants` list with `min_length=1` but no maximum, so a single caller could
  queue an arbitrarily large cohort; the schema now caps it at `MAX_BATCH_VARIANTS`
  (1000) and rejects an over-large request with 422 before any work is scheduled.
  Separately, `JobManager._jobs` grew without bound (a long-lived server leaked
  memory); it is now size-bounded, evicting the oldest *terminal* (done/error)
  records past a configurable cap (default 1000) while never dropping an in-flight
  job. And `JobManager` now enforces a max-in-flight cap (default 16): `submit`
  raises `JobCapacityError` when saturated, mapped to 429 by `POST /api/jobs/design`,
  so a submission flood cannot exhaust the worker threadpool. And an optional API
  token now gates every `/api/*` request (except `/api/health`) via an `X-API-Token`
  header when `create_app(api_token=...)` is set; `serve()` refuses to bind to a
  non-loopback host without a token (from the argument or `ALLELEFORGE_API_TOKEN`),
  so the service cannot be exposed unauthenticated. (Part of the in-progress
  `harden-web-api`; a per-request timeout and the durable-job-backend seam remain
  open. The default localhost experience is unchanged.)
- **Benchmark split leakage and leaderboard injection are now blocked.**
  `Split.verify` hashed whatever membership was in a split file but never checked
  that `train`/`val`/`test` were disjoint or that every id existed in the dataset —
  so a minted split with an id in both train and test passed every integrity check
  (the one thing a benchmark most needs to forbid), and a dangling id surfaced only
  later as a `KeyError`. `verify` now rejects overlapping folds and absent ids up
  front. Separately, the leaderboard interpolated `model_name`/`submitter`/`task`
  raw into HTML/Markdown; those cells are now HTML- and Markdown-escaped, so a
  submitter handle with markup or a `|` can no longer inject into the static board.
  A submission may also no longer carry two results for the same task (one model
  ranking twice). Finally, `BenchmarkResult` and the TSV/Parquet candidate exports
  now carry a `schema_version` (in the result's signed body and as the leading
  export column), so a downstream consumer can detect a field/column addition or
  reordering instead of silently misreading a changed record. This completes
  `guard-benchmark-integrity` (only the optional metric hardening is deferred).
- **Prime-editing routing no longer over-promises edits it cannot produce.**
  Routing advertised prime for any non-knockout edit up to 44 bp, but
  `enumerate_prime` templates only a single-base substitution (SNV) — so an
  insertion, deletion, or MNV routed to prime, enumerated nothing, and surfaced
  only as a generic "eligible but no actionable candidate" note, silently
  under-delivering the flagship capability. `_prime_eligible` now consults an SNV
  feasibility gate matching enumeration, and the prime routing rule's rationale
  states the SNV-only limitation, so an ineligible decision carries the specific
  reason. (First slice of the in-progress `align-prime-coverage`; Pol-III
  rejection reasons and separating a defect from an empty result remain open.)

### Added

- **Design provenance records the datasets it consumed.** `Provenance` defaulted
  `datasets`/`tools` to empty and the designer populated only `models`, so a menu's
  provenance under-reported its own inputs even though the dataset-capture helpers
  existed — they were never wired in. The design path now collects the reference
  build's `DatasetVersion` (and gnomAD/ClinVar once they carry a version) into
  `Provenance.datasets` via `_collect_datasets`, mirroring `_collect_model_checkpoints`,
  so a result no longer silently omits a dataset it read. (First slice of the
  in-progress `complete-provenance`; the load-bearing seed, full config snapshot,
  CLI/web config-file honoring, and `aforge verify` remain open.)
- **Cached artifacts are re-verified on every load (hash-on-read).** The
  consent + license + checksum gate was bypassed exactly where tampering matters —
  on cache hits: `ModelRegistry.checkpoint`, `DatasetRegistry.resolve`, and
  `ReferenceGenome.from_build` only hashed bytes on download and returned an
  existing cached file unverified. Each now re-verifies a cached checkpoint,
  dataset, or reference FASTA against its pinned hash on every load and fails
  closed (`ChecksumError`) on a mismatch, so a tampered or truncated cache entry
  can no longer pass silently. Artifacts with no pinned hash are served as before.
  Relatedly, `known_failure_modes` is now a **required**, non-empty `ModelCard`
  field (validated at construction), so every model's audit surface is complete and
  rides into provenance rather than being an optional afterthought. (Part of the
  in-progress `verify-artifact-integrity`; pinning real hashes for the remaining
  cards is a maintainer release step, and the cache content-verify remains open.)
- **Wet-lab oligo path is now alphabet-, scaffold-, and boundary-safe**
  (`validate-oligo-alphabet`). The oligo module emits the exact duplexes a bench
  scientist orders, so a wrong sequence wastes reagents. `revcomp` used
  `str.maketrans` and silently passed any non-`ACGTN` character through
  untranslated (an RNA `U`, an IUPAC code, stray whitespace) — a mis-complemented
  antisense oligo that could still round-trip because both strands shared the bad
  complement. Now: (1) `revcomp` and every oligo-construction input are validated
  against the `ACGTN` DNA alphabet and raise a clear error naming the offending
  character; (2) the pegRNA scaffold is verified against the canonical SpCas9
  scaffold constant, so a wrong or empty scaffold is caught rather than shipped;
  (3) the pegRNA extension carries an RTT/PBS boundary check that compares the
  whole extension body to `RTT + PBS` (independent of the stored slice length), so
  a mis-split extension is detected, plus a `component_lengths` annotation. Valid
  DNA inputs are unchanged.
- **Bulletproofed population/haplotype off-target nomination** — the tool's
  differentiated capability — on four correctness fronts (`bulletproof-offtarget-nomination`):
  (1) **Best alignment per anchor.** Each PAM anchor now reports the *edit-minimal*
  alignment across ungapped / single-DNA-bulge / single-RNA-bulge candidates, with a
  deterministic tie-break, instead of the first in-budget one found — so a bulged
  near-perfect match (higher CFD, more dangerous) is never under-scored behind a
  many-mismatch ungapped alignment. (2) **Indel-aware coordinates.** When a population,
  haplotype, or patient variant changes the window length, hits are scanned in
  alt-local coordinates and *lifted back* to true genomic coordinates through the
  indel, so insertions and deletions place downstream sites correctly (a capability
  CRISPOR and Cas-OFFinder lack); the equal-length (SNV) path is byte-for-byte
  unchanged. (3) **Partial haplotype application.** One ref-clashing variant no longer
  discards a whole haplotype's nominations — the non-clashing subset is applied and the
  skipped variants are recorded on the site provenance (`SiteProvenance.skipped_variants`).
  (4) **Unified dirty-input handling.** Bases outside `ACGTN` are folded to `N` up front
  so the linear scan and the FM-index/native path agree — both skip an unexpected base
  rather than one silently mis-scoring while the other raises.
- **Honest-uncertainty contract, enforced end to end.** The `calibrated` and
  out-of-distribution flags are no longer honor-system, and ranking now acts on
  uncertainty instead of ignoring it (`harden-uncertainty-honesty`). Four hardenings:
  (1) `calibrated = True` is **unforgeable** — only a fitted calibrator can set it,
  through the new `Prediction.calibrated_by` classmethod; a scorer that constructs a
  `Prediction` asserting calibration directly is silently coerced to
  `calibrated = False`. (2) An **out-of-distribution prediction can never be
  calibrated** and its interval is **widened, never narrowed** (`OOD_WIDEN_FACTOR`), so
  an OOD input can't present a narrow, confident interval even when ensemble members
  agree. (3) The **weight-free stub embedder path is labeled honestly** — the default
  ensemble on the stub reports `method = heuristic`, `calibrated = False`, so
  content-hashed noise is never mistaken for a trained model. (4) **Interval repair is
  recorded, not silent** — when a point estimate falls outside its own interval (an
  inconsistent-head signal), the interval is widened to contain it *and* an auditable
  note is attached (new `Prediction.notes` field). Ranking became
  **uncertainty-aware**: the efficiency objective uses the point estimate
  in-distribution but the **lower interval bound out-of-distribution**, so a
  confident-looking OOD candidate can no longer outrank an otherwise-equal
  in-distribution one, and each candidate's interval and OOD status now appear in its
  score breakdown and the menu rationale. The reproducibility golden was regenerated to
  reflect the new, honest ranking output.

- **Aggregate genome-wide off-target specificity score.** `OffTargetReport`
  gained `specificity_score()` — the CFD-scale analog of the Hsu 2013 / MIT guide
  specificity (`100/(100+Σ)`), i.e. `1/(1 + Σ site scores)` ∈ (0, 1], **1.0** for a
  guide with no nominated off-targets and decreasing as the total burden grows.
  The report already aggregated site count, worst-case, and ancestry strata, but
  lacked the field-standard single-number specificity that distinguishes two guides
  with the same worst-case off-target but a different *number* of off-targets. It is
  now a `CandidateReport.offtarget_specificity` export field (schemas regenerated)
  and is rendered in the HTML and PDF reports. It is surfaced across every output
  surface that summarizes off-target: the standalone `aforge offtarget` command
  (JSON `specificity` + the human one-liner) and the cohort batch summary
  (`best_specificity`, the top candidate's specificity — in the JSONL manifest, the
  per-item TSV, and `design.design_many`'s summaries), so cohort triage can rank by
  total off-target burden, not just the single worst site. The web API closes the
  last gap: `POST /api/offtarget` now returns an `OffTargetResponse` envelope —
  the full report **plus** the aggregate summary (`n_sites`, `worst_score`,
  `specificity`, `ancestry_stratification`) — because those aggregates are
  *methods* on `OffTargetReport` and so were absent from its serialized fields,
  leaving an API client to recompute what the CLI already prints.

- **Phase 0 — Repository bootstrap.** Hatchling build, `aforge` console-script
  entry point, dependency groups (`core`/`genome`/`variant`/`ml`/`web`/`docs`/`dev`),
  pinned tool configuration (ruff line-length 100; mypy `strict`; pytest with an
  85% coverage gate). Rust PyO3 crate `aforge_native` (built with maturin)
  exposing `version()` to prove the toolchain end to end. Single-source version
  in `_version.py`; typed `Settings` (pydantic-settings) carrying every
  cross-cutting default (seed `20240501`, reference `hg38`, 80% interval level,
  MAF threshold `0.001`, XDG cache dir). MIT license for all code, schemas,
  benchmark, and first-party weights; `CITATION.cff`, Contributor
  Covenant 2.1 code of conduct, contributing guide, multi-stage `Dockerfile`,
  `docker-compose.yml` stub, conda environment file, and a GitHub Actions CI
  matrix (lint, type-check, test, strict docs build).
- **Phase 1 — Core domain types & schemas.** The typed vocabulary under
  `alleleforge.types`: strand-aware `DNASequence` with ambiguity-aware
  reverse-complement, `GenomicInterval` (0-based half-open), `Variant` with
  idempotent normalization, guide/pegRNA/nicking-guide models with structural
  validation, edit-outcome and strategy models, off-target site/report models
  with ancestry stratification, the generic `Prediction[T]` uncertainty
  contract (80% interval, method tag, in-distribution and calibration flags),
  design-candidate and ranked-menu models, and the provenance block. JSON
  Schemas for every public model are emitted to `docs/schemas/`.
- **Phase 2 — Genome access & indexing.** `alleleforge.genome`: a strand-aware,
  bounds-checked `ReferenceGenome` over pyfaidx that N-pads contig ends and
  flags the over-run rather than crashing, with a registry of built-in builds
  (hg38, T2T-CHM13 v2, mm39) and consent-gated, checksum-verified download; a
  content-addressed, memory-mapped FM-index (with a correct pure-Python fallback
  when the Rust kernels are not built) for PAM-anchored candidate search; and
  cross-build liftover plus `flag_ambiguous_regions()`, which recommends
  T2T-CHM13 for segmentally-duplicated / centromeric / hg38-difficult loci and
  wires the recommendation into the Phase 1 result types.
- **Phase 3 — Data registry & population datasets.** `alleleforge.data`: a
  license-aware, versioned `DatasetRegistry` that never vendors a
  non-redistributable source and refuses to fetch an artifact it cannot
  checksum-verify; ClinVar parsing into normalized variants with
  significance/review-status and `get`/`by_rsid`/`by_gene`/`in_region` lookups;
  gnomAD per-population allele-frequency queries; 1000 Genomes and HGDP phased
  common-haplotype enumeration; dbSNP rsID ↔ locus resolution; and GENCODE gene
  models plus ENCODE bedGraph signal lookups. Every parser reads plain-text
  fixtures so CI needs no `pysam`/`cyvcf2`. Dataset versions, licenses, and
  citations are documented in `docs/data.md`.
- **Phase 4 — Variant resolver.** `alleleforge.variant`: `resolve(...)` turns a
  ClinVar accession, dbSNP rsID, HGVS (`g.`/`c.`/`p.`), VCF record, raw
  coordinates, or a raw target sequence into one canonical, **left-aligned**,
  reference-validated `Variant` (a ref/reference disagreement is a hard error)
  with its working interval and molecular consequence. Includes a
  dependency-free genomic-HGVS parser, an `HgvsAdapter` that projects coding /
  protein expressions through an injected backend, and a VEP-style
  `EffectPredictor` protocol with a deterministic static implementation.
- **Phase 5 — Off-target engine (population & haplotype aware).**
  `alleleforge.offtarget`: a five-stage [`search`][] — reference candidate
  search (PAM-anchored, ≤4 mismatches, ≤1 DNA + ≤1 RNA bulge, both strands;
  Rust FM-index with a correct linear-scan fallback), gnomAD **population
  augmentation** that finds *de novo* PAMs and strengthened seed-mismatch sites,
  **haplotype-aware** walking of common 1000G/HGDP haplotypes, an optional
  patient-VCF pass, then CFD+MIT scoring, thresholding (CFD ≥ 0.20 or MIT ≥ 0.10),
  de-duplication, and **ancestry stratification by default**. Published MIT/Hsu
  and CFD scorers (the exact Doench PAM table; an injectable mismatch table) plus
  a Cas12a CFD analog, behind a swappable `OffTargetScorer` protocol; an optional
  Cas-OFFinder cross-check. The reference-bias / `rs114518452` finding is
  reproduced as an integration test: a reference-only scan is blind to the
  ancestry-enriched off-target the population-aware scan nominates. Cites
  Hsu et al. *Nat Biotechnol* 2013, Doench et al. *Nat Biotechnol* 2016, and
  Cancellieri & Pinello *Nat Genet* 2023.

[`search`]: https://github.com/clay-good/alleleforge/blob/main/src/alleleforge/offtarget/engine.py
- **Phase 6 — Scoring foundations (model zoo, embeddings, uncertainty).** The
  reusable ML substrate before any chemistry-specific predictor.
  `alleleforge.model_zoo`: a `ModelRegistry` over required, validated YAML
  **model cards** that refuses a missing card, a license that forbids the use
  (non-commercial cards block commercial use; unknown/proprietary refused), or an
  unverifiable checkpoint, surfacing each as a Phase 1 `ModelCheckpoint`; bundled
  cards for Nucleotide Transformer v2 (500M) and Rule Set 3.
  `alleleforge.scoring`: a swappable `SequenceEmbedder` protocol (NT v2 default;
  Caduceus and Evo 2 adapters; a deterministic weight-free `StubEmbedder` and a
  hash-keyed embedding cache for CI); calibrated-uncertainty machinery — a
  deep ensemble (N=5, the default) whose interval widens on disagreement, an
  evidential (Normal-Inverse-Gamma) single-model fallback, quantile intervals,
  isotonic post-hoc calibration with `expected_calibration_error`, and an
  embedding-space `OODDetector`, all packaged into the Phase 1 `Prediction`; and
  the `Scorer` protocol with a runtime `ensure_prediction` guard enforcing the
  no-bare-float contract. Pure stdlib — no numpy/torch in the core path; real
  backbones are gated behind the `real_weights` marker. PyYAML joins the core
  dependencies for card parsing. Cites Hsu/Doench, Amini et al. *NeurIPS* 2020
  (deep evidential regression), and Dalla-Torre et al. *Nat Methods* 2024 (NT).
- **Phase 7 — Chemistry: SpCas9 nuclease.** The first full vertical slice
  (enumerate -> efficiency -> outcome -> off-target -> candidate).
  `alleleforge.enumerate.cas9`: strand-aware enumeration of every PAM-anchored
  guide whose blunt cut (3 bp 5' of the PAM) falls in the actionable window, with
  `NG`/SpRY fallback only when no `NGG` guide is actionable, an HDR donor for
  precise intents, and a guide-context helper. `alleleforge.scoring.cas9_efficiency`:
  a transparent Rule-Set-3-style baseline (with the DeWeirdt-Doench tracrRNA-aware
  term) and a backbone-fine-tuned deep-ensemble scorer with embedding-space OOD
  flagging — both calibrated `Prediction`s, never bare floats.
  `alleleforge.scoring.cas9_outcome`: a microhomology/MMEJ + templated-1-bp-insertion
  indel-spectrum baseline (the inDelphi mechanism) plus license-gated inDelphi /
  Lindel / X-CRISP adapters and an ensemble mode reporting inter-model top-allele
  agreement. `alleleforge.design.cas9`: `design_cas9` wires the slice into ranked
  `DesignCandidate`s, each with a calibrated efficiency interval, predicted outcome
  distribution, and ancestry-stratified off-target report. Bundled model cards for
  the efficiency ensemble and inDelphi. Cites DeWeirdt & Doench *Nat Commun* 2022
  (Rule Set 3) and Shen et al. *Nature* 2018 (inDelphi).
- **Phase 8 — Chemistry: base editing (ABE / CBE).** A declarative `BaseEditor`
  registry (deaminase, chemistry, window, PAM, motif preference) seeded with
  ABE8e, CBE4max, and evoCDA1 — adding an editor is a data change.
  `alleleforge.enumerate.base_editor.enumerate_base_edits` finds, for the
  transition a variant requires (only transition SNVs are base-editable;
  strand-aware), every sgRNA placing the target base in the activity window,
  annotated with target / bystander positions and the in-window composition.
  `alleleforge.scoring.base_outcome`: a transparent window-outcome baseline (the
  BE-DICT mechanism — per-position editing probability × motif preference,
  enumerating the 2^k window alleles) yielding the allele distribution plus
  calibrated `p_intended_exact` and `bystander_burden`, license-gated BE-DICT /
  BE-Hive adapters, and a cross-editor recommendation. `alleleforge.design.base_editor.design_base_editor`
  wires enumerate -> outcome -> off-target into `DesignCandidate`s ranked by exact-
  intended probability then bystander burden, flagging the cleanest as
  recommended and surfacing the tradeoff on every candidate. Phase 1
  `BaseEditWindow` gains optional placement/PAM and a `window_bases` property;
  `DesignCandidate` gains a `base_edit_window` reagent slot. Bundled BE-DICT
  model card. Cites Richter et al. 2020 (ABE8e), Koblan et al. 2018 (BE4max),
  Thuronyi et al. 2019 (evoCDA1), and Marquart et al. 2021 (BE-DICT).
- **Phase 9 — Chemistry: prime editing (the flagship).** The chemistry where no
  open-source tool combines all four axes — AlleleForge unifies them.
  `alleleforge.enumerate.prime.enumerate_prime`: full pegRNA enumeration (both
  strands via a reverse-complement frame) — for each PAM whose nick sits 5' of the
  edit, it enumerates **PBS 8-17 nt** and **RTT 7-34 nt** (covering the edit + >= 5
  nt 3' homology), attaches a **tevopreQ1** epegRNA motif by default, and selects a
  **PE3/PE3b** nicking guide (preferring a seed-disrupting PE3b ngRNA). Emits
  structurally-validated `PegRNA` + `NickingGuide` pairs.
  `alleleforge.scoring.prime_efficiency`: a transparent PRIDICT2.0-style baseline
  over the pegRNA geometry with an **ePRIDICT** chromatin adjustment (ENCODE
  tracks) and **prominent OOD honesty** — any context outside PRIDICT's HEK293T /
  K562 training distribution flags `in_distribution=False`; plus license-gated
  DeepPrime / GenET cross-check adapters. `alleleforge.scoring.prime_outcome`: an
  intended-vs-byproduct distribution (scaffold incorporation, partial RTT, indels)
  with calibrated intended probability. `alleleforge.design.prime.design_prime`
  wires enumerate -> efficiency -> outcome -> off-target into ranked
  `DesignCandidate`s, running the off-target engine on **both** nicks and merging
  them into one ancestry-stratified report. Phase 1 `PegRNA` gains optional
  placement / nick-site fields. Bundled PRIDICT2.0 card; canonical example
  `examples/01_clinvar_to_design.ipynb`. Cites Mathis et al. 2023/2024
  (PRIDICT / PRIDICT2.0 / ePRIDICT).
- **Phase 10 — Designer: routing, multi-chemistry menu, ranking.** The
  orchestrator that turns one variant into a ranked, explained menu across every
  eligible chemistry. `alleleforge.design.routing`: `eligible_chemistries` and
  `route` over a small table of transparent, inspectable `RoutingRule`s — each a
  chemistry paired with a one-line biological rationale and a pure
  `(resolved, intent)` predicate (a transition SNV → base editing; any precise
  small edit → prime; disruption intent → nuclease). Adding or relaxing a rule is
  a one-line data change and every verdict is explained.
  `alleleforge.design.ranking`: multi-objective ranking projecting every
  candidate — regardless of chemistry — onto four shared, higher-is-better
  objectives (calibrated efficiency, outcome cleanliness, off-target safety,
  reagent simplicity), ordered by a transparent weighted sum (defaults 0.35 /
  0.30 / 0.30 / 0.05, all overridable and echoed in output) **and** a Pareto
  front. The safety term is computed against the **worst-affected ancestry**, not
  the average, so a guide safe on average but dangerous in one population is
  correctly down-ranked. `alleleforge.design.designer.design`: resolves any input
  form (or an already-`ResolvedVariant`), routes, enumerates and scores per
  chemistry, ranks across them, and returns a `RankedMenu` with the Pareto front
  and a full provenance block. **Degrades gracefully** — an unavailable model, a
  failing enumeration, or a chemistry that finds nothing is recorded with its
  reason in the menu rationale while the rest of the menu still returns.
- **Phase 11 — Reporting & oligo output.** Turns a ranked menu into the
  artifacts users consume, leading with the research-use disclaimer and ending
  with full provenance on every render — **dependency-free**.
  `alleleforge.report.oligos`: cloning-ready annealed oligo duplexes per
  chemistry — SpCas9 / base-editor sgRNAs (vector overhangs + U6 `G`) and
  pegRNAs (spacer duplex + 3' extension carrying RTT + PBS + the epegRNA motif,
  plus the PE3/PE3b ngRNA duplex) — parameterized by named `VectorScheme`s
  (lentiGuide BsmBI, pX330 BbsI, pegRNA GG BsaI). Every set `reconstruct()`s the
  intended spacer / RTT / PBS, the headline round-trip invariant.
  `alleleforge.report.builder`: assembles a `RankedMenu` into a serializable
  `DesignReport` (per-candidate reagent summary, calibrated efficiency, top
  outcome alleles, ancestry-stratified off-target table, oligos, flags,
  rationale). `alleleforge.report.export`: JSON (full report, or the menu
  validated against the Phase 1 schemas), one-row-per-candidate TSV, and
  lazy-`polars` Parquet. `alleleforge.report.html`: a self-contained interactive
  HTML page — Plotly charts pulled from a CDN with figure specs inlined as JSON
  (no Python plotting dependency, no sequence data leaves the page) — and
  `alleleforge.report.pdf`: a small pure-Python writer emitting a valid,
  print-ready multi-page PDF. JSON Schemas emitted for the new report and oligo
  models. Cites the lentiCRISPRv2 (Sanjana et al. 2014), pX330 (Ran et al.
  2013), pegRNA GG-acceptor (Anzalone et al. 2019), and epegRNA motif (Nelson
  et al. 2022) cloning protocols.
- **Phase 12 — CLI (`aforge`).** A thin, reproducible, config-driven Typer shell
  over the library (new optional `cli` extra) with **no business logic** of its
  own. `aforge resolve` normalizes any input form; `aforge design` runs the full
  variant→ranked-menu pipeline and renders JSON / TSV / HTML / PDF (writing a
  `.provenance.json` sidecar next to file output); `aforge offtarget` runs a
  standalone population-aware search for a spacer; `aforge data list`/`show`
  inspects the dataset registry; `aforge bench` is wired for Phase 14. Global
  `--seed` / `--reference` / `--cache-dir` / `--verbose` / `--version`, a
  `--json` flag on every command, `--config run.toml` with CLI overrides, and
  ranking-`--weights` parsing. Meaningful, distinct exit codes (`0` ok, `2`
  usage, `3` missing data, `4` unavailable feature); runs are reproducible from
  the echoed seed + config modulo timestamp. The `aforge` entry point now
  resolves to the real Typer app; the CI test and type-check jobs install the
  `cli` extra. CLI usage page added to the docs.
- **Phase 13 — Web UI & API.** A FastAPI backend (`alleleforge.web.api`) exposing
  the library over HTTP and a dependency-free served single-page frontend
  (`alleleforge.web.frontend`). `create_app(...)` builds a thin async layer with
  **no business logic beyond orchestration**: `resolve`, `design`
  (`?format=json|html|pdf`), `offtarget`, `data` list/show, `bench`, and
  `health` endpoints, each validating requests/responses against the Phase 1 /
  Phase 11 pydantic schemas with auto-generated OpenAPI. Long design runs go
  through an **in-process async job queue** (`POST /api/jobs/design` →
  `GET /api/jobs/{id}`) that runs work in a worker thread with a state/progress
  status endpoint. The reference genome is supplied by the deployment
  (`create_app(reference=...)` or `ALLELEFORGE_REFERENCE_FASTA`); endpoints that
  need it return `503` until one is configured. The served frontend implements
  the variant-first journey (entry → ranked menu with interactive Plotly +
  ancestry-stratified off-target → oligo/report export) by embedding the
  server-rendered HTML report, with a prominent research-use disclaimer and a
  no-egress notice. **All compute is local: the app makes no outbound network
  call and transmits no sequence data externally**, asserted by a test that
  fails if any socket connects during a design request. New `Dockerfile` and
  `docker-compose.yml` for one-command local deploy; `httpx` added to the `web`
  extra and `pytest-asyncio` to `dev`; `GenomicInterval` gains a clean
  `chrom:start-end(strand)` `__str__`. 31 async endpoint tests (httpx +
  ASGITransport) cover every route, schema validation, the job lifecycle, exit
  paths, and the no-egress guarantee. Web API page added to the docs.
- **Phase 14 — CRISPR-Bench.** A standardized, calibration-first benchmark for
  guide- and edit-design models under `alleleforge.benchmark` (an installed
  subpackage, pure-Python and dependency-light, held to the same
  `mypy --strict`/ruff/coverage gates as the rest of the library). Five fixed
  task contracts (`tasks.py`): Cas9-efficiency and PE-efficiency (regression),
  Cas9-outcome and BE-outcome (distribution), and off-target-classification.
  Provenance-stamped, license-aware datasets (`datasets/`) shipped as small
  **synthetic fixtures** for CI, with the real corpora (Rule Set 3, FORECasT,
  BE-Hive, PRIDICT2, GUIDE-seq) fetched at runtime through the consent-gated
  registry. **Frozen, content-hashed splits** (`splits/`) with deliberate
  cross-cell-type test folds; `load_split()` re-verifies both the dataset content
  hash and the split membership hash on read and raises `SplitIntegrityError` on
  any drift — changing the data or the split requires a new version. A
  pure-Python metric battery (`metrics.py`): Spearman/Pearson, KL/top-k,
  AUROC/AUPRC, and **Expected Calibration Error required on every task**
  (interval coverage for regression, binned reliability for classification,
  predicted-mode reliability for distributions). A `runner.py` that evaluates any
  `BenchScorer` (the library's efficiency `Scorer`s already conform), enforces
  the no-bare-float contract at the seam, and emits a **signed** (content-hashed),
  provenance-stamped `BenchmarkResult`. A model-card-gated `leaderboard.py`
  (`Submission`/`Leaderboard`) that rejects unsigned, edited, or uncarded entries,
  ranks by metric direction (KL/ECE ascending), and renders static
  Markdown/HTML with calibration shown next to accuracy. A reference
  `BaselineScorer` fit on the train-fold marginal so every task runs out of the
  box. `aforge bench list` / `aforge bench run` wired over the runner. 63 tests
  (metrics vs hand-computed values, split-integrity tamper/drift detection,
  end-to-end runner across all kinds with signature reproducibility, leaderboard
  gating, and CLI). New `benchmark/README.md` (datasets/licenses/citations, split
  philosophy, submission format, launch plan), a CRISPR-Bench docs page,
  benchmark JSON schemas, and a deterministic fixture generator
  (`scripts/make_benchmark_fixtures.py`).
- **Phase 15 — Documentation, examples, and release.** Two new runnable example
  notebooks: `examples/02_population_offtarget.ipynb` (reproduces the
  reference-bias / `rs114518452` ancestry-stratified off-target finding;
  Cancellieri & Pinello, *Nat Genet* 2023) and `examples/03_batch_vcf.ipynb`
  (cohort-scale design reduced to one auditable summary with provenance). All
  three notebooks are **self-contained against the stub models** and **executed in
  CI** via a new `examples` job (`pytest --nbmake examples/ --no-cov`); `nbmake`
  and `ipykernel` added to the `dev` extra, and `01_clinvar_to_design.ipynb`
  normalized to nbformat 4.5 (cell ids). New docs pages: a deployment & operations
  guide (`docs/deployment.md`), an examples/tutorials gallery (`docs/examples.md`),
  and a methods-preprint outline (`docs/paper/outline.md`), all wired into the
  mkdocs nav and built strictly in CI. Release engineering: a tag-triggered
  `release.yml` workflow (build → PyPI via OIDC Trusted Publishing → multi-arch
  `linux/amd64`+`linux/arm64` Docker image to GHCR → GitHub Release), a Zenodo
  metadata file (`.zenodo.json`) for DOI minting on first tag, and a bioconda-style
  recipe (`conda/meta.yaml`). README updated with the runnable-examples gallery and
  the release/packaging matrix; all fifteen build phases are now complete.
- **v0.1.0 acceptance suite (`tests/test_acceptance.py`).** Encodes the
  specification's §16 "definition of done" as six executable end-to-end checks,
  complementing the per-component unit tests: a **ClinVar accession** flows
  through `design()` to a complete menu (every candidate carrying a calibrated
  efficiency interval, an outcome distribution, and an off-target report or an
  explicit reason); the unified entry point **reaches every chemistry** (base,
  prime, nuclease); a run is **reproducible from seed** (identical serialized
  menu); the **reference-bias / `rs114518452`** off-target case is reproduced;
  **prime editing unifies all four axes**; and **CRISPR-Bench publishes** the
  Cas9-efficiency, PE-efficiency, and off-target tasks with frozen splits,
  calibration, signed results, and a working leaderboard. All run against the stub
  models, so the release contract is verified on every CI run.
- **Native FM-index kernel (`aforge_native::bwt`).** The Rust crate now implements
  the genome-scale FM-index off-target search path the layout reserved for it:
  `fm_build` / `fm_count` / `fm_locate` and a `NativeFmIndex` object exposing
  `count`, `locate`, `pam_sites` (with IUPAC PAM expansion), `content_hash`, and
  `length`. `FMIndex.build(prefer_native=True)` transparently uses it when the
  crate is present and falls back to pure Python otherwise. Construction mirrors
  the Python fallback exactly (sentinel, C-table, checkpointed occ/rank, sampled
  suffix array, LF-walk, SHA-256 content hash), and a new parity test module
  (`tests/genome/test_native.py`, marked `native`) pins the native output to be
  **byte-identical** to the fallback across texts, patterns, and PAM sites. The
  CI `rust` job now builds the wheel and runs the parity suite; the existing
  FM-index tests are pinned to the pure-Python path so they stay deterministic
  whether or not the crate is built. Adds the `sha2` crate dependency.
- **Post-v0.1.0 roadmap (`SPEC_V2.md`).** A phase-structured contract for the work
  to "bake" the release before v1.0: R0 release hardening (pin real artifact
  hashes), R1 real-weights integration, R2 native `kmer`/`haplotype` kernels +
  SA-IS wired onto the off-target hot paths, R3 external-tool adapters, R4 scale,
  R5 validation/calibration + methods preprint, and the R6 v1.0 criteria.
- **R1 — consent-gated real backbone weights (first slice).** Real
  sequence-embedding backbones now resolve their weights through the
  license-gated, consent-required, checksum-verified model zoo instead of a bare
  `from_pretrained(model_id)`. Adds `ModelRegistry.authorize(name, *, use,
  consent)` (the license + consent gate for hub-resolved models, returning the
  provenance `ModelCheckpoint`); `SequenceEmbedder.resolve_weights()` (uses the
  pinned-artifact download+checksum path when the card pins a hash, else the
  authorize gate, recording the resolved checkpoint) and `model_checkpoint()`;
  and `EnsembleEfficiencyScorer.backbone_checkpoint()` so the cas9 efficiency
  chemistry stamps the backbone into provenance. Adds model cards for the
  `caduceus` and `evo2` backbones. The full consent/license/checksum flow is
  CI-tested with an injected downloader (no network, no torch — 8 new tests); the
  real tensor load stays behind the `real_weights` marker. The default backbone
  (Nucleotide Transformer v2, CC-BY-NC-SA) is loadable for research and refused
  for commercial use by the license gate.
- **R1 — backbone ONNX export path (`export_onnx`).** The HuggingFace backbone
  embedders now export the consent-resolved model to a portable ONNX graph
  (`_HuggingFaceEmbedder.export_onnx(path, *, sample_sequence=...)`): the model is
  resolved through the same consent gate, traced on a sample sequence, and written
  with **dynamic batch and sequence axes** (opset 17) so it runs under any ONNX
  runtime without torch/transformers at inference time. This replaces the prior
  `NotImplementedError` stub. The export code is wired now; running it needs the
  `ml` extra and real weights, so — like the tensor forward pass — it stays behind
  the `real_weights` marker.
- **R5 — reproducible SVG figures for the docs & preprint (`alleleforge.viz`).** A
  dependency-free, hand-rolled SVG bar-chart renderer (`viz.svg`, the same
  no-plotting-stack discipline as the PDF report) plus four figures (`viz.figures`)
  computed from the **weight-free, deterministic** pipeline: the reference-bias
  reproduction (reference-only vs population-aware off-target nomination), the
  split-conformal coverage restoration, per-task CRISPR-Bench ECE, and the
  cross-cell-type generalization gap. Figures regenerate byte-for-byte from config +
  seed (`scripts/figures.py`, `make figures`), are committed under
  `docs/assets/figures/`, and are embedded in the README and methods preprint. The
  deterministic calibration/generalization computations moved into a library module
  (`alleleforge.benchmark.calibration`) so the markdown report and the figures share
  one source of truth; `scripts/calibration_study.py` now delegates to it. 26 new
  tests; no new runtime dependency.
- **R1 — menu provenance now records every model invoked.** `design()` stamps the
  card-backed `ModelCheckpoint` of each eligible chemistry's scorers into
  `RankedMenu.provenance.models`, which previously always shipped empty despite the
  field documenting "checkpoints of every model invoked." Each vertical exposes its
  default checkpoints (`cas9_model_checkpoints()`, `prime_model_checkpoints()`,
  `base_editor_model_checkpoints()`); the designer aggregates and dedupes them by
  name + version, scoped to the chemistries that were actually eligible (a
  knock-out records only the Cas9 efficiency + outcome models, an A→G install
  records BE-DICT + PRIDICT2.0). The HTML and PDF report footers now render the
  invoked models, and the reproducibility golden captures them (they are
  deterministic and scientifically meaningful, so they belong in the digest).
- **R1 — consent-gated trained prime-efficiency adapters.** The trained
  prime-editing efficiency adapters (`DeepPrimeAdapter`, `GenETAdapter`) now
  resolve their weights through the same consent/license/checksum flow as the
  backbone: `resolve_weights()` (pinned-artifact download+checksum or the
  `authorize` gate) and `model_checkpoint()`, and `score()` runs the consent gate
  before any inference. Adds bundled, license-gated model cards for `deepprime`
  and `genet` (both research-only, so the license gate refuses commercial use).
  The flow is CI-tested with an injected downloader (no ML stack); the trained
  forward pass stays gated behind real weights. The `PridictScorer` heuristic
  baseline remains the CI default.
- **R1 — shared `WeightGate` + consent-gated outcome adapters.** Extracted the
  consent/license/checksum weight-resolution flow into a single
  `model_zoo.loader.WeightGate` mixin and refactored every trained model onto it
  (the sequence backbone, the prime-efficiency adapters, and now the cas9-outcome
  `InDelphi`/`Lindel`/`X-CRISP` and base-edit-outcome `BE-DICT`/`BE-Hive`
  adapters), removing four copies of the same logic. Each outcome adapter's
  `predict()` now runs the consent gate before inference. Adds bundled,
  license-gated cards for `lindel`, `x-crisp`, and `be-hive` (all research-only).
  The consent/license/checksum flow is CI-tested per chemistry with an injected
  downloader (no ML stack); the trained forward passes stay behind real weights.
  `loader.py` is at 100% coverage.
- **R2 — k-mer seed kernel on the off-target scan.** A native Rust k-mer kernel
  (`kmer.rs`: `kmer_seed_positions`) with a pure-Python fallback
  (`offtarget._kmer`) and a seed-and-extend prefilter wired into the off-target
  scan (`scan_sequence(..., seed=...)`). By the pigeonhole bound (partition the
  spacer into `E+1 = mismatches+dna_bulges+rna_bulges+1` blocks; ≥1 is uncut and
  substitution-free) any in-budget alignment shares an exact length-`k` seed with
  the spacer, so the prefilter is a **proven superset** — it never drops a hit.
  Equivalence is pinned by an exhaustive randomized test (400+ cases, seeded ≡
  brute-force across budgets/PAMs/strands), and the native seeding is pinned
  byte-for-byte to the Python path. The prefilter **auto-engages only when the
  seed is selective** (`k >= 5`); a micro-benchmark
  (`scripts/native_speedup.py`) measures **~2–4x** for high-stringency scans, a
  native seed lookup **~5–6x**, and a transparent no-op at the default
  ≤4-mismatch+bulge budget (where the FM-index is the genome-scale path). The CI
  rust job runs the native k-mer parity suite.
- **R2 — true-linear FM-index suffix array build (SA-IS).** The native FM-index
  suffix array (`bwt.rs`) is built by **SA-IS** (`sais.rs`, Nong–Zhang–Chan
  induced sorting, `O(n)`) — superseding the interim prefix-doubling
  (`O(n log² n)`) build, which itself superseded the direct sort's `O(n² log n)`
  that collapsed on the long poly-A / poly-N runs and tandem repeats real genomes
  contain. The unique sentinel keeps the suffix array unique, so it is
  byte-identical to the direct sort: pinned **directly** by a parity test of the
  newly-exposed `fm_suffix_array` against the ground-truth direct sort (textbook
  pathological inputs — all-same/alternating runs, tandem repeats — plus a 500-case
  fuzz) *and* end-to-end by the FM-index `count`/`locate`/`pam_sites` parity over
  low-complexity and random-long inputs. The CI rust job runs all of it.
- **R2 — FM-index seed-and-extend wired into the reference scan.** The
  off-target engine's stage-1 reference search now runs FM-index seed-and-extend
  (`scan_sequence(..., use_fm_index=...)`, threaded from `engine.search`): each
  concrete PAM is *located* in a content-addressed FM-index (the PAM is the seed)
  and only those anchors are *extended* by the shared alignment, replacing the
  linear `O(n)` PAM pass. It returns **byte-identical hits** to the brute-force
  scan — pinned by a randomized parity test at both the `scan_sequence` and
  `engine.search` levels (across mismatch/bulge budgets and both strands) — and
  **auto-engages per region** past `FM_INDEX_AUTO_THRESHOLD` (1 Mb), so
  genome-scale contigs take the indexed path while small inputs stay on the
  linear scan. The native Rust `bwt` kernel and the pure-Python FM-index share
  the interface; CI exercises the Python path, the rust job the native parity.
- **R2 — native haplotype-walk kernel wired into the haplotype engine.** A Rust
  kernel (`haplotype.rs`: `haplotype_apply_variants`) with a pure-Python fallback
  (`offtarget._haplotype`) materializes a common haplotype's alternative sequence
  by applying its full variant set to the reference window — applied right-to-left
  so indels keep later edits' coordinates valid, returning `None` on a
  reference-base clash (a phasing/coordinate mismatch the engine skips rather than
  mis-applying). It is wired into `offtarget.haplotype._apply_all` (the hot inner
  step of stage 3) and is **byte-identical** to the Python path, pinned by a fuzz
  parity test over lowercase refs, `N` bases, indels, overlaps, and
  out-of-window positions. The R2 micro-benchmark
  ([`scripts/native_speedup.py`](scripts/native_speedup.py)) measures **~4x**. With
  this the three spec kernels — `bwt`, `kmer`, `haplotype` — are all on their hot
  paths behind the fallback-plus-parity discipline; the CI rust job runs the
  native parity suite for each.
- **R3 — external tool adapters made real (Cas-OFFinder · VEP · HGVS).** The
  three previously-inert `NotImplementedError` adapters now have working
  implementations, each tested against **recorded fixtures** with the live
  network/binary call factored behind an injection point (opt-in,
  `live_integration`-marked, never run in CI):
  - **Cas-OFFinder** (`offtarget.cas_offinder_adapter`): `format_input` builds the
    binary's three-line input deck; `parse_output` reads both the legacy 6-column
    and bulge-aware 8-column result layouts into `(chrom, position, strand)` loci;
    `run(..., runner=...)` orchestrates write→invoke→parse with an injectable
    runner, and the existing `disagreements()` cross-check flags divergence from
    the native engine.
  - **VEP** (`variant.effect`): `VepRestPredictor` queries the Ensembl region
    endpoint through an injectable fetcher; `parse_vep_response` maps the JSON to a
    `VariantEffect` (MANE/canonical or named-transcript selection, most-severe SO
    term, impact tier), cached by `(variant, assembly, transcript)`.
  - **HGVS** (`variant.hgvs_adapter`): `HgvsLibraryProjector` wraps the real `hgvs`
    library (UTA + SeqRepo `AssemblyMapper.c_to_g`) behind the existing
    `HgvsProjector` interface, degrading to a clear `RuntimeError` when the
    optional library is absent.
  Adds the `live_integration` pytest marker for the opt-in live tests.
- **R4 — cohort-scale batch design (`design.design_many`).** Streams a whole
  cohort through `design`: the input is consumed lazily (a `cyvcf2` stream, a
  generator, or a list), and only the per-item working set is held — each ranked
  menu is summarized (and optionally written to `output_dir`), then released, so
  peak memory does not grow with cohort size (`on_result` makes the run `O(1)` in
  cohort size). Runs are **resumable** through a JSONL run manifest that opens
  with a provenance header (version, seed, reference build, intent, start time)
  and against which a re-run **skips items already recorded**; per-item failures
  are **captured, not fatal** (an unresolvable variant is recorded with its error
  and the cohort continues). A thread-parallel path (`max_workers` +
  `reference_factory`, since a pyfaidx handle is not thread-safe to share)
  produces summaries identical to the sequential run. Returns a `CohortRunReport`
  with the run counts and provenance.
- **R4 — `cyvcf2` fast path (`variant.iter_vcf`).** The streaming VCF adapter that
  *produces* the lazy iterator `design_many` consumes: it reads a VCF with
  `cyvcf2` (htslib-backed) and yields one `VcfRecord` per **concrete ALT allele**,
  splitting multi-allelic rows, skipping symbolic/`<DEL>`/spanning-`*`/non-ACGTN
  alleles, and dropping non-`PASS` records by default — so a whole-VCF cohort flows
  through the designer with bounded memory. The reader is **injectable**: a path is
  opened with `cyvcf2` lazily (a clear `RuntimeError` names the `genome` extra when
  it is absent), but any iterable duck-typed to the cyvcf2 `Variant` shape works,
  so the split/filter logic is fully CI-tested with a fake reader and **no native
  dependency**. (Whole-genome scale validation on a real VCF remains an opt-in
  nightly.)
- **R4 / Phase 12 — `aforge batch` cohort command.** The cohort path now reaches
  the CLI audience (the "three audiences, one core" principle): `aforge batch
  <input>` streams a whole cohort through `design_many`, **auto-detecting** a VCF
  (`.vcf`/`.vcf.gz`/`.bcf` → the `iter_vcf` cyvcf2 fast path) from a plain
  one-variant-per-line list (`#` comments skipped). It exposes the full streaming
  contract as flags — `--manifest` (resumable JSONL run), `--output-dir` (durable
  per-item menu JSON), `--max-workers` (thread-parallel with a per-worker
  reference), `--summary-tsv` (per-item table), plus `--intent`/`--populations`/
  `--weights`/`--no-offtarget` forwarded to `design`. Emits a human summary or, with
  `--json`, the full provenance-stamped run report; a VCF input without `cyvcf2`
  surfaces as a clean exit code `4` (unavailable), not a crash.
- **R4 / Phase 13 — `POST /api/batch` cohort endpoint.** Cohort design now reaches
  the **third audience** (the web): the endpoint takes a JSON variant list, runs
  `design_many`, and returns the per-item summaries, counts, and run provenance
  (per-item failures isolated, not fatal), all behind the same `503`-until-a
  -reference-is-configured contract as `/api/design`. The shared design knobs
  (intent/chemistries/weights) are factored into one `_design_options` helper used
  by both `/api/design` and `/api/batch`. Cohort design is now reachable from all
  three surfaces (library `design_many`, `aforge batch`, `POST /api/batch`) over one
  core.
- **R4 / Phase 13 — browser cohort UI.** The served single-page frontend gains a
  **cohort (batch) tab** beside the single-variant one: a one-variant-per-line
  textarea (blank/`#`-comment lines skipped) posts to `/api/batch` and renders the
  per-item summary table (status, best chemistry, efficiency, worst off-target,
  candidate count), with a JSON download. It keeps the no-egress, no-third-party
  -script guarantee — cohort design is now usable end to end from the browser.
- **Phase 13 fix — `GET /api/bench` lists the CRISPR-Bench tasks.** The endpoint
  previously returned a stale `501 "arrives in Phase 14"`; Phase 14 has shipped, so
  it now returns the five tasks with their kind, chemistry, dataset, primary metric,
  and metric battery (ECE included) — the HTTP mirror of `aforge bench list`.
- **Phase 14 — `aforge bench leaderboard` command.** `bench run` already emitted
  signed, provenance-stamped result JSONs but nothing aggregated them; the new
  command reads one or more result files, groups them by model into **card-gated
  submissions**, and renders the leaderboard as Markdown (default) or HTML. It
  enforces both honesty gates on read — every result must verify its own signature
  and carry a complete model card (name/license/citation) — so a number edited
  after signing, or a model without a card, is refused (exit `2`); a missing file
  exits `3`. The benchmark's "publish the leaderboard" story is now reachable from
  the CLI, not just the `Leaderboard` API.
- **R4 — content-addressed cross-run caches.** A shared
  `alleleforge.cache.ContentAddressedCache` — a sharded, atomically-written
  (temp-file-then-rename) disk key/value store under the cache dir, keyed by the
  SHA-256 of the inputs that determine a result — backs two cross-run memos:
  - **Embeddings:** `CachedEmbedder.persistent(embedder)` reuses embeddings across
    runs via a `PersistentEmbeddingCache` scoped per backbone identity (so two
    backbones never collide); a sequence embedded in one run is free in the next.
  - **Off-target:** `OffTargetCache` + `search(..., cache=...)` reuse the expensive
    reference scan. It is **safety-gated**: used only when the result is a pure
    function of the reference — the default scorer and no gnomAD/haplotype/patient
    augmentation — so a stale entry can never be served for a query whose external
    data the content key does not capture. A changed budget/PAM/threshold/reference
    is a distinct key; a custom scorer or any augmentation bypasses the cache.
- **R4 — whole-genome on-disk, memory-mapped FM-index (`genome.GenomeIndex`).**
  Builds one content-addressed FM-index per contig (both strands) over a
  reference, driven by **R2's native SA-IS**: the on-disk `FMIndex` build now uses
  the linear-time kernel (`_suffix_array` → `fm_suffix_array` when the crate is
  built), so the persistent + memory-mapped path scales to whole chromosomes
  instead of being limited to the pure-Python direct sort. The index **survives
  across runs** (a re-run memory-maps the cached contig index rather than
  rebuilding) and is queried over its memory map without pinning it in RAM. The
  off-target engine consumes it via `search(..., genome_index=...)` (and
  `scan_sequence(..., fm_plus=, fm_minus=)`) for the reference scan — **identical
  hits** to the per-call build (a parity test pins this across budgets and both
  strands), but built once and reused. Validated in CI on a downsampled-chromosome
  fixture in the rust job (native SA-IS build → mmap query → linear-scan parity →
  cross-run reuse); full hg38 / T2T-CHM13 builds are an opt-in nightly.
- **R5 — conformal interval recalibration + calibration-study script.**
  `scoring.ConformalCalibrator` recalibrates predictive *intervals* to a target
  coverage with the finite-sample **split-conformal guarantee** — the regression
  analog of `IsotonicCalibrator` for probabilities, and the first producer of the
  long-reserved `UncertaintyMethod.CONFORMAL`. It learns a single multiplicative
  width scale from a held-out calibration set, so recalibrated intervals meet the
  nominal coverage while the model's *relative* per-example uncertainty shape is
  preserved (normalized conformal). `empirical_coverage` measures interval coverage
  to decide when recalibration is needed. `scripts/calibration_study.py`
  regenerates the calibration report — every CRISPR-Bench task's primary metric and
  ECE, plus a conformal recalibration demonstration (coverage before/after at the
  spec's 80%/90% levels) — deterministically from config + seed. The recalibration
  machinery and the report are CI-tested on the weight-free splits; the real-data
  ECE numbers fill in with R1.
- **R5 — cross-cell-type generalization gap.** `benchmark.generalization_gap`
  quantifies the drop in a model's primary metric from an in-context fold (a
  training-seen cell type, default `val`) to the held-out cell type (default
  `test`) — the field-wide reality that a model tuned on one cellular context
  predicts an unseen one worse. The gap is **orientation-corrected** (positive
  always means worse held-out generalization, whether the metric is higher- or
  lower-is-better) via a `HIGHER_IS_BETTER` map, and computed through a shared
  `evaluate_fold` primitive. `scripts/calibration_study.py` now reports the
  per-task gap table (the cross-cell-type chemistry tasks; off-target, stratified
  by sequence pair, is excluded). Pinned by a test where a scorer that memorizes
  the in-context fold but is ignorant on the held-out one shows a positive gap.
- **R5 — methods-preprint draft.** `docs/paper/preprint.md` drafts the working
  outline into a full manuscript: abstract, methods (the domain model & provenance,
  the genome/variant front end, the population/haplotype off-target engine, the
  license-gated scoring substrate and uncertainty methods, the three chemistries,
  conformal recalibration, and the native kernels), the CRISPR-Bench design, the
  **weight-free end-to-end results** (the `rs114518452` reference-bias reproduction
  and the split-conformal coverage-before/after table regenerated from
  `scripts/calibration_study.py`), reproducibility, and discussion. The
  accuracy-vs-published-numbers results are explicitly fenced off as `[pending R1]`,
  so the draft never overstates what is measured. Wired into the docs nav (under a
  *Methods preprint* section) and linked from the outline, the README roadmap, and
  the citation block.
- **Docs — rendered diagrams on the published site + status fix.** Enabled
  Material's native **Mermaid** rendering (`pymdownx.superfences` custom fence) so
  the documentation site renders architecture and sequence diagrams as figures
  rather than code blocks, and gave the docs home (`docs/index.md`) the layered
  **architecture flowchart** and the **variant-first journey** sequence diagram that
  the README already carried. Fixed the stale build-status table on the docs home
  (Phase 14 CRISPR-Bench and Phase 15 docs/examples/release were still marked
  *next*/*planned* — both have shipped; all fifteen v0.1.0 phases now read *done*),
  and pointed the post-v0.1.0 roadmap at `SPEC_V2.md`.
- **R0 — supply-chain hardening.** Dependabot now tracks all three dependency
  surfaces — `pip`, `cargo`, and `github-actions` (`.github/dependabot.yml`,
  grouped weekly PRs); a CI `security` job runs `pip-audit` (PyPI advisory DB)
  and `cargo audit` (RustSec); and the release pipeline emits a **CycloneDX
  SBOM** over the resolved dependency closure (`sbom` job) and attaches it to the
  GitHub Release alongside the sdist/wheel.
- **R0 — reproducibility audit.** `scripts/reproduce.py` (and `make reproduce`)
  re-derives the canonical weight-free design run (a ClinVar accession → ranked
  menu, the §16.1 acceptance scenario) from config + seed, asserts run-to-run
  determinism, and diffs a canonicalized digest — volatile provenance stripped,
  floats rounded for cross-platform stability — against a committed golden
  manifest (`scripts/reproduce_golden.json`). A CI `reproduce` job gates it.
- **R0 — CI/CD runner hardening (Node 24).** Bumped every pinned GitHub Action off
  the deprecated Node 20 runtime, which GitHub force-migrates on 2026-06-16:
  `actions/checkout@v4→v5`, `actions/setup-python@v5→v6`, and (in the release
  pipeline) `actions/upload-artifact@v4→v7` + `actions/download-artifact@v4→v7` (the
  matched Node-24 pair, chosen over v8 to avoid its ESM/hash-mismatch breaking
  changes for the trivial named-artifact handoff), `softprops/action-gh-release@v2→v3`,
  and the Docker buildx stack (`setup-qemu@v3→v4`, `setup-buildx@v3→v4`,
  `login@v3→v4`, `metadata@v5→v6`, `build-push@v6→v7`). Both workflows now run
  entirely on Node 24; the CI workflow is verified green on the new majors, and the
  Docker/composite actions (`gh-action-pypi-publish`, `dtolnay/rust-toolchain`) are
  unaffected by the Node deprecation.

### Fixed

- **Out-of-range CFD/Cas12a mismatch weights are caught at scoring time.** An
  injected mismatch- or PAM-weight table with a value outside `[0, 1]` previously
  produced a specificity score `> 1.0` that only failed downstream, as an abort in
  the `OffTargetSite` validator. `cfd_score` / `cas12a_cfd_score` now validate each
  weight as it is applied and raise a clear `ValueError` naming the offending weight
  (base substitution and position), so a bad table is a scoring-time error, not a
  late crash. (Part of the in-progress `ship-published-cfd-matrix`; vendoring the
  authentic Doench 2016 matrix as the default remains blocked on an authoritatively
  sourced, cross-verified copy — it must not be fabricated.)

### Added

- **`aforge offtarget` and `POST /api/offtarget` now expose every engine knob.**
  The off-target engine's `search()` has always accepted a tunable bulge budget
  (`dna_bulges` / `rna_bulges`), CFD/MIT reporting thresholds (`cfd_threshold` /
  `mit_threshold`), and a carrying-frequency floor (`maf`) — and the docs state
  "every threshold is a parameter" — but the CLI command and the web request
  hardcoded all of them to the defaults, exposing only `mismatches` and
  `populations`. Both surfaces now pass the full set through (CLI options with
  range validation; `OffTargetRequest` fields with `ge`/`le` bounds), so a user
  can tighten the thresholds, drop bulges for speed, or change the population
  stringency without dropping to the Python API. The library, CLI, and web are
  again faithful mirrors of one engine. Pinned by monotonic tests on both
  surfaces (tightening a knob can only remove nominations, never add).

### Fixed

- **Async design jobs hold a strong task reference (no GC mid-flight).** The web
  `JobManager` scheduled each job with a bare `asyncio.create_task(_run())` whose
  result was discarded, suppressing the lint that flags exactly this
  (`# noqa: RUF006`) with the justification "lifetime tracked via the record
  store" — but the store holds the job *record*, not the running *task*, and
  asyncio keeps only a weak reference to a task, so a job could be garbage-
  collected mid-execution. The manager now keeps each task in a set and clears it
  with a done-callback, so a running job is strongly referenced until it finishes
  and the set stays bounded (no per-job leak). The misleading suppression is gone.
  Pinned by JobManager unit tests (jobs run to completion and the tracking set is
  released, for both success and failure).

- **`ReferenceGenome` is now thread-safe for concurrent reads.** The web app
  holds a single shared `ReferenceGenome` on `app.state`, and its compute
  handlers (`/api/design`, `/api/offtarget`, `/api/batch`) are sync `def`s —
  which FastAPI runs in a threadpool, so concurrent requests fetch from that one
  handle on different threads at the same time. `pyfaidx` keeps a shared file
  position (a seek+read is not atomic), so those concurrent fetches could
  silently return interleaved, wrong reference bytes — corrupting the very
  sequence the off-target and edit design depend on, under nothing more exotic
  than two simultaneous requests. The cohort path already knew pyfaidx isn't
  thread-safe to share (it hands each worker its own handle via a
  `reference_factory`); the web layer did not. `ReferenceGenome.fetch_result`
  now guards the pyfaidx read with a per-instance lock, covering only the read
  (not the CPU-bound design/search that follows), so a shared instance is
  correct under concurrency while compute still parallelizes. Pinned by a test
  that fetches many varied intervals across a threadpool and asserts each is
  byte-exact.

- **Robustness: enumeration margins and the mmap loader no longer crash/leak on
  edge inputs.** Three small hardening fixes, swept as a class:
  - `enumerate_prime(..., pbs_lengths=())` and `enumerate_base_edits(..., editors=())`
    raised `ValueError: max() arg is an empty sequence` from the reference-window
    *margin* computation — an asymmetry, since the sibling `max(rtt_homologies,
    default=5)` was already guarded. Both `max()` calls now carry a `default`, so
    an empty parameter degrades to an empty result (no candidates) like every
    other empty enumeration input, rather than crashing.
  - `FMIndex.load()` opened the BWT file, mmap'd it, then closed the fd — but a
    failure in `mmap.mmap()` (a corrupt cache, `ENOMEM`) leaked the descriptor.
    The open is now a `with` block, releasing the fd on the error path too; the
    mmap still outlives it as before.
  Pinned by tests for the two empty-parameter paths; no behavior change on any
  in-range input. No type/schema/golden change.

- **Menu rationale notes are now byte-deterministic.** When a caller restricted
  the chemistries, `design()` listed each *requested-but-ineligible* chemistry by
  iterating a `set` difference (`requested - eligible`) and appending to the
  notes that compose the serialized menu rationale — so with two or more such
  chemistries the note order depended on the process hash seed and varied run to
  run, breaking byte-reproducibility of the rationale string. The canonical
  reproducibility run passes no `chemistries`, so the golden never exercised this
  path. The difference is now emitted in sorted order. Pinned by a test (two
  ineligible chemistries → notes in sorted order) verified under varying
  `PYTHONHASHSEED`. (Companion to the ancestry-stratification determinism fix.)

- **Ancestry stratification is now byte-deterministic.**
  `OffTargetReport.ancestry_stratification()` built its per-ancestry mapping by
  iterating a `set`, and `worst_ancestry()` then took `max()` over that mapping —
  so the **key order** of the returned/serialized strata, and the ancestry chosen
  on a worst-case **tie**, depended on the process hash seed and varied run to
  run. That is a reproducibility break in a safety-relevant output (the worst-
  affected ancestry drives the ranking's safety term and appears verbatim in
  reports and the `aforge offtarget` / `POST /api/offtarget` JSON), even though
  the values themselves were always correct. The reproducibility golden missed it
  because its canonicalizer sorts dict keys before hashing and the canonical run
  has no ancestry tie. Ancestries are now emitted in **sorted order** and a
  worst-case tie resolves to the **alphabetically-first** ancestry, so the
  serialized report is identical across runs and machines. Pinned by a test that
  passes under varying `PYTHONHASHSEED`.

- **VEP transcript selection now prefers MANE Select with strict priority.** For
  the default `transcript="MANE_SELECT"`, `_select_transcript` returned the first
  consequence block that was MANE Select **or** canonical in a single pass — so a
  merely-canonical transcript that happened to precede the MANE Select one (VEP
  does not guarantee MANE-first ordering) was reported instead of the MANE one.
  Selection is now a strict two-pass priority — MANE Select, then canonical, then
  the first block — and both the selection and the `is_canonical` flag test
  membership by **truthiness** (a MANE accession / `canonical: 1`) rather than
  `is not None`, so an explicit falsy `mane_select` (`""`/`false`/`0`) never
  matches. The recorded HBB fixture is unaffected (its MANE transcript is first
  and truthy); pinned by two new tests (a canonical block preceding MANE, and a
  falsy `mane_select`).

- **CRISPR-Bench regression ECE is now correct under mixed interval levels.**
  `_regression_metrics` took `predictions[0].interval_level` as the single nominal
  for the interval-calibration ECE and pooled every prediction's interval against
  it. `Prediction` permits a per-prediction `interval_level`, so a scorer that
  returned mixed levels in one batch would have its calibration silently
  misreported — comparing, say, an 80% and a 50% interval against one nominal —
  in the benchmark whose entire purpose is honest calibration measurement. The
  ECE is now computed **per `interval_level` and count-weighted** across the
  groups. A homogeneous batch (the common case — every scorer uses the settings
  interval level) is one group and reduces **exactly** to the prior value, so no
  shipped number changes; a mixed-level batch is now scored correctly. Pinned by
  a unit test (the pooled result `0.3` vs the correct per-level `0.35`).

- **Removed a dead `_nick_to_edit` duplicate in `scoring/prime_outcome.py`.**
  The prime-outcome baseline carried a byte-identical copy of the nick-to-edit
  helper that lives in (and is used by) `scoring/prime_efficiency.py`; the outcome
  model never called it (it folds nick-to-edit geometry into the RTT-length
  proxy). Pure housekeeping — no behavior change.

- **`aforge offtarget --json` now emits the full per-site audit set.** The CLI
  hand-flattened each off-target site into a dict that dropped `mit_score` (added
  in this release), `dna_bulges`/`rna_bulges`, the causal-allele `frequency`, and
  the per-site `ancestries` — even though `POST /api/offtarget` returns all of
  them (it serializes the whole report). A pipeline reading the CLI JSON saw a
  strictly poorer record than an HTTP client of the same engine. The flattened
  shape is kept (friendly `locus` string, `method` key) but now carries every
  field, so the two surfaces are at parity; the human one-liner also shows the
  MIT score when defined. Pinned by an extended CLI test.

- **Model provenance now carries each model's documented failure modes.**
  `ModelCard.known_failure_modes` is parsed, validated, and required of every
  bundled card, but `ModelCard.to_checkpoint()` dropped it — so a result's
  `provenance.models` named the exact checkpoints (name, version, hash, license,
  citation) yet omitted the most safety-relevant card metadata. `ModelCheckpoint`
  gained `known_failure_modes: tuple[str, ...]`, populated by `to_checkpoint()`,
  so a `RankedMenu`/`BenchmarkResult` provenance block is **self-contained for
  safety audit** — a consumer can check a design against what each model is
  documented to get wrong without re-opening the cards. Schemas regenerated; the
  reproducibility golden re-pinned (its stamped `be-dict`/`pridict2` checkpoints
  now carry their failure modes — deterministic). Pinned by an extended test.

- **Off-target sites now record the companion MIT score (`OffTargetSite.mit_score`).**
  The engine nominates a site when **either** its CFD clears `cfd_threshold`
  (default 0.20) **or** its MIT clears `mit_threshold` (default 0.10) — an OR.
  But the MIT score was computed only for the threshold test and then discarded:
  the site stored only the primary (CFD) score, so a site retained *because* its
  MIT cleared the bar — while its displayed CFD sat below `cfd_threshold` — gave
  no record of the score that nominated it, contradicting the engine's "every
  nomination can be audited, not trusted blindly" contract. `OffTargetSite` gained
  `mit_score: float | None` (the MIT/Hsu score when defined, `None` for a bulged
  or non-20-nt alignment where MIT does not apply), populated by the engine and
  carried through to the serialized report (JSON, the `aforge offtarget` output,
  and the `POST /api/offtarget` envelope). Selection is **byte-identical** to
  before — an undefined MIT is still treated as `0.0` for thresholding — so this
  is purely additive; the reproducibility golden re-pinned only to record the new
  field (its single site now carries `mit_score: 1.0`). Schemas regenerated.

- **Haplotype off-target sites no longer over-attribute ancestry burden.** The
  haplotype path stamped the full, *unfiltered* per-population frequency dict
  (`dict(hap.frequencies)`) into each site's `ancestries` provenance, and applied
  the MAF carrying threshold to the `populations` list only when the caller
  restricted the populations — so when populations were left unset (the common
  case), a population with a trace, *sub-threshold* frequency was still recorded
  as carrying the site. `OffTargetReport.ancestry_stratification()` attributes a
  site's score to every ancestry with a non-zero entry, so those below-threshold
  populations inflated the per-ancestry off-target burden — a population-aware-
  safety regression, since the worst-affected-ancestry roll-up is what the report
  surfaces. The carrying threshold is now applied **identically on both branches**
  (mirroring the population-variant path), and `ancestries` is filtered to the
  same carrying set as `populations`, so the two provenance fields are the one
  set by construction. Pinned by a regression test (a haplotype carried in one
  population above threshold and another below it surfaces only the carrier).

- **Base-editor `bystander_burden` is now persisted on the candidate.** The
  window-outcome predictor returns two calibrated `Prediction`s per base-editor
  candidate — `p_intended_exact` and `bystander_burden` (SPEC §8) — but only the
  first was stored (as `DesignCandidate.efficiency`); the bystander burden was
  rendered into the human-readable `flags`/`rationale` strings and then dropped,
  so it was absent from every machine-readable surface (JSON, TSV, Parquet, the
  ranked menu, the web API). `DesignCandidate` and `CandidateReport` gained a
  structured `bystander_burden: Prediction[float] | None` field, carried through
  the report builder, exports (a new `bystander_burden` TSV/Parquet column), the
  HTML/PDF renderers (now showing the calibrated value + interval, not just the
  flag), and the cohort batch summary (`best_bystander_burden`, in the JSONL
  manifest and per-item TSV). Schemas regenerated; the reproducibility golden
  re-pinned to the canonical ABE run that now serializes the field. The
  cleanliness/bystander tradeoff the vertical is *ranked* on is now exportable,
  not just printable.

### Security

- **Bumped PyO3 `0.22.6` → `0.24.2`** in the `aforge_native` crate, resolving
  [GHSA / Dependabot #1](https://github.com/clay-good/alleleforge/security/dependabot/1)
  (risk of buffer overflow in `PyString::from_object`, fixed in PyO3 0.24.1). The
  crate's source already used the modern `Bound` API, so the upgrade was a clean
  dependency bump — verified with `cargo check`, `cargo clippy`, and a full
  `maturin develop` round-trip of `aforge_native.version()`.

### Changed

- **CI now gates the Rust crate.** A new `rust` job runs `cargo fmt --check`,
  `cargo clippy --lib -D warnings`, and `maturin build --release`, so the native
  toolchain (and its pinned, security-patched PyO3) is exercised on every push —
  closing the "Rust" leg of the v0.1.0 definition-of-done CI matrix and catching
  future dependency drift automatically.

### Fixed

- **Ship the PEP 561 `py.typed` marker.** The package declared the
  `Typing :: Typed` classifier and is `mypy --strict` clean, but shipped **no**
  `py.typed` marker — so a downstream type-checker silently ignored every one of
  its types (the metadata claimed typing support the distribution did not deliver).
  Added `src/alleleforge/py.typed` (hatchling bundles it into the wheel and sdist
  automatically) and a packaging test that guards the marker — plus the bundled
  model cards, benchmark splits, and web frontend — against silent removal.

[Unreleased]: https://github.com/clay-good/alleleforge/commits/main
