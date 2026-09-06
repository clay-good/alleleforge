# Changelog

All notable changes to AlleleForge are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The
project is in the `0.x` series until the three launch modalities pass
acceptance.

## [Unreleased]

### Added

- **Every number that gates what a user sees now says what kind of number it is.** The CFD and MIT thresholds
  decide which off-target sites appear in a report *at all*; the MAF threshold decides which population
  variants are considered; the GC band decides which spacers get a quality caveat. None is a published cutoff
  and three said nothing about that — `DEFAULT_CFD_THRESHOLD` carried the comment "spec defaults", which reads
  as though a specification had derived it. Each now states plainly that it is a project default, what it
  costs to be wrong, and that lowering it only ever adds sites. A test requires it, so a new judgement
  constant cannot arrive unlabeled.

- **`aforge offtarget --scorer`: the three specificity scorers are selectable at last.** `search(scorer=…)`
  took an `OffTargetScorer` object, so a scorer could only be chosen by importing its class — MIT was
  unreachable from every shell, and so was the **Cas12a analog**, a whole nuclease's scoring, implemented,
  carded and cited. The report already *named* which scorer produced its numbers; the user could not choose
  it. The off-target engine also had no shell-parity check at all — only `design()` did — which is now fixed,
  with the remaining gaps (the R4 cross-run cache and prebuilt genome index) recorded with reasons rather
  than left silent.

- **`scripts/release_readiness.py` measures the v1.0 criteria instead of leaving them as prose.** `SPEC_V2.md`
  lists five conditions for cutting v1.0 and nothing checked any of them, so "how close are we" was answered
  by reading bullet points. Four are blocked outside the repository — which is exactly why measuring is worth
  it: it separates *blocked* from *forgotten*, and it will notice the day one stops being blocked. Current
  state: **1/5 met**; 1 of 12 artifact-backed model cards pins a checkpoint hash (5 further cards are
  heuristic baselines with nothing to pin, and are excluded from the denominator rather than counted as
  failures), 0 of 5 benchmark corpora are real, and the Zenodo DOI is minted on the first tagged release. It
  exits non-zero while any criterion is open and is now a step in `RELEASE.md`.

- **`aforge batch` offers the design options it was missing.** The cohort path — the run someone leaves going
  over a whole VCF, where a trained model or a PAM-flexible fallback matters most — could not select a
  trained model or a fallback **by any means**, config file included, while `aforge design` could.
  `--chemistry` and `--cell-context` were config-file-only there: honoured if you knew to write TOML,
  invisible from `--help`. All eight are now flags on `batch`, and a test requires every `design` option to
  exist on `batch` or be recorded with a reason (`--format`, `--out` and `--render-candidates` shape a single
  rendered document, which `batch` does not produce).

- **`--trained-prime`, and shell/library parity is now pinned.** `design()` is the one entry point behind all
  three audiences, and a parameter it accepts that a shell does not forward is a capability that exists and
  cannot be reached. Three instances: the PAM fallbacks (previous entry); the trained prime-efficiency model,
  which had no CLI flag while its Cas9 and base-editor siblings did — on the flagship chemistry; and
  `--allow-ng`/`--allow-spry`, which the previous entry added to the CLI and not to the web API. All three are
  closed, and a test now requires every `design()` parameter to be forwarded by each shell or recorded with
  the reason it is not (the web API's file-backed exclusions, for instance, are a deliberate refusal to accept
  client-supplied filesystem paths on a server).

- **`--allow-ng` and `--allow-spry`: the PAM-flexible fallbacks are reachable at last.** `enumerate_cas9`
  falls back to SpCas9-NG (`NG`) and SpRY (`NRN`/`NYN`) when no `NGG` guide is actionable, and `design_cas9`
  exposed both — but `design()`, which the CLI, the web API and the cohort path all use, did not, so no shell
  could ask for them. At a locus with no NGG in range the default run produces **0 candidates** and enabling
  both produces **190**. Off by default, deliberately: an NG guide is a different reagent with different
  specificity, so it is offered rather than assumed. An empty Cas9 vertical now also names the variants it
  did not try, which is the difference between a dead end and a next step.

- **Every field on the report models must now reach a renderer.** The recurring defect here is not a wrong
  number but a correct one nothing shows — `search_description()` dropped by the web envelope, the CFD
  citation left in a docstring, `sources_considered` needing separate wiring. `project.md` prescribes the
  guard ("a test that iterates `Model.model_fields` covers the fields that do not exist yet") and `Provenance`
  and `OffTargetReport` had one; the two models a reader actually reads did not, while two fields were added
  to `CandidateReport` in recent work with nothing to notice if either had been left unrendered. Both are
  currently clean. A new field that no renderer mentions now fails, unless recorded with a reason.

- **Each of the eight non-negotiable principles now has its evidence written down.** `test_stated_principles`
  checked three of them while reading as though it covered "the principles" — the same shape as the
  principle-8 gap it sat next to. It now parses the numbered list from `openspec/project.md` and requires
  every principle to name either the test that checks it or the reason it cannot be checked mechanically
  (principle 4, "wrap don't rebuild", is a judgement no assertion decides). A named test must actually exist.
  A ninth principle added to the list fails the suite until its evidence is recorded.

- **The frontend's "loads no third-party scripts" promise is now enforced.** The README, the deployment guide
  and the page itself all state it, and it is a privacy claim about a page a lab opens while pasting patient
  variants into it — a CDN font leaks the fact and timing of every visit, and a third-party script leaks
  whatever it likes. The claim holds today (every `src`, `<link href>` and `fetch` is a same-origin relative
  path) and was one `<script src="https://…">` from being false with nothing to notice. A scan now rejects
  any off-origin target in a position the browser fetches on its own; an `<a href>` the *user* clicks is
  still allowed, since a link is not a load. Verified against injected CDN script, stylesheet, `fetch`, and
  CSS `@import` references.

- **The "deliberately minimal core" claim is now a test.** `pip install alleleforge` really does pull eight
  transitive dependencies, none of them numpy, and `import alleleforge` really is ~85 ms — but nothing checked
  it, and a single top-level `import numpy` added anywhere in the `__init__` chain would break the core
  install outright on a machine that has no numpy, invisibly to a CI that installs every extra. A subprocess
  probe now asserts that importing the package loads none of the optional stacks.

- **The citation metadata is now checked against the package it ships with.** `CITATION.cff` and
  `.zenodo.json` restate the version, license, title, repository URL, authors, and keywords that live
  authoritatively in `_version.py` and `pyproject.toml` — and nothing checked any of it, so the next version
  bump would leave `CITATION.cff` naming a release that never existed and every citation of the software
  pointing at it. For a project whose stated purpose is reproducible open science that is not a cosmetic
  defect. The check found a live divergence on its first run: the two files listed different keywords
  (`.zenodo.json` had `benchmark`, which is right — the project ships CRISPR-Bench). `RELEASE.md`'s
  version-bump step now names the file too.

- **`openspec/project.md`'s conventions are current again.** The file distils the audit into durable rules
  and had stopped at R128, so a stretch of process lessons existed only inside individual round entries.
  Seven added: co-presented numbers must range over the same population; an aggregate can be a claim even
  when it is not a number; for an opt-in check the question is *who opted in*; a guard in a convenience
  wrapper is not a guard on the documented path; a duplicated exception is a duplicated `except`; an audit
  returning implausible results has two suspects and one is the audit; and audit the artifacts the audit
  produces. A test pins that every round a convention cites resolves to a log entry — which immediately
  caught a dangling `R117`.

- **The audit log is navigable again, and pinned.** `openspec/changes/README.md` ran ascending for rounds
  1–134 and then **descending** for 135–145, because each of those rounds prepended its entry ahead of the
  previous one — the log read chronologically and then reversed. Two round numbers (50, 71) had shipped work
  and were cited by later entries but had no section at all; both are now written from their commits and
  labeled as reconstructions. Round 117 turns out to be a skipped *number*, not lost work — R116's entry
  covers it — and that is now recorded where a reader following the citation looks. Tests pin ascending order
  and that every number in the range resolves to an entry or to a documented, still-accurate skip.

- **The changelog was an append-only log, not a changelog.** `[Unreleased]` had grown **77** change-type
  headings — 36 separate `### Fixed`, 32 `### Added` — because every change prepended its own instead of
  merging into the existing one, and nothing checked it. Consolidated to one section per type in Keep a
  Changelog's order, with all 300 bullets preserved verbatim (verified by diffing the bullet sets), and pinned
  by a test so it cannot drift back.

- **Every copy-pasteable `aforge` command in the prose is now checked against the real CLI.** One direction
  was pinned — every command appears somewhere in the docs — and not the other, so a renamed flag would turn
  a quickstart into a usage error with nothing to notice. All 25 documented commands currently resolve.

- **`SECURITY.md`.** A public repository that ships a web API, downloads pinned artifacts, and accepts signed
  leaderboard submissions from strangers had no stated way to report a vulnerability privately. Reports go
  through a GitHub private advisory — the same channel the code of conduct uses. It states what is in scope
  (untrusted-input parsing, the API and frontend, the artifact gates, generated leave-behinds), what is not
  (a wrong scientific prediction is a modeling issue, not a vulnerability), and the deployment facts an
  operator needs.

- **`aforge lift` — a build mismatch now has a remedy inside the tool.** `resolve` refuses a record whose
  native assembly disagrees with the requested build (relabeling a coordinate designs a guide at the wrong
  place in the genome) and told the caller to lift the coordinates first — naming an operation the CLI did
  not offer. `Liftover` was implemented, tested, and called by nothing in the library; `from_chain_file` had
  no callers outside its own tests. The new command takes loci in the same form `--region` accepts and emits
  them the same way, so its output pipes straight back in, and an unmappable locus prints `UNMAPPED` and
  exits non-zero rather than being silently dropped — a shorter region list searches less than was asked for.

- **Seven public names are now re-exported from their packages.** `alleleforge.design` did not export
  `PRIME_MAX_EDIT` or `PRIME_MAX_TEMPLATED_EDIT` — the two prime budgets `routing.__all__` declares public
  and the README cites by name — and `alleleforge.data` exported `ClinicalSignificance` but not the
  `ClinicalAssertion` that carries it. `alleleforge.report` gained `caveats`, `provenance_lines`,
  `model_limitation_lines` and `visible_candidates`, which is everything a caller needs to build a report
  view of their own; they were reachable only from `alleleforge.report.builder`.

  Two mechanical rules now hold this, so neither depends on anyone's taste about what "the API" is: a name
  in a submodule's `__all__` is a declaration the package must honor, and a dotted name the docs cite must
  resolve. The second catches a renamed or deleted name that a cross-reference still points at.

- **Eight modules reached the API reference for the first time**, including `design_many` — the cohort
  entry point, with its own README section and its own example notebook, absent from the reference since it
  was written. Also `alleleforge.config` (the `Settings` and network-consent surface), the cross-run caches,
  VCF ingestion, the model-checkpoint loader, the PRIDICT engine adapter, and the shared spacer-quality
  checks. The docs build passed throughout: mkdocstrings renders what it is pointed at and says nothing
  about what it is not.

  `tests/test_api_docs_cover_the_package.py` now fails when a public module has no `:::` directive and is
  not listed in `_NOT_IN_API_REFERENCE` with a reason — currently four entries, all documented as endpoints
  or commands rather than as functions. A second test rejects an exclusion naming a module that no longer
  exists, so the list cannot become a stale excuse.

- **A cohort row now says which safety sources it was actually screened against** (`offtarget_sources`, in
  the JSON row and the summary TSV). This is where a per-item difference hides: one variant screened against
  a haplotype panel and the next screened without it produce identical-looking rows, the candidate counts do
  not move, and the row is what a reader scans across hundreds of variants. It is also what made the bug
  above observable at all.

- **The "config file is honored" contract now has a test.** `_load_config` warns on an *unknown* key, which
  means a key inside the whitelist gets no warning — so a whitelisted key that no command reads would be
  accepted silently and do nothing, and the user's run would differ from the one their config describes. The
  comment beside the run-param handling names that exact failure; nothing checked it. Two tests now do: every
  whitelisted key is read somewhere in the CLI, and a config-only run produces the same candidates,
  rationale and provenance snapshot as the equivalent flags.

  All ten keys are honored today, `populations` included — a negative result worth recording, since it is
  the safety-relevant one.

- **An ambiguous spacer position now says that it biases the safety score downward.** A non-ACGT base in a
  spacer cannot be scored — the CFD matrix has no entry for it — so the aligner counts it as a mismatch and
  the site's score falls toward 0. On a safety axis that is exactly backwards: the true base is unknown and
  may match perfectly, so an ambiguous position should make a reader *less* confident and instead made the
  number look better. A degenerate spacer with an `N` at position 20 reported `worst score 0.000` on its own
  locus. It is recorded rather than refused — a degenerate spacer is a legitimate reagent, and the oligo
  layer says so explicitly — and `OffTargetReport` carries `ambiguous_spacer_positions`, with the search
  description naming the positions and stating the direction of the bias.

- **An ancestry requested for stratification that no supplied source carries data for is now named.**
  Asking to stratify by `sas` against a frequency file whose records carry only `afr` and `nfe` contributed
  nothing and was dropped in silence — while the provenance snapshot recorded `sas` among the populations
  considered, so the artifact asserted an ancestry had been examined when no data for it existed, and its
  absence from the breakdown read as *no risk in that population* rather than *no data*. On a tool whose
  differentiator is ancestry-stratified safety, that is the wrong silence. `OffTargetReport` records
  `unbacked_populations`, checked across every supplied source (a haplotype panel backs its own ancestries),
  and the search description names them. It stays empty when no source was supplied at all — that case has
  its own warning, and two warnings for one situation is worse than one.

- **A chromatin track that covers none of the candidate loci is now reported, and an adjusted candidate is
  flagged.** The per-candidate path was already careful — an uncovered locus produces no chromatin note, so
  the tool never claims evidence the track did not have. What was missing is the menu-level statement: a
  track supplied and named in provenance can cover nothing, leaving every efficiency the unadjusted estimate
  while the run reads as chromatin-aware. The menu now says so, and candidates the track actually moved
  carry a `chromatin-adjusted` flag — previously that fact existed only in prose inside the candidate
  rationale.

- **A safety source that is supplied but covers nothing in the searched region now says so.** The warning
  for a *missing* frequency source has existed for a while; a source that is **present and inert** produced
  nothing at all — and its report is byte-identical to a reference-only scan, empty ancestry breakdown
  included, while the user believes they supplied the data. A per-chromosome gnomAD download, a region
  subset, a haplotype panel for another locus, a patient VCF from a different sample: all land here, and
  this is the more dangerous case, because nothing is absent to prompt a second look.

  `OffTargetReport` carries `sources_considered`, a mapping from each **supplied** source to how many of its
  entries fell in the searched region. An absent key means "not supplied", `0` means "supplied and covered
  nothing here", and those are different statements. A mapping rather than a field per source deliberately:
  the sources are a growing set, and checking one while its siblings go unchecked is exactly how this gap
  arose.

  Two things checked and found sound, worth recording: **contig naming** (an Ensembl-style `11` gnomAD file
  against a UCSC `chr11` reference gives identical results — `canonical_contig` does its job), and
  **soft-masked reference sequence**, which a repeat-masked hg38 would otherwise have silently failed to
  match in exactly the regions where off-targets live.

- **An off-target report now says how much of the requested region could actually be searched.** A window
  holding an assembly gap or an IUPAC ambiguity code cannot be scanned, and the report looked identical
  either way: a scan over a contig that is **99% `N`** returned the same shape of answer as one over
  fully-resolved sequence. On a real genome that is the difference between "no off-targets" and "no
  off-targets in the 1% of your region that is sequenced" — and a region overlapping a centromere or a
  scaffold gap is not exotic. `OffTargetReport` records `searched_bases` and `resolved_bases`, and the search
  description appends *"only 1% of the 4,038 requested bases were searchable"* when the fraction is below
  99%. A fully-resolved reference says nothing, so the caveat is information rather than furniture. The count
  uses four `str.count` passes, so it costs nothing next to the scan that walks the same bytes.

- **`aforge bench compare` — the operation the reproducibility digest exists for, which had no
  implementation.** Every benchmark run computed a platform- and release-stable digest over its scientific
  body, stored it, and nothing ever read it back. Its docstring promises that two independent runs of the
  same model on the same frozen `(task, split)` match across releases and platforms; nothing could test that
  promise, and nothing recomputed the digest either — so a runner that computed it wrongly would have
  shipped a wrong digest in every result while the signature (which covers the digest as one more field)
  went on passing.

  `BenchmarkResult` gains `scientific_body()`, `verify_reproducibility_digest()` — the counterpart
  `verify_signature()` never had — and `agrees_with()`. The new command re-derives each result's digest from
  its own body, then reports whether the two are the same scientific result and, when they are not, **names
  the fields that differ** rather than leaving a user to diff JSON. Two runs at different wall clocks now
  demonstrably agree while their signatures differ, which is precisely the gap the digest was introduced to
  fill.

- `tests/test_examples_teach_the_contract.py` — the notebooks checked as documentation people copy: an
  example that renders `best_efficiency` must also render its interval, and none may default a summary
  value with `or`, which fires on the meaningful zeros (`0.0` efficiency, `0` candidates).

- **A truncated outcome table now says it is truncated.** A knock-out card read `P(intended) = 0.87` above
  three alleles of 0.069, 0.060 and 0.055 — a headline and a table that look like they contradict each other
  until you know the NHEJ spectrum has forty-six alleles and the table is showing three. The renders now
  add *"showing 3 of 46 predicted alleles (0.18 of the probability mass); the rest are in the lossless
  export"*, and `CandidateReport` carries `n_outcome_alleles` and `outcome_shown_mass`. The candidate list
  has said "Showing 50 of 470" since it was capped; the outcome table made the same omission and looked far
  more like an arithmetic error. A complete table says nothing.

- `tests/test_stated_principles.py` — the README's design principles checked as claims. It pins the
  citation-and-version guarantee over both registries and guards the specific "by default" overclaims,
  including an assertion that the honest wording is still present, so the test cannot be satisfied by
  deleting the claim rather than correcting it.

- **The flat TSV/Parquet export now carries what makes its own numbers readable** (export
  `schema_version` 2 → 3). It had `n_offtarget_sites` and nothing to interpret it with: not the aggregate
  specificity, not the scorer or weight matrix, not the search settings. Every one of those has been on the
  HTML page and the PDF leave-behind since it was added — and missing from the format something *automated*
  reads, which is where an uninterpreted number does the most damage, because a pipeline filtering on
  `n_offtarget_sites = 0` cannot tell a clean scan from a narrow one and never asks.

  New columns: `offtarget_specificity`, `offtarget_scorer`, `offtarget_matrix`, `offtarget_search`,
  `caveats` (the hazard subset of `flags`, so a pipeline can filter on "needs attention" without hard-coding
  a flag-name list that keeps growing), and `rationale` (the per-candidate score breakdown, previously
  human-renders-only).

- **An off-target site now records the PAM that anchored it.** Two things were undecidable from a report
  without it. A canonical `NGG` site and a low-stringency `NAG` one carry very different real risk and
  appeared identical on the table. And with bulges allowed the same 20 bp of genome is reachable from two
  *adjacent* PAMs, so a report showed what looked like one locus printed twice —
  `chr11:2019-2038(-)` and `chr11:2018-2038(-)`, both scoring 1.0. Recording the PAM settles it: `AGG` and
  `GGG`, one base apart, two genuinely distinct cut registers rather than a duplicate. `OffTargetSite`
  gains `pam_sequence`, the CLI prints `pam=AGG` on each row and in the JSON payload, and the web API
  carries it automatically with the report.

  Worth noting what did *not* change: nothing is merged and no aggregate is adjusted. Deciding that two
  overlapping registers should count as one site would be inventing a convention; recording the PAM lets
  the reader decide, which is the information they were missing.

- **A menu now says when its own ranking is not resolved by the evidence.** Measured on a realistic
  single-SNV correction: the top fifty pegRNAs spanned **0.027** of composite score while the leader's own
  efficiency interval was **0.30** wide — eleven times the entire spread — and **248 of 470** candidates
  were within the leader's uncertainty. The order was arithmetically exact and, past the first few places,
  meaningless, with nothing on the page saying so. A ranked list reads as a claim that #1 beats #12; here it
  was not one.

  `indistinguishable_leaders()` counts the leading group using a deliberately transparent rule rather than
  a statistical one, because a real test would need an error model the project does not have: the
  efficiency term contributes `w_efficiency × efficiency` to the composite, so the honest uncertainty in
  that single largest term is `w_efficiency × (upper − lower)`, and any composite gap smaller than that is
  inside the noise of its own biggest input. The rule can only ever report that candidates are
  *unseparated* — never that one is better — so being wrong makes the menu more cautious, not less.
  Nothing is reordered; the menu simply says *treat them as one group and choose on the reagent, not the
  rank*, and stays silent when the spread genuinely resolves.

- **A code of conduct, which the README and `CONTRIBUTING.md` had both promised and neither delivered.**
  Two public documents told contributors to read a Contributor Covenant behind a link that 404s — a
  governance claim with nothing behind it. `CODE_OF_CONDUCT.md` now adopts the Contributor Covenant 2.1 **by
  reference** to its canonical URL rather than reproducing it, so the file cannot drift from the version it
  names, and states the reporting channels that actually exist today (a private GitHub security advisory for
  anything sensitive, issues otherwise). Two calls in it are properly the maintainer's — adoption by
  reference versus verbatim text, and whether to publish a direct contact address — and have been flagged
  for review rather than decided quietly.

- **The prose is now checked mechanically for claims the repository cannot back.** Alongside the
  every-CLI-command check, `tests/test_readme_documents_the_cli.py` asserts that every local link in
  `README.md` and `docs/` resolves to a file that exists, and that every `alleleforge.x.y` module path the
  prose cites is importable. Documentation drift is invisible to a test suite by construction — the code
  keeps working while the sentences about it rot — so the checkable half is now checked. Paths the prose may
  legitimately cite before they exist go in an explicit allow-list with a reason, so it cannot quietly become
  a place to park a broken promise.

- **The leaderboard now shows how much of its output each model disclaimed.** The uncertainty contract
  makes every model declare which predictions are out of distribution, and `BenchmarkResult` records the
  count — and the board dropped it. A model that stood behind every prediction and one that flagged nine in
  ten of them as out-of-distribution and scored the same appeared on identical rows. ECE was already shown
  for exactly this reason; its sibling was left behind. Both renders gain an **OOD** column showing the
  share of the scored test fold (`87% (261/300)`), with `n/a` — not `0%` — when it is unmeasurable, the same
  distinction the board already draws for an undefined ECE: silence and a clean bill are different claims.

  Ranking is unchanged. The OOD share is reported, not scored: turning it into a ranking term would need a
  defensible exchange rate between accuracy and coverage, and inventing one would be a worse dishonesty
  than the omission it replaces.

- **The predicted molecular consequence now appears in the menu; it was computed and read by nothing.**
  Supplying an effect predictor made AlleleForge annotate the variant, store a full `VariantEffect` on
  `ResolvedVariant.effect` — gene, Sequence-Ontology consequence, VEP impact tier, HGVS c./p., transcript,
  canonical flag — and then use none of it. The user paid a network round trip for that, and since the
  lookup goes to a third-party API, an explicit decision to disclose their variant, and got no answer
  anywhere in the output. The menu rationale now leads with `Predicted effect: missense variant (moderate
  impact) in HBB, p.Glu7Val on ENST00000335295`, and says so when the transcript is not the canonical one —
  the same variant is missense on one transcript and intronic on another, so an unqualified consequence is
  half a statement. A correction targeting a variant with only **modifier** impact gets a note to confirm
  the intent; a correction with real predicted impact stays quiet, so the note carries information.
  Annotates only — a silent variant can still be a splice or regulatory target, and the predictor speaks
  for one transcript.

- **Model-card limitations now appear in the report; they were carried "for safety audit" and shown to
  nobody.** Two breaks in the same chain. `ModelCard.to_checkpoint()` — a hand-written field list — carried
  `known_failure_modes` into provenance and dropped `intended_use` and `out_of_scope_use`, so a result
  recorded *how* its models fail but not *what they were never meant to do*. And no human-facing render
  printed any of it, including the failure modes, whose docstring says they are carried so a consumer can
  audit a design "without re-opening the cards" — which still required re-opening the cards.

  The shipped `cas9-efficiency-ensemble` card, the default Cas9 efficiency scorer, states that trusting its
  point estimate as a trained activity prediction is out of scope because "the heads are an unfitted
  pseudo-random scaffold". Every report was silent on that. The HTML page and PDF leave-behind now carry a
  **Model limitations** section listing, per model, what it is not for and how it fails, from one shared
  `model_limitation_lines()` so the two renders cannot drift. A model documenting nothing produces no line
  and no section — an empty heading reads as "no known limits", which is the opposite of the truth.

  A regression test compares `to_checkpoint()` against the card over the two models' shared field *names*
  rather than naming fields, so a field added to both tomorrow is covered without editing the test.

- **A ClinVar accession's clinical significance now reaches the design menu; it used to be read and
  discarded.** `_from_clinvar` returned `record.variant` and nothing else, so the classification — the
  reason anyone picks an accession over coordinates — never left the resolver. A menu for a variant ClinVar
  calls **Benign** read exactly like a menu for a pathogenic one: the tool designed a "correction" for an
  allele the database says is harmless, and said nothing. (`docs/data.md` had ClinVar's role listed as
  "accession → normalized variant + clinical significance"; only the first half was true.)

  `ResolvedVariant` now carries a `ClinicalAssertion` — the normalized class, the raw review status, and
  the verbatim source token. The review status is carried alongside the class deliberately: "Pathogenic, no
  assertion criteria provided" and "Pathogenic, reviewed by expert panel" are the same class and very
  different evidence. The menu rationale — which every render already prints — leads with the assertion,
  and adds a note when the requested intent and the classification pull in different directions: correcting
  a benign variant, correcting a VUS, or installing a pathogenic allele (a disease model, not a therapy).
  These annotate; nothing is refused. A congruent design stays quiet, so the note carries information
  rather than appearing on everything.

  `ClinicalSignificance` moves to `alleleforge.types.variant` (still importable from `data.clinvar`) so the
  resolver can carry an assertion without depending on the data layer, which it deliberately reaches only
  through a Protocol. A ClinVar stub that supplies only coordinates still resolves — it simply asserts
  nothing.

- **The PE3 nick-to-nick distance is now shown, and a dangerously close nick is flagged.** `nick_offset`
  was computed by the enumerator, stored on `NickingGuide`, and read by nothing — not the reagent line, not
  the flags, not the ranking. It is *the* PE3 design parameter: two PE3 candidates differ in essentially
  nothing else, and two nicks placed close together on opposite strands are a staggered double-strand
  break, the outcome prime editing is chosen to avoid. Candidates now carry a signed
  `nick-distance:+62nt` flag, the reagent line reads `PE3 (+62 nt nick)`, and a nick closer than
  `CLOSE_NICK_NT` (30 nt) adds `close-nick`. The test fixture's only PE3 nick turned out to sit **4 nt**
  from the pegRNA nick — previously unremarked anywhere in the output.

  The distance deliberately does **not** enter ranking. Scoring it would need a byproduct model calibrated
  against real PE3 data, which AlleleForge does not have; the constant is labelled in the source as a
  conservative floor rather than a fitted threshold, and it has been flagged for verification against the
  primary literature.

- **The off-target cut-offs are now printed where the site count is, on every surface that shows one.**
  R84 put the mismatch budget, the DNA/RNA bulge budgets, and the CFD/MIT cut-offs on `OffTargetReport`;
  nothing rendered them, so an HTML page, a PDF leave-behind, the CLI's human line and its JSON payload all
  still showed "2 nominated site(s), specificity 0.82" as if those numbers were absolute. They are not:
  the same guide yields two sites at a 0.20 CFD cut-off and fifteen at 0.05, and the report a collaborator
  is handed is precisely where that has to be visible. `OffTargetReport.search_description()` states the
  settings in one line, `CandidateReport.offtarget_search` carries it (alongside the existing
  `offtarget_scorer` / `offtarget_matrix` labels, which exist for the same reason), and the HTML, PDF and
  CLI renders print it. The JSON payload gains a structured `search` object. The description is
  deliberately ASCII — the PDF's WinAnsi font has no glyph for a mathematical `<=` and would have printed
  `?3 mismatches` on the handed-out page.

- **An off-target report said how many mismatches it allowed, but not the four other knobs that decided
  what it found.** `OffTargetReport` carried `mismatch_threshold` — recorded, correctly, so that a site
  count could be read against the budget that produced it — and nothing about the DNA/RNA bulge budgets or
  the CFD/MIT reporting cut-offs, which narrow the result just as hard: the same guide yields two sites at
  a 0.20 CFD cut-off and fifteen at 0.05, and a zero-bulge scan cannot report the bulged hits a one-bulge
  scan finds. Two reports could disagree by an order of magnitude with nothing on either of them to explain
  it. The report now records `dna_bulge_budget`, `rna_bulge_budget`, `cfd_threshold` and `mit_threshold`
  beside the mismatch budget. This is the R83 rule — *any parameter that narrows what was examined must
  appear beside the result* — applied as a sweep rather than a one-off: the tell was five settings of the
  same kind with one recorded.

- **Region scoping is now available over HTTP too — I had mis-classified it as a file input.** The
  file-backed safety sources stay CLI-only for a real reason (a client-supplied path is a server-side
  file-read primitive), but a *region restriction* is data, not a path, and carries none of that risk.
  `POST /api/design` and `POST /api/offtarget` now take `offtarget_regions`. They accept a small `Region`
  shape that does **not** require a strand — a restriction covers both by construction — while still
  accepting a `locus` copied verbatim out of a previous response, whose extra `strand` and
  `coordinate_system` keys are ignored. An empty interval is a 422 rather than a silent scoping of the scan
  to nothing, which would report every guide spotless; an empty *list* means "search everything", not
  "search nowhere".

- **`design()` could not scope an off-target search at all, and now can — reachable as `--region` /
  `--regions-bed`.** Every *vertical* (`design_cas9`, `design_prime`, the base-editor path) accepts
  `offtarget_regions`, and `search()` takes `regions`. The unified `design()` entry point — the one the CLI
  and web API are thin shells over — accepted neither and passed nothing through, so a whole-genome scan
  could not be narrowed from anywhere except by calling a vertical directly. Over a real reference that
  scoping is the difference between a practical run and an impractical one. `design()` now takes
  `offtarget_regions` and threads it to all three verticals; the CLI exposes repeatable
  `--region chrom:start-end` and `--regions-bed panel.bed` on `design`, `batch` and `offtarget`. A
  malformed region is a usage error rather than a silent widening back to the whole genome, and an empty
  restriction stays `None` ("search everything") rather than becoming an empty list, which would restrict
  the search to nothing and report every guide spotless.

- **`--haplotypes` and `--patient-vcf` complete the safety inputs on the CLI.** The same reachability
  sweep that found `--gnomad` left two more: the *haplotype*-aware pass (the second half of the README's
  "population- **and haplotype**-aware" claim, which catches a site existing only on a co-inherited
  combination of alleles) and patient-specific personalization (a site present in *this* genome but not the
  reference). Both are now loadable — a phased-panel TSV and a VCF or variant list — on `design`, `batch`
  and `offtarget`. Patient variants are resolved against the reference, so an allele asserting a base the
  genome does not have fails loudly rather than silently personalizing the scan with a wrong-build variant.
  `HaplotypePanel` gained `__iter__`/`__len__`, since the engine consumes a flat iterable and a caller with
  a whole panel and no single interval to query had to reach into its buckets. Verified through the CLI:
  0 sites reference-only, then one `patient`-origin site with `--patient-vcf`, and one causally-attributed
  site with `--haplotypes`. **Also corrected an inaccuracy introduced one commit earlier:** the
  "reference-only" warning keyed on `--gnomad` alone, so a run supplying `--haplotypes` was told its scan
  was reference-only while the haplotype pass was actively finding sites. It now fires only when neither
  ancestry-bearing source is present, and a test parametrizes all three cases.

- **The README's CLI examples advertised population-awareness they could not deliver.** `aforge design
  ... --populations afr,eur,eas` was captioned "ranked, safety-annotated menu", and the `offtarget` example
  listed "the carrying MAF" among the tunable engine knobs — while `--maf` filters population alleles that,
  with no way to load any, were never there. Both examples now pass `--gnomad`, and the `design` one also
  shows `--cell-context`; the batch example notes that an empty `worst_offtarget` column means "not
  measured", not "clean".

- **`--gnomad` on `design`, `batch`, and `offtarget`: the population-aware off-target search is reachable
  from the CLI for the first time.** This is the capability the project is built around — the README calls
  reference-only off-target "a known safety gap" and cites the Casgevy / BCL11A `rs114518452` case — and
  `design()` and `search()` have always taken a `gnomad=` database. **No CLI command could supply one.**
  `--populations` names ancestry *labels* to stratify by; it carries no alleles. So every command-line scan
  was reference-only, and a user passing `--populations afr,eur` got an empty ancestry breakdown back with
  nothing saying why — silence that reads as "no ancestry-specific risk found" rather than "nothing was
  searched". The three commands now take `--gnomad <sites.tsv[.gz]>` (`#chrom pos ref alt af <pop>...`,
  1-based `pos` as in a VCF), warn explicitly when ancestries are requested without one, and exit with a
  data error on an unreadable path rather than falling back to a reference-only scan the caller believes is
  population-aware. Verified by reproducing the reference-bias case end to end through the CLI: 0 sites
  reference-only, then one `population`-origin site at score 1.0 whose risk is concentrated in African
  ancestry (`afr` 0.105 vs `nfe` 0.001).

- **`cell_context` — the input that raises the OOD flag — is now settable from the CLI and the web API.**
  It was reachable only through a CLI *config file*, and not at all from the web API, whose `DesignRequest`
  had no such field. So every design the web API returned reported `in_distribution: true` whatever cell
  line the user was actually targeting — the exact opposite of what the flag exists for, on the surface most
  likely to be used casually. `aforge design --cell-context HepG2` (overriding the config key, matching the
  other options' precedence) and the API's `cell_context` field now set it. Verified end to end: with no
  context or with `HEK293T`/`K562` the prediction stays in-distribution; with `HepG2` it flips to
  `in_distribution: false` and the candidate carries `ood`. Found by asking which `design()` capabilities
  the shells cannot reach — the query the previous entry's lesson suggested.

- **The report render cap is now reachable from the CLI and the web API.** `render_html` / `render_pdf`
  have taken `max_candidates` since the cap was introduced, but neither surface exposed it — so a user who
  wanted the full 720-candidate page had no way to ask for it, and the parameter was library-only. `aforge
  design --render-candidates N` and the API's `render_candidates` field now set it, with `0` spelling "draw
  them all" (the command line has no natural way to write `None`, and a zero-candidate render is not
  something anyone wants). Both surfaces were done together rather than one now and one later — the same
  fix reaching one shell and not the other is how the `specificity` labeling ended up inconsistent for five
  rounds. Tests pin, on both surfaces, that the cap changes the HTML and **never** the lossless export.

- **Every pegRNA 3' motif is now round-tripped through the oligo output; `mpknot` previously reached no
  test and no caller.** `MOTIF_SEQUENCES` ships three options, but the enumerator only ever emits
  `tevopreQ1`, so `ThreePrimeMotif.MPKNOT` was a sequence that goes into a **synthesized** extension oligo
  with nothing exercising it. The oligo module's cardinal invariant is that the oligos reconstruct the
  declared RTT and PBS, and `reconstruct()` strips the declared motif off the 3' end first — so a motif it
  mishandled would either corrupt that boundary or silently ship the wrong bases. All three motifs are now
  parametrized through `pegrna_oligos` → `reconstruct()`, with checks that the declared motif's bases are
  actually present in the ordered sense oligo, are concrete `ACGT`, and that no two motifs produce the same
  oligo. Found by asking which enum members no test names — the same query that surfaced `REVERT` above.
  **Not** verified: that the two motif *sequences* match the publication they cite. Both are 46 nt and share
  a 9-nt prefix, which may be correct; confirming a published sequence needs the source, so it is flagged
  for a human rather than guessed at.

- **`REVERT` — a CLI-exposed edit intent — had no test coverage at all, and no documentation of what it
  means.** It reaches five *independent* `intent in (CORRECT, REVERT)` checks: routing, all three
  enumerators, and the HDR donor. Nothing centralizes that, so a sixth branch added later that forgot
  `REVERT` would silently fall through to the `INSTALL` behavior — writing the **alternate** allele where
  the user asked for the reference. A wrong reagent from a one-word omission, on a path nothing exercised.
  `EditIntent` now documents all four intents, including why `REVERT` exists (mechanically identical to
  `CORRECT`; it records in provenance *why* the edit was made — repairing a pathogenic allele versus
  returning an engineered line to wild type). A new suite pins the equivalence at every layer — routing,
  carried allele, each enumerator, the donor, both design verticals, and `design()` — and each assertion is
  paired with a check that `CORRECT` and `INSTALL` genuinely *differ* at that locus, so the equivalence
  cannot pass vacuously. Mutation-checked: dropping `REVERT` from the prime enumerator or from routing
  fails it.

- **The prime byproduct model now has a card, so the flagship's provenance names both its models — and
  `design()` can finally be given prime overrides.** Two gaps, found by running `aforge verify` and
  noticing it reported **1 model** for a prime design:
  - `PrimeOutcomePredictor` had no model card, and `prime_model_checkpoints()` documented this as "a
    card-free heuristic, so it contributes no checkpoint". Its siblings do not work that way:
    `indelphi-mh-baseline` (nuclease) and `be-dict-baseline` (base editing) each carry one. So the
    *flagship* was the single chemistry whose outcome model went unrecorded — the model whose
    `p_intended` feeds the menu's cleanliness objective directly. A `prime-outcome-baseline` card now
    records its version, citation, and three known failure modes (geometry-keyed only; no sequence
    context, cell type, or edit-size term; three modeled byproduct channels, not an exhaustive account).
  - `prime_model_checkpoints()` took no arguments while `cas9_model_checkpoints(scorer, predictor)` and
    `base_editor_model_checkpoints(predictor)` took the overrides — because `design()` exposed no prime
    overrides at all, so a caller could substitute a scorer for the nuclease and for base editing but not
    for the flagship. `design()` now accepts `prime_efficiency_scorer` / `prime_outcome_predictor` and
    records the override's card instead of the default's, matching the other two verticals. **What this
    does not do** is make a trained model reachable: there is no drop-in trained per-pegRNA prime scorer
    today. `PridictEngineAdapter` is the real PRIDICT2.0 path but a *sequence-level* `design()` API rather
    than a `score(pegrna, ...)` one, and `DeepPrimeAdapter` / `GenETAdapter` implement the scorer protocol
    only to refuse — documented placeholders, because DeepPrime's per-pegRNA API needs edit metadata a
    `PegRNA` does not carry. That remains an R1 gap. The reproducibility golden moved by exactly one added
    model, verified by diffing the canonical run's body; no number changed.

- **`POST /api/offtarget` gained the same on-target handling as the CLI.** The previous entry fixed the CLI
  and left the web API reporting the identical unlabelled `specificity` — the envelope's own docstring
  promises "the same summary the `aforge offtarget` CLI surfaces", which had quietly stopped being true.
  The request now takes `on_target` **as a `GenomicInterval`**, the same shape a reported site's `locus`
  has, so a client can copy one straight back; the response carries `on_target_excluded`; a malformed
  locus is a 422. (The string form was tried first and was wrong: the API emits loci as objects and never
  as `chrom:start-end(strand)`, so a field accepting only the string would have taken a spelling the API
  itself never produces — caught by driving the round trip.) The locus parser the CLI uses is now
  `GenomicInterval.parse`, the exact inverse of `__str__`, so the two surfaces cannot drift into accepting
  different spellings.

- **`aforge offtarget` gained `--on-target`, and says when it is missing.** The standalone command passed
  no on-target locus, so the guide's own perfect match was reported like any other site: the worst score
  pegged at `1.0` and specificity capped at `0.5` for even a spotless guide — the failure mode the engine's
  own `_is_on_target` docstring warns about, on the one call site that could not opt in. Reporting every
  perfect match *is* the honest answer when the tool has not been told which one is intended, so the fix is
  not to guess: `--on-target 'chrom:start-end(strand)'` excludes it when the caller knows, and when they do
  not, the output now states `[on-target locus NOT excluded]` and the JSON carries
  `on_target_excluded: false`. Without that, the same word — "specificity" — named two different quantities
  in the CLI and in a design report. A malformed locus is a usage error, never a silently skipped
  exclusion. Found by running the command.

- **An acceptance test carries a large precise edit from variant to orderable reagent**, and the README's
  SpCas9 section now describes the shipped behavior rather than a dotted side-branch. Correcting a 41-base
  restoration is beyond every break-free chemistry; it must not return a blank menu, and it must not return
  a bare double-strand break dressed as a correction. The test asserts the whole chain connects — routing
  admits only the nuclease, the top candidate carries a gap-free donor and its `hdr-donor:*` /
  `outcome-is-nhej-spectrum` flags, the reagent line names the pair, and the donor is emitted as an
  orderable `hdr-donor-ssodn` beside the guide duplex and reaches the rendered HTML. Each hop had a unit
  test; nothing asserted they joined up.

- **A precise nuclease candidate is now *orderable*: the HDR donor is emitted as a template to synthesize,
  alongside the sgRNA duplex.** `oligos_for` returned only the guide duplex — the half of the reagent that
  cannot make the edit. A new `DonorOligo` (`kind="hdr-donor-ssodn"`) carries the sequence to order and the
  repaired product's re-cut disposition; it rides on `SgRnaOligos.donor`, and its hazards are promoted into
  the same prominent warnings list the guide's use rather than buried in the JSON block. Two hazards are
  flagged: a donor longer than the ~200 nt most vendors synthesize as one oligo (order it as a dsDNA
  fragment or plasmid instead — a 300 nt "oligo" should not reach a shopping cart unremarked), and a
  repaired product that is still a substrate for its own guide.

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

### Changed

- **`aforge batch` exits non-zero when any item failed.** Per-item isolation is the feature — every item runs,
  the manifest stays complete, one bad variant does not abandon the other four hundred — but reporting
  *success* for a run that failed items is not part of it. A 500-item run where 200 errored exited 0, so a
  script or CI job had no way to tell without re-parsing the summary, while `verify`, `bench compare` and
  `scripts/reproduce.py` all signal through the exit code. The run still completes and the manifest is
  intact; only the exit code changed.

- **Flat export schema 3 → 4:** adds an `offtarget_scorer_citation` column.

- **The reproducibility gate now says what drifted.** `scripts/reproduce.py` is a blocking `make ci` job, and
  on failure it printed the golden hash, the current hash, and nothing else — leaving a developer to bisect
  by hand for a difference the script was holding both sides of. The golden manifest now stores the
  canonical body alongside its digest (8 KB, 200 lines), so drift is a readable diff in review, and the gate
  walks the two bodies and names the values that moved:
  `candidates[0].efficiency: 0.5 -> 0.7`. The script also gained tests; it previously had none.

- **`BenchmarkResult` schema version 4:** `n_out_of_distribution` moves into the scientific body, so it is
  covered by the reproducibility digest. A result produced under an earlier version keeps a digest that will
  not re-derive; the bumped `schema_version` is how a consumer detects that rather than misreading it.

- **The cohort summary no longer reports a bare efficiency.** "Every numeric prediction carries a calibrated
  interval, never a bare float" is the project's stated principle, and the one surface built for scanning
  *hundreds* of variants printed `eff=0.61` and nothing else — so a confident prediction and an
  out-of-distribution guess looked identical at exactly the moment nobody is reading the detail. The
  human line now reads `eff=0.61 [0.46,0.76]`, marks `OOD` when the prediction is out of distribution, and
  appends the recommended candidate's hazards (`!close-nick`). The machine-readable row and TSV gain
  `best_efficiency_low`, `best_efficiency_high`, `best_efficiency_in_distribution` and `best_caveats`; an
  empty menu still reports `None`, never a reassuring zero.

- **A candidate's hazard flags are now separated from its decorative ones, each with the reason it
  matters.** Found by running a realistic correction end to end and reading the page: the **top-ranked,
  Pareto-front** pegRNA carried `close-nick` — its two nicks 8 nt apart, which is a staggered double-strand
  break, the outcome prime editing is chosen to avoid — printed inside a comma-separated `flags:` line with
  exactly the weight of `epegRNA:tevopreQ1` and `both-nicks-searched`. The oligo *warnings* have had a
  prominent channel since the donor work; a candidate's own hazards did not.

  `CAVEAT_FLAGS` maps each hazard to a one-line explanation — an out-of-distribution efficiency prediction,
  a close nick, out-of-band spacer GC, a re-cuttable HDR donor, an NHEJ-spectrum outcome, bystander bases
  in the window, a population-only off-target, a relaxed PAM, an ambiguous locus, an internal cloning-enzyme
  site — and the HTML and PDF renders give each its own line before the flat list. `flags` still carries
  everything: separated, not filtered.

  A test reads every `flags.append(...)` literal out of the source and fails if any flag is classified as
  neither a hazard nor a description, so a new flag has to be decided rather than defaulting to harmless —
  the direction that loses a hazard, which is how `close-nick` came to be rendered as decoration two rounds
  after it was added.

- **README brought current with twelve rounds of behavior change**, each of which had shipped without the
  prose catching up: the two kinds of consent and why they are not interchangeable, the clinical and
  predicted-effect notes that now lead a menu, the settings and model limitations every render carries, the
  PE3 nick distance, the HDR donor's blocking mutation, and the leaderboard's OOD column.

- **A "re-cut blocked" HDR donor carries a second, unrequested edit into the genome, and now says so on the
  order.** The blocking mutation is the mechanism that makes the block work: an extra base substituted in
  the guide's PAM or seed so the repaired allele is no longer a substrate. It is written into the patient's
  genome permanently, and whether it is silent depends on a reading frame AlleleForge does not know — the
  enumerator already says "confirm it is synonymous in your reading frame". That sentence lived only in
  `HDRDonor.note`, which every render buries inside the collapsed oligo JSON. The result was backwards: the
  *failing* case (no block available, correction re-cuttable) got a prominent warning, while the
  *succeeding* case's consequence was invisible. `donor_oligo()` now emits it as a warning — the same
  channel the too-long-for-one-oligo and re-cuttable hazards use — naming the position, the base change,
  the region, and the check to perform before ordering. Verified end to end: it appears as its own line in
  both the HTML page and the PDF leave-behind.

- **Both human-facing renders — HTML and PDF — now draw the top 50 candidates plus the whole Pareto
  front, instead of every candidate.** A single prime design routinely yields several hundred candidates — every PBS x
  RTT-homology x PAM combination is a distinct pegRNA — so the "self-contained" page was **2.3 MB** for one
  variant (720 candidates), slow to open and mostly a tail nobody reads. `render_html` and `render_pdf`
  both take `max_candidates` (default 50, `None` for all) and share one selection helper
  (`report.builder.visible_candidates`) so they cannot drift apart on the guarantee below. The same report
  now renders in **181 KB** of HTML (12.7x smaller) and **74 KB** of PDF (down from 1.1 MB, 14.6x).
  Two obligations come with capping and both are enforced by tests: the page states how many candidates
  exist, how many are shown, and that the rest are in the lossless JSON/CSV export (which the cap does not
  touch); and **every Pareto-front candidate is rendered whatever its rank**, because the front is the
  report's entire answer to "I weight the objectives differently from your defaults" — a candidate optimal
  on safety but 200th on the composite score is exactly the one such a reader came for, and a display cap
  must not be allowed to decide it away.

- **The k-mer seed prefilter's documented speedup was re-measured and is now ~1x; the claim is corrected
  rather than left standing.** `MIN_SELECTIVE_K = 5` carried a calibration note — "k>=5 gives a ~2-4x
  speedup" — and the README repeated it. Both were true when written. They are not true now: the two
  preceding entries made the per-anchor work the prefilter prunes roughly 50x cheaper, so the prefilter's
  own `O(n)` cost (building seed positions plus the covered-index prefix sum) cancels what it saves.
  Re-measured across six mismatch/bulge configurations with five repeats each: **0.94-1.12x — neutral
  within noise — with hit sets identical in every configuration.** The kernel's own lookup is still
  ~5-7x native-over-Python, which is a different number and remains accurate. The prefilter is kept, and
  the threshold unchanged: it is exact and costs nothing measurable, and making it pay again would mean
  attacking the prefix-sum construction, not the constant. An optimization elsewhere silently invalidated
  a benchmark citation two modules away, and a stale speedup claim in a README is a claim a user can plan
  around.

- **The off-target scan prunes two more ways, for a further ~2.5x on top of the previous round.** With the
  quadratic alignment gone, a re-profile put the remaining time in two places, both fixed exactly:
  - **The bulge alignment now bails out of each pass as soon as it exceeds the budget.** Both the prefix and
    the suffix mismatch counts are monotone in their direction, so once either passes `max_mm` no further
    removal position on that side can qualify. If the two feasible ranges do not overlap the answer is
    `None` with no further work. On a random 20-mer window at the default budget that decides the window in
    roughly a dozen comparisons instead of forty.
  - **The per-window PAM test is memoized within a scan.** `PAM.matches` was called once per anchor per
    strand — ~400,000 times for a 200 kb contig — re-walking the IUPAC codes base by base, with a
    `str.upper()` and two dict lookups each. Windows come from the sanitized `ACGTN` alphabet, so the
    distinct ones are few (`5**pam_len`) while the anchors are many; each distinct window is now decided
    once.

  Measured back-to-back on one machine, two interleaved passes, query held fixed, two workloads: the
  original ≈6s, the previous round ≈1.2s, and now ≈0.3-0.5s — **>10x cumulative**, with this round
  contributing ~2.5x. (Absolute timings on this machine drift by a factor of two between runs, so only the
  interleaved A/B ordering is quoted.) Output is unchanged: the differential test against the naive oracle
  runs 25,000 randomized inputs per run, spanning budgets 0-10 and lengths 0-24 so both the
  bail-immediately and never-bail regimes are covered, with zero mismatches; a one-off 400,000-input sweep
  during development was also clean.

- **The off-target scan's innermost alignment is now linear instead of quadratic — a 4.2-4.6x speedup on the
  whole scan, with byte-identical output.** `_best_with_removed_base` prices every single-base-removal
  alignment of a bulged window, and it runs **twice for every PAM-positive anchor in the search space** — the
  hottest function in the safety-critical off-target engine. It rebuilt the reduced string and fully
  re-compared it once per removal position: `O(n²)` character comparisons plus `n` string allocations per
  call. A profile of a 150 kb scan put 85% of wall-clock inside it. Removing base `r` leaves the first `r`
  comparisons untouched and shifts every later one by exactly one position, so the mismatch count splits
  into a prefix sum and a suffix sum; two linear passes now price every removal and the reduced string is
  built once, for the winner. Measured on the full scan with the query held fixed and three repeats, on two
  independent workloads: **3.29s → 0.72s (4.6x)** and **2.21s → 0.52s (4.2x)**, output identical in both.
  The project's own test suite runs in **59s instead of 299s** as a result. Equivalence is pinned by a new
  differential test against the naive implementation kept verbatim as the oracle (4,000 randomized inputs
  over `ACGTN` plus the degenerate and tie-breaking edges); the tie rule — keep the earliest removal
  position — is preserved exactly, because that position determines the reported alignment.

- **`scripts/native_speedup.py` now also reports FM-index vs linear anchor enumeration.** R6 requires a
  recorded speedup for the native kernels on their hot paths. The new section measures the two anchor
  enumeration paths against each other on the same contig. It is reported as a measurement to track, **not**
  as a claim: across runs the ratio landed on both sides of 1.0 at the same contig size, because the
  dominant cost is how many in-budget hits a particular query has rather than the contig length. The script
  says so explicitly so no one quotes a speedup from a single run.

- **CI now gates the Rust crate.** A new `rust` job runs `cargo fmt --check`,
  `cargo clippy --lib -D warnings`, and `maturin build --release`, so the native
  toolchain (and its pinned, security-patched PyO3) is exercised on every push —
  closing the "Rust" leg of the v0.1.0 definition-of-done CI matrix and catching
  future dependency drift automatically.

### Fixed

- **A job's `progress` looked like a completion fraction and is not one.** It takes exactly three values —
  `0.0` queued, `0.1` running, `1.0` finished — and the status endpoint returned a bare `dict`, so it reached
  clients with no description at all and no OpenAPI schema. A client rendering it as a percentage shows 10%
  for the entire duration of a cohort run and then jumps to 100%, which is a worse lie than showing nothing.
  The endpoint is now typed, and the field says outright that it is a state, not a fraction.

- **Three model cards reported an unmeasured accuracy as `0.0`.** `spearman_validation: 0.0` sat on the
  Rule Set 3, PRIDICT2-baseline and Cas9-ensemble cards, with the reason in a YAML comment no consumer reads
  — *"populated when CRISPR-Bench scores it"*, *"not fitted/scored"*. `card.metrics` handed back
  `{'spearman_validation': 0.0}`, so anything reading a card saw a model claiming **zero** rank correlation
  with the truth: the floor of the scale, and for a correlation the damning extreme rather than the
  reassuring one. On the trained Rule Set 3 card that asserted a published model has no predictive value.
  This project states the principle in its own cohort code — defaulting an unmeasured axis to a number makes
  "we did not look" indistinguishable from a measurement. The key is now absent, the Rule Set 3 card says
  plainly that AlleleForge has not independently scored it, and a test rejects any performance metric of
  exactly 0.0.

- **`P(intended)` had no caveat at any value.** It is the number a reader is actually deciding on — of
  everything this reagent produces, how much is the edit that was asked for — and a real report printed
  `P(intended) = 0.05` beside an outcome table whose most likely row was a bystander-only edit at 0.288, with
  the CAVEATS block silent. Candidates now carry `intended-not-modal:<p>` when the single most likely outcome
  is not the requested edit. Deliberately **not** a threshold: "low" needs a number nobody can defend, while
  "something else is more likely than what you asked for" is a comparison the data already makes.

- **A guide with a perfect-match off-target elsewhere in the genome carried no caveat.** The number was
  always there — a report prints `off-target sites: 2 (specificity 0.376)` — but the CAVEATS block, which is
  what a reader scans for *what should worry me*, listed spacer GC and bystander bases and said nothing about
  a nominated site scoring **1.000**. The only off-target caveats were "not searched" and "population
  specific"; a searched candidate with a plausible cut somewhere else got a lower ranking score and no label.
  It still comes back `recommended` when it is the only candidate, which is when the caveat matters most.
  Candidates now carry `offtarget-high:<score>` above a stated triage band, with the score in the flag so a
  reader judges rather than trusting the band.

  The three verticals had also drifted: cas9 and the base editor flagged `population-offtarget` and prime did
  not — because prime's flag builder was passed a *boolean* rather than the report, so the information never
  reached it. All three now derive these from one shared helper, pinned by a test.

- **The CLI reported a defect as a missing package.** Two handlers caught `RuntimeError` to mean "an optional
  dependency is absent" — one for the patient-VCF reader, one around the whole cohort run — so a genuine bug
  in the reader or in `design_many` was reported as an installation problem, telling the user to install
  something they already had. Both are narrowed to `MissingDependencyError`. The previous entry converted six
  such raise sites and missed three outside `scoring/` (the VCF reader, the Cas-OFFinder adapter, the Parquet
  export); those are converted too, and a test now rejects any bare `raise RuntimeError` whose message is
  about an absent dependency — the check that would have caught the miss.

- **A genuine defect in a chemistry vertical was reported as "skipped".** `_EXPECTED_DESIGN_FAILURES` exists
  so "this chemistry produced no design" and "this code has a bug" read differently — its own comment says a
  real bug must not be "silently swallowed behind an 'eligible but empty' note". `RuntimeError` was on the
  list, which is the commonest way a Python defect reaches a boundary, so a crash in a vertical got the same
  word as a chemistry that simply did not apply. It was there for a reason — the consent, license and
  missing-dependency signals are all `RuntimeError` subclasses — so they are now named individually, with a
  new `alleleforge.errors.MissingDependencyError` for the "requires the optional X extra" sites. Deliberately
  excluded: `CacheIntegrityError` and `FMIndexIntegrityError`, which mean corruption or tampering; degrading
  those to "skipped" would undo the fail-closed gates that exist to surface them.

- **A cohort item that designed nothing said `ok` and nothing else.** The single-variant path explains an
  empty result in full — which chemistries were routed out, which rejected every protospacer and why — and
  the cohort summary dropped all of it, leaving a row reading `ok` with every column blank. A cohort is the
  one surface where a reader *cannot* re-run the item by hand to find out: there are five hundred rows and
  forty of them say `ok, n=0`. The summary, the manifest and the TSV now carry `no_candidate_reason`, and the
  human line prints it.

- **Selecting the MIT scorer failed with a message about the wrong thing.** The MIT score is defined only for
  an ungapped 20-nt alignment, and a bulge changes the length — so MIT with the default bulge budget died
  partway through the search with *"MIT score requires 20-nt spacers"*, while the user's spacer was a
  perfectly valid 20 nt and the bulge budget was the cause. The combination is now refused before the scan
  with the flags that fix it, and the underlying error names the alignment rather than the input. Found
  immediately on exposing `--scorer`.

- **The readiness report graded R2 on half its criterion.** Shipped one round earlier, it checked "on their
  hot paths with parity tests" and printed MET without checking "**and a recorded speedup**". The verdict
  happens to be right — `scripts/native_speedup.py` exists and the README cites it — but it was reached on
  half the evidence, which is the failure mode the report exists to prevent. Both halves are now graded, and
  a test requires each criterion's summary to name every conjunct its `SPEC_V2.md` bullet does.

- **The base-editor vertical explains an empty result too, and its reasons matter more.** Base editing's
  failure modes have sharply different remedies, and one of them is a fact about the *edit* rather than the
  locus: *no deaminase in the panel writes this substitution*. The others — the target base outside every
  activity window, no PAM in range, the base not being the editor's substrate on that strand — each send a
  reader somewhere different. The shared rejection accounting now lives in one module so the three
  enumerators cannot drift into three spellings of the same sentence, and a test pins that every label a
  `note(...)` call uses has a user-facing sentence behind it (the renderer drops unknown labels silently,
  which is what makes that guard necessary).

- **An empty prime vertical now says why.** Prime is the flagship chemistry and the one most often
  eligible-but-empty — a nick has to land within RTT reach of the edit, and no PAM in range may manage it —
  and the report said only *"prime: eligible but no actionable candidate enumerated"*. The reasons have
  different remedies (the other strand, a different PAM, another chemistry, or a genuine dead end) and naming
  none of them leaves a scientist with a result they cannot act on and cannot tell from a bug. The enumerator
  now tallies why each protospacer was rejected, and the rationale reads: *"…no actionable candidate
  enumerated — the nick-to-edit distance plus the edit and its 3' homology needs an RTT outside the
  synthesizable range (360); no PAM match at this offset (243); the edit lies 5' of the nick, which an RTT
  extending 3' cannot reach (8)"*. The tally is opt-in and costs nothing when omitted.

- **The outcome table could omit the one allele the user asked for.** `outcome_top` was the top N by
  probability, and a base editor with bystanders routinely ranks the intended edit outside the top few. A
  real run on a three-A window showed `A6G` (0.288), `A5G;A6G` (0.192) and `wildtype` (0.192) — with the
  **requested** `A4G` seventh of eight at 0.048. So the table that answers "what happens to my cells"
  contained no intended row at all, and its caption said only that the rest were in the lossless export. The
  intended allele now always survives the cap, exactly as Pareto-front members survive the candidate cap, and
  the shown-mass arithmetic follows the rows actually shown.

- **The off-target score, the project's differentiator, travelled without its citation.** Principle 8 is
  "cite everything … in code **and in output provenance**". Datasets and model cards were covered and tested;
  scoring functions were not. A report named its scorer `CFD` and its weights `doench-2016-cfd` and carried
  no reference — the published citations for CFD (Doench 2016) and MIT (Hsu 2013) lived only in a module
  docstring — while the heuristic efficiency and outcome models each shipped one through their registry
  cards. The off-target number is the one a reviewer is most likely to ask the provenance of. Reports, the
  HTML and PDF renders, and the flat export now carry `offtarget_scorer_citation`.

- **"CI stays weight-free" was a convention, not a mechanism.** It is a non-negotiable design principle, and
  the `real_weights` marker's own description claimed the marker enforced it ("opt-in, skipped in CI") — but
  CI runs a bare `pytest` with no `-m "not real_weights"`, and what actually kept the weights out was that
  each of the four such tests opened with its own hand-written `pytest.skip`. Four correct guards and no
  mechanism: a fifth that forgot would download real model weights in a CI job. The root `conftest.py` now
  skips `real_weights` and `live_integration` tests unless their opt-in variable is set, so the marker
  descriptions are true. CI behaviour is unchanged; `native` is deliberately untouched, since it has its own
  job selecting it with `-m native`.

- **`pip install "alleleforge[cli]"` then `aforge design` ended in a traceback.** That is a documented
  install — the deployment guide lists the CLI and the genome stack as separate rows — so the first command
  a new user runs raised `ModuleNotFoundError: No module named 'pyfaidx'`. The CLI defers its heavy imports,
  but the modules those pull in import *their* dependencies at module level, so the failure happens before
  any of the explicit checks that already answer this well. `design`, `batch`, and `offtarget` now report
  `error: this command needs the optional dependency pyfaidx, which is not installed: pip install
  'alleleforge[genome]'` and exit non-zero. Found by building the wheel, installing it into a clean venv, and
  running the quickstart; the suite had only ever run from `src/` with every extra present.

- **The disk cache's integrity gate was implemented and nothing switched it on.** `ContentAddressedCache`
  defaults to `verify=False`, and the persistent embedding cache — the only cache constructed anywhere in the
  library — took the default, so `verify=True` appeared solely in the cache's own tests: the checksum
  sidecar, the fail-closed read, the careful publish ordering all ran in CI and never in the product. That is
  the wrong default here in particular: a corrupted embedding does not fail, it produces a plausible vector,
  which becomes an efficiency score, which is what a guide is ranked on — and the check costs a SHA-256 over
  a few kilobytes against the transformer forward pass it exists to avoid. The embedding namespace also gains
  a version segment, so a warm cache written before the sidecar existed goes unreferenced rather than raising
  integrity errors on valid data.

- **Seven exception classes wore two names, so `except` on an artifact gate caught a third of it.**
  `ChecksumError` was defined independently in the model zoo, the genome reference, and the data registry;
  `ConsentError` in those three plus the VEP adapter — and each was exported under that name from its public
  package. A caller writing `from alleleforge.genome import ChecksumError` and guarding a design run with it
  caught reference-checksum failures and silently missed the model-checkpoint and dataset ones, which escaped
  as unrelated-looking `RuntimeError`s, while the scorers' docstrings promised "ConsentError / LicenseError /
  ChecksumError from the weight gate" as though each named one type. Both now live in
  `alleleforge.errors` and every module re-exports them, so existing imports keep working and `isinstance`
  finally agrees. "Nothing may be downloaded without my say-so" is one policy, not four.

- **`bench compare` called two very different results "the same scientific result."** `n_test` was in the
  scientific body the reproducibility digest covers and `n_out_of_distribution` was not, which split one
  ratio across the honesty boundary — denominator covered, numerator not. Two runs of one model on one split,
  one standing behind all ten predictions and one disclaiming nine of them, produced the *same* digest, and
  `aforge bench compare` printed *"agree: the same scientific result"* and exited 0. The leaderboard already
  treats this quantity as ranking-relevant — a board without it "puts two very different models on the same
  row" — so it belongs in the claim, not in the volatile provenance. Compare now reports
  `DIFFER … n_out_of_distribution: 0 != 9`.


- **The web API returned a spotless-looking off-target result for a search that ran on nothing.**
  `OffTargetResponse` exists, by its own docstring, to give a client "the same summary the `aforge offtarget`
  CLI surfaces" — and it projected every *numeric* method on the report (`n_sites`, `worst_score`,
  `specificity_score`, `ancestry_stratification`, `effective_matrix`) while omitting the one *prose* method.
  The CLI prints the aggregates and then `search: …` beneath them; that line is what says the scan covered 1%
  of the requested bases, that a supplied gnomAD file was inert, or **"NO SEQUENCE WAS SEARCHED — this is not
  a clean result, it is an empty one."** An API client saw `n_sites: 0, specificity: 1.0` and had no way to
  tell a clean guide from an empty run. The envelope now carries `search_description`.

- **No user-facing surface said which coordinate base its loci were in.** AlleleForge is uniformly 0-based
  half-open (BED-style), in at `--region` and out at every printed locus — but the report printed a bare cut
  site, `--region`'s help said only `'chrom:start-end'`, and `GenomicInterval.to_one_based()`, the declared
  egress converter, had no callers anywhere. Meanwhile `--variant` and `--pop-freqs` on the *same command
  line* explicitly documented 1-based VCF positions, so a reader carried that base onto the silent option.
  `chr7:100-200` searches 100 bases from offset 100; a genome browser shows 101 for the same string. Every
  rendered report now states the convention in its footer, `--region`'s help states it and contrasts it with
  the 1-based options, and `docs/data.md` covers both human boundaries. The convention is unchanged.

- **The leaderboard ranked scores that were never comparable.** `rankings()` put every entry for a task
  into one 1-2-3 column regardless of the frozen split it was measured on, the corpus (real vs the bundled
  synthetic stand-in), or even the metric — so a model scoring 0.91 on the synthetic fixture printed as
  **rank 1** above a model scoring 0.42 on a real corpus. Each cell was honest and labelled; the ordering
  was not. Ranks now hold only within a `ComparisonGroup` —
  `(primary_metric, split_version, dataset_is_synthetic)` — and both renderers emit one captioned, separately
  ranked table per group, with a "not comparable across groups" note when a task spans several. This also
  fixes sort direction and the score column's header, which were both taken from the first entry and so
  could sort one submission's metric by another's direction.

- **A resumed cohort's counts described two different populations and could not be added.** `skipped` was
  `len(done)` — the size of the *manifest file*, not the number of requested items already recorded — while
  `total` counted only what this run processed. Reusing a manifest across a narrower variant list therefore
  reported `total: 0, skipped: 5` for a **two-item** request. `skipped` now counts requests, so
  `total + skipped` is the number asked for, and the CLI header says it: *"cohort: 4 requested — 2 designed
  (2 ok, 0 failed), 2 already done (resume)"*, instead of leading with "0 item(s)" on a resume that had
  nothing left to do.

  Verified in passing that resume itself is sound: an interrupted run picks up exactly the outstanding
  items, produces the same results as an uninterrupted one, and leaves a complete manifest.

- **A cloning scheme whose enzyme cannot be screened reported a clean insert.** The Type IIS site table
  covers the three shipped schemes, and `_screen_enzyme_site` returned *no warnings* for anything else —
  indistinguishable from a screened, clean insert. `VectorScheme` is public, so a caller cloning into their
  own vector with a different enzyme got silence on a cloning-lethal hazard, which reads as a pass. It now
  emits `enzyme-not-screened:<enzyme>`, and a test asserts every shipped scheme is screenable so the flag
  never fires on the project's own schemes.

- **Two oligo warnings were filed as candidate caveats.** `internal-<enzyme>-site` and the new
  `enzyme-not-screened` travel on `SgRnaOligos.warnings`, which every render already prints as its own
  prominent line; they never appear in `candidate.flags`, so classifying them there did nothing. The
  classification guard could not tell, because it scanned for a local named `flags` and the oligo builder
  uses that name for a different list. Its scan is now limited to the modules that build candidate flags.

- **A one-shot safety input reached only the first *item* of a cohort.** `design_many` forwards its
  `design_kwargs` verbatim to every variant, and — with `max_workers > 1` — to every worker thread. A
  generator among them was consumed by the first item, leaving every later variant screened without it; in
  parallel, which item won was a race. Fixing the same aliasing inside `design()` did not help here, because
  the exhausted original is what the next item receives.

- **A one-shot safety input reached only the first chemistry in a menu.** `design()` hands `haplotypes` and
  `patient_vcf` — both typed `Iterable` — to every eligible vertical in turn. A caller passing a generator
  had it consumed by whichever chemistry ran first, so a single menu could hold **haplotype-aware
  base-editor candidates beside reference-only pegRNAs**: screened differently, presented identically, and
  ranked against each other on a safety axis they did not share. Both are now materialized once before the
  fan-out.

  This is the same defect as the previous fix, one layer up and worse, because there the whole search lost
  the input and here only *some chemistries* do — which is invisible in a menu that shows every candidate
  the same way. It was found by a mechanical sweep for `Iterable` parameters read more than once, and it was
  *detectable* only because `sources_considered` records per-report which sources contributed.

- **A one-shot `patient_vcf` iterable lost its personalization silently.** `search()` reads that parameter
  twice — once to count how much of it covers the searched region, once to enumerate the personalized sites
  — and it is typed `Iterable`. Given a generator, the **second** pass got nothing: the pass that actually
  personalizes the search. The count from the first pass then reported `patient-vcf: 1`, asserting that
  patient data had been used while none of it had. Haplotypes were already materialized at the top of the
  function; this was the sibling that was not. Introduced when the coverage counting was added.

- **Two performance regressions in the safety-labelling work of recent changes, both in `search()` — which
  runs once per *candidate*, so a 470-candidate prime menu multiplies them by 470.**

  `GnomadDB.available_populations` scanned the entire database on every call. Measured over 200,000 records
  that is 49 ms, so one design paid **~23 seconds** for a label, and a real per-chromosome gnomAD file is an
  order of magnitude larger again. It is now computed once — the database is immutable after construction.

  The haplotype and patient-VCF coverage counts re-derived the canonical contig for every
  (entry, region) pair. On a 2,000-haplotype panel that was **19% of an entire search**; indexing the regions
  by contig once brings it to 4% (333 ms → 292 ms against a 280 ms baseline).

- **The searchable-base count allocated a full copy of every scanned region.** It upper-cased each region
  before counting; on a whole chromosome that is a **~250 MB transient** on top of the sequence already
  held, in a path whose design is explicitly bounded-memory. Measured on a 20 Mb region: the copy costs
  +20 MB peak to save ~8% of a step that is negligible beside the scan itself. It now counts both cases in
  place. A regression introduced with the count itself, ten changes ago.

  It counts **both** cases even though sequence arrives upper-cased today, because that normalization is
  `pyfaidx`'s `sequence_always_upper=True` — a *dependency default*, not an invariant of this repository. If
  it changed, every base of a repeat-masked genome would count as unsearchable and the report would claim a
  real scan had covered almost nothing: the exact false alarm inverse to the one the count exists to
  prevent.

- **A candidate whose off-target search never ran scored a perfect safety mark, with nothing saying so.**
  `_safety` returns `1.0` when there is no off-target report — the reassuring extreme for an axis nobody
  measured — and its docstring justified that by saying the absence "is surfaced in the candidate's flags".
  No vertical did so. A candidate carried `safe 1.00` into the composite, weighted 0.30, purely for not
  having been screened. All three verticals now flag `offtarget-not-searched`, classified as a hazard so
  every render lifts it out of the flat flag list, and the docstring says what is actually true.

  The ranking arithmetic is deliberately unchanged: penalising an unmeasured axis means choosing how much,
  which is a policy this project has no basis for. The number stays and the label stops implying it was
  earned.

- **A truncated reference genome produced the most reassuring report the system can make.** A FASTA that is
  a contig header with no bases — an interrupted download — indexes without complaint, and a scan over it
  returned *"0 site(s), worst score 0.000, specificity 1.000"*. Every number is correct and the conclusion a
  reader draws is the opposite of the truth. The searchable-fraction line did not fire either: there were no
  requested bases to take a fraction of. A search that examined **no sequence at all** now says so, plainly,
  next to the numbers.

- **An allele-frequency column given as a percentage was accepted silently.** `af=1.5`, `afr=2.0` — the
  ordinary cause is a percent column (0–100) read as a fraction — passed validation, defeated the MAF filter,
  and put "200%" into the ancestry breakdown a human reads to judge whether a guide is safe in a population.
  `PopulationFrequency` now rejects any frequency outside `[0, 1]`, naming every offending field and saying
  frequencies are fractions. `0.0` and `1.0` remain valid: a monomorphic and a fixed allele are both real.

- **An empty or non-FASTA reference raised an indexing traceback**, now a clean `MISSING_DATA` error. A
  truncated download and a file that is really a VCF are the ordinary causes.

- **Two more file inputs failed with a raw traceback.** A haplotype panel whose header lacks a column
  raised a bare `KeyError`; it now names the missing column *and* the expected header, since a hand-built or
  differently-exported panel is the ordinary cause. Reading a real VCF without the optional `genome` extra
  raised an uncaught `RuntimeError` — the message was already actionable, only its presentation was a stack
  trace — and now exits `UNAVAILABLE` rather than `MISSING_DATA`, because the file is fine and the feature is
  not installed, a distinction the exit codes already make and scripts can act on.

  Found by the same sweep as the region-panel fix: feed every file input a file that is wrong in the way a
  real user's file is wrong. `--gnomad` came back clean and did the right thing — a wrong-contig frequency
  file runs and reports "supplied but contributing nothing in this region".

- **A region panel naming a contig the reference does not have dumped a raw traceback.** A BED built against
  another assembly or naming convention is the ordinary way this happens, and the CLI caught `ValueError`
  but not the `KeyError` that a missing contig raises deep in the fetch. It is now a clean usage error
  naming the offending region, the contig, and what the reference actually holds. Refusing is right rather
  than skipping the region: a silently dropped region searches less than was asked for, and a smaller search
  reports fewer off-targets — the direction that reads as safer and is not.

  A region running *past* a contig end is deliberately **not** refused. That is legitimate scoping, and the
  searchable-fraction line already reports it precisely ("0% of the 100 requested bases were searchable"),
  which is more informative than a refusal. Its wording is corrected too: bases past a contig end were being
  described as assembly gaps, which they are not.

- **The committed figures plotted fixture data without saying so.** All four — reference bias, conformal
  coverage, per-task ECE, generalization gap — draw numbers from synthetic stand-ins or a constructed locus,
  and every subtitle read as though the bars were measurements. The ECE chart even draws a *flag threshold*
  across them, framing fabricated numbers as a measurement against a real bar. A figure is the artifact most
  likely to be seen alone — a slide, an issue, a paper — so a caveat sitting in the report beside it does not
  travel with the image. Each subtitle now names its data: bundled synthetic fixtures at single-digit `n`, a
  seeded miscalibrated interval set, or a locus constructed in the style of `rs114518452` rather than the
  real allele. The note is conditional on the rows actually being synthetic, so it disappears when a real
  corpus arrives instead of becoming permanent furniture.

- **The generated calibration report — the artifact a reader treats as the project's calibration evidence —
  did not say its numbers were synthetic.** It opened with `| cas9-efficiency | regression | spearman | 0.0
  | 0.2 |` and gave neither the sample size (ten rows) nor the corpus (a bundled stand-in). The preprint
  states it in prose; the *generated file* is what gets read, quoted and screenshotted, and it said nothing.
  The report now leads with a block quote saying every number below comes from the synthetic stand-ins at
  single-digit sample sizes, demonstrates that the measurement machinery works, and is not a measurement of
  any model. Each row gains `n` and a per-row `synthetic`/`real` label, so a future real corpus is visibly
  different rather than silently replacing the same numbers.

- **Benchmark numbers computed on the bundled synthetic fixtures were published in the shape of real ones**
  (result `schema_version` 2 → 3). `aforge bench run cas9-efficiency` printed
  `spearman=0.0000, ece=0.2000 (n=10, model=crispr-bench-baseline)` — ten rows of a synthetic stand-in
  shipped so the harness runs in CI, presented exactly as a GUIDE-seq result would be. The datasets have
  always carried `synthetic: true`; nothing read it. On a project that calls this "a calibration-first
  benchmark", that is the most consequential unlabelled number in it.

  `BenchmarkResult` now records `dataset_is_synthetic` and, deliberately, records it **in the scientific
  body** that the reproducibility digest covers — which corpus a metric came from is as scientific a fact as
  which split, so a synthetic run cannot re-derive to a real one's digest. `bench run` prints a note saying
  the number measures the contract and not the model, and the leaderboard marks such rows **(synthetic)** in
  both renders, so a board can never rank a stand-in against a real result without saying so.

- **`aforge data list` labelled every redistributable dataset "vendored". Almost none of it ships.**
  `redistributable` is a *licence* fact — AlleleForge is permitted to redistribute this — and the table
  printed it as a *presence* claim. gnomAD v4.1 is CC0, so it read as `vendored` while no gnomAD data ships
  with the project at all, and a user reasonably concludes they do not need `--gnomad`. That is precisely
  the confusion the reference-only warning exists to prevent, printed by the command whose job is to say
  what data you have.

  The table now shows the permission and the availability separately: `may redistribute` /
  `fetch-on-consent` for the licence, and `bundled in the package` / `cached` /
  `NOT AVAILABLE - supply or fetch it` for whether a run can use it today. `DatasetDescriptor` gains
  `bundled`, true for exactly one entry — the Doench-2016 CFD matrix, whose bytes really do ship inside the
  package and are loaded from there, never from the cache, so reporting it as merely "not cached" would have
  been the same error in the other direction.

- **`aforge verify` reported "verified" for a run that re-hashed nothing.** The command makes two different
  claims — *provenance is complete* and *the pinned artifacts still hash to what was recorded* — and only
  the first is checked without `--cache-dir`. `aforge verify result.json` printed
  `verified: provenance is complete and consistent` with an empty check list, which reads as an integrity
  pass. That is "not measured" presented as "clean", the failure this project names at every other surface,
  on the one command whose entire purpose is checking. The output now says plainly that no bytes were
  re-hashed and how to make it happen, and says it again in the sharper case where `--cache-dir` *was* given
  but every artifact turned out unpinned, uncached or of unknown layout — the flag was passed and still
  nothing was established. The JSON payload gains `artifact_verification_run` and `artifacts_rehashed`.

- **The cohort example notebook printed a bare efficiency and could turn a real `0.0` into `NaN`.** It is
  the file a user is most likely to paste into their own script, and it rendered `best_eff` as a lone
  rounded float — the omission just fixed on the CLI, the report and the browser table — while writing
  `s.get("best_efficiency") or float("nan")`, where `or` also fires on a genuine efficiency of exactly zero.
  That is the same falsy-default shape that already shipped one bug in this very notebook. The table now
  shows `0.59 [0.16,1.00]`, marks `OOD`, carries a **caveats** column, and checks for `None` explicitly.

- **The browser's cohort table interpolated a raw user-supplied line into `innerHTML`.** A cohort row is
  built from the pasted variant list: `item_id` is a raw input line and `error` is an exception message
  quoting it back, and both went in unescaped — so a list line like `<img src=x onerror=…>` executed in the
  page. Every value in that table is now escaped at the boundary.

- **The browser's cohort table still showed a bare efficiency estimate.** The interval, the
  out-of-distribution flag and the recommended candidate's hazards were already in the batch response; the
  table rendered the point estimate alone. It is the triage view for the audience the web UI exists to
  serve — people who will not open a terminal — and the surface where a lone number is most likely to be
  trusted. It now shows `0.61 [0.46, 0.76]`, marks `OOD`, and carries a **caveats** column.

- **The Pol III spacer caveats were applied to prime editing only, so the same bad reagent was flagged on
  one chemistry of three.** Found by running a base-editor design and reading the card: the top-ranked
  candidate, labelled `recommended`, carried a spacer with **5% GC** — outside the band where U6
  transcription and oligo synthesis behave — and was reported `clean`, with no caveat anywhere. An identical
  spacer inside a pegRNA would have been flagged `gc-out-of-band`. These are properties of a spacer as a
  *transcribed reagent*, not of the chemistry holding it, so they now live in one
  `design/spacer_quality.py` that all three verticals call. The reproduce golden moved by exactly two
  flags — the canonical scenario's own ABE candidate has a 10% GC spacer that had never been flagged.

- **The flag-classification guard was under-covering itself.** The R98 check reads every
  `flags.append(...)` literal out of the source and fails on an unclassified flag — but the base-editor
  vertical attaches `recommended` through `model_copy(update={"flags": ...})`, which the scan never saw. So
  the guard reported full coverage while a flag had never been classified: the mechanism that exists to stop
  a hazard being missed, quietly missing one itself. It now also reads `"flags": (...)` constructions, and
  its second half — every classified flag must actually be emitted — keeps the first honest.

- **The README's headline principle claimed population-aware search "by default". It is not, and the same
  README said so three sections later.** Without `--gnomad`, `--haplotypes` or `--patient-vcf` the scan is
  reference-only — AlleleForge vendors no gnomAD data — and every surface already says so out loud, because
  an empty ancestry breakdown means *not measured*, not *clean*. The principle now describes the actual
  guarantee: population and haplotype variation is a first-class search pass, on whenever a frequency source
  is supplied, and explicitly labelled when it is not. `docs/index.md`'s "ancestry-stratified by default"
  is corrected the same way. For a project whose stated ethos is honest labelling over hype, the overclaim
  was on the one axis it exists to be careful about.

- **Principle 8 ("cite everything") was false for user-supplied inputs.** Your own gnomAD slice or patient
  VCF has no literature to cite, and provenance recorded `citation: null` for it. The principle now says
  what is actually true: everything in the *registries* carries a citation and a version, and a user-supplied
  input is pinned by content hash instead — recorded, not attributed.

- **A guide was reported as its own perfect off-target whenever bulges were allowed.** The on-target
  exclusion matched the guide's placement *exactly*, which is correct for an un-bulged hit — with no bulge a
  different start is a different protospacer. With bulges allowed the guide also aligns to **its own locus**
  through a single bulge: same bases, zero mismatches, score 1.0, at an interval one base shorter than the
  placement. That survived the exact test, halving the candidate's specificity to 0.5 and pegging its
  worst-case score at 1.0 for a spotless guide. On a realistic prime menu it affected **170 of 470
  candidates** — the precise failure the exclusion exists to prevent, reaching it through the one alignment
  class the check did not consider.

  The test is now containment in the placement grown by the hit's own bulge budget, which subsumes the exact
  case (an un-bulged hit has zero slack, and a full-length window contained in the placement *is* the
  placement) and keeps the original guarantee: a paralog abutting the on-target lies outside the window and
  is still reported. Found by running a cohort and reading the output; the regression test's genomic window
  is lifted from the actual reproduction, because a synthetic sequence does not reliably admit a bulged
  self-alignment and a test built on one passes against the bug.

- **A cohort row's two safety columns described different reagents.** `worst_offtarget` was the maximum over
  *every* candidate in the menu while `best_specificity` came from the recommended one, so a variant whose
  top pegRNA was spotless still reported `worst_offtarget = 1.0` because an alternative ranked #301 of 470
  was not — a row reading `worst 1.0, specificity 1.0`, which is self-contradictory on the column a reader
  scans to decide which variants need a closer look. Both are now scoped to the recommended candidate. An
  unsearched recommendation still reports `None`, never a reassuring `0.0`.

- **The README said VEP's molecular consequence drives "chemistry routing". It never did.** Routing is a
  pure function of variant class and intent; nothing read the consequence at all until it was surfaced in
  the menu rationale. The row now says what the adapter actually does.

- **`aforge verify` shipped complete and was documented nowhere.** The command that turns provenance from a
  record into a checkable contract — confirming a result names every model and dataset it used, and
  re-hashing each pinned artifact in a cache against the recorded hash — appeared in neither the README nor
  `docs/`. An undiscoverable feature is, in practice, an unshipped one, and nothing could catch it: the
  command worked and its own tests passed. It is now in the CLI table, and
  `tests/test_readme_documents_the_cli.py` asserts every registered command is named in the prose, with a
  guard-the-guard case so the assertion cannot pass blindly.

- **`Settings.allow_network` did nothing.** Its docstring said the registries "must never auto-download"
  when it is false; none of the three consulted it, so the setting was decorative — an environment that had
  already agreed to download still had to thread `consent=True` through every entry point, and a user who
  believed they had switched the network off had switched nothing. It is now the standing form of the
  per-call consent: a fetch proceeds if the caller passed `consent=True` **or** the environment opted in.
  The default stays `False`, so nothing about today's behavior changes for anyone not setting it. All three
  registries now call one predicate, `artifact_download_permitted()`, instead of three identical copies of
  `if not consent`, and the refusal messages name both ways to say yes.

  `allow_network` governs **downloads only**. It does not authorize sending anything out: disclosing a
  variant to a third-party effect API is a different act from fetching an artifact, and stays gated
  separately at its own call site regardless of this setting.

- **A VEP effect lookup sent the user's variant to a third-party public API with no consent gate.** Three
  of AlleleForge's four network paths — the model zoo, the dataset registry, the reference genome — refuse
  to fetch without an explicit `consent=True`. `VepRestPredictor.predict()` did not, and it is the one that
  matters most: the registries send a URL and receive a file, while this sends the variant *outbound* —
  chromosome, position, and both alleles — to `rest.ensembl.org`, and that variant may have come from a
  patient VCF. Consenting to download a reference genome is not consenting to disclose a variant. The
  built-in fetcher is now gated behind `consent=True`, and the refusal names both what leaves and where it
  goes so the user can judge it. An **injected** fetcher stays ungated: the caller supplied the transport
  and knows its destination — that is how CI replays a recorded response with no network at all, and gating
  it would break offline use to protect against nothing.

- **The provenance footer named the models but not the datasets, so a report said which code ran and not
  what it ran on.** "Population-aware off-target search" is a claim about *data* — which gnomAD release
  stratified the ancestries, whether a patient VCF was applied — and the footer that is supposed to make a
  result self-contained printed the version, build, seed, timestamp and models, then stopped. `tools` was
  missing too. Both renders now print them. The two footers were also duplicated implementations that had
  already drifted (the HTML said "reference build hg38", the PDF said "reference hg38") and would each have
  had to grow the same field twice; they now share `provenance_lines()`. A new test iterates
  `Provenance.model_fields` and asserts each one is either rendered or listed in
  `PROVENANCE_FOOTER_OMITTED` with a reason, so the next field added cannot be dropped silently.

- **Every PE3/PE3b candidate reported the *default* off-target cut-offs, whatever the run actually used.**
  A prime design searches twice — once around the pegRNA nick, once around the ngRNA nick — and merges the
  two reports. The merge rebuilt the report field by field, so it silently reset anything it did not name
  back to that field's default. It had already lost the scorer/matrix identity once and the sub-threshold
  tail once; adding the bulge budgets and CFD/MIT cut-offs made it three. A prime run at `cfd_threshold=0.05`
  therefore emitted a report labelled `0.20`, which is worse than an absent label: it asserts a scan that
  did not happen. The merge is now a copy-and-update — only the deduplicated sites and the summed
  sub-threshold tails are named, because those are the only two fields that genuinely aggregate — so any
  field added to `OffTargetReport` later is carried through without touching the merge. The regression test
  compares the merged report against the pegRNA report **field by field over `model_fields`** rather than
  naming fields, so it covers fields that do not exist yet.

- **A region-restricted off-target scan was indistinguishable from a genome-wide one.** The provenance
  config snapshot recorded `intent`, `weights`, `populations`, `run_offtarget`, `cell_context` and the
  resolved settings — but not the region restriction. A scan narrowed to a 100 bp window reports far fewer
  sites than one over every contig, and nothing in the result said which had happened: **"0 off-target
  sites" read identically either way.** That is the reassuring-value class again, on the safety axis. The
  snapshot now records `null` for a genome-wide scan, and otherwise how many intervals, how many bases they
  cover, and a content pin of the canonicalized list — compact enough not to carry a whole BED file, and
  order-independent so two runs agree iff they restricted to the same intervals. `chromatin_track` is
  recorded too, since it changes every efficiency number in the menu.

- **A population- or haplotype-aware run recorded none of the data that made it so.** `_collect_datasets`
  looked at the reference, gnomAD and ClinVar, and only recorded a source carrying a `dataset_version`
  descriptor — which a file loaded from a path does not have. A haplotype panel and a patient variant set
  were not consulted at all. So the moment those inputs became reachable from the CLI, a run could be
  population-aware, haplotype-aware and personalized while its provenance named **none** of it: not
  re-derivable, and a reader could not distinguish a populated scan from an unpopulated one. Each supplied
  file is now pinned by the **content hash of what it contained** — a user's file has no upstream version
  string, so the honest pin is the bytes, and two runs agree iff those agree. `design()` collects the
  haplotype and chromatin sources too, and the CLI passes the *panel* rather than a flattened tuple of its
  haplotypes so the descriptor survives. A source with no descriptor is omitted rather than given an
  invented one. **Personal variants are deliberately handled differently**: the run records that it was
  personalized and over how many variants, with no content hash — reproducibility does not need one, and
  embedding a fingerprint of a personal VCF in a shareable report would be an identifier for someone's
  genotypes.

- **A prediction's free-text caveats never reached the rendered page.** `Prediction.notes` sits beside the
  `calibrated` and `in_distribution` flags, and the renderers spell *those* out inline ("nominal — coverage
  not measured", "out-of-distribution") — but nothing rendered `notes` at all. So the note added earlier in
  this release stating that **the default prime scorer has no edit-size term** existed only in the JSON,
  and the HTML and PDF for a multi-base prime edit said nothing about it: precisely the caveat a reader of
  such a design needs, on precisely the page they read. Both renders now show any note the inline wording
  does not already convey, deduplicated, and skip the nominal-interval note because the parenthetical
  already says it. Found by sweeping the previous entry's lesson — follow every recorded diagnostic to a
  rendered artifact — across the codebase's other `note`/`warning` sinks; the rest were already delivered
  (cloning-oligo warnings render prominently, cohort errors have a TSV column, HDR donor disposition
  reaches the reagent line).

- **A report could be empty with no explanation anywhere in it.** `RankedMenu.rationale` records exactly
  which chemistries routed and why, which ran, and any that were skipped or failed — the designer degrades
  gracefully rather than crashing when one vertical fails, and puts the reason there. `DesignReport` had no
  field for it, so **every** renderer dropped it. A mistyped `--chromatin-track` produced zero candidates,
  exit code 0, and nothing in the JSON, TSV, HTML or PDF to say why, while the discarded rationale read
  `prime: skipped (KeyError: "unknown track 'missing'; known: ('atac',)")`. The same drop also hid the
  empty-menu explanation added earlier in this release: routing's per-chemistry reasons existed on the menu
  object and reached no user-facing artifact. `DesignReport.rationale` now carries it, the HTML renders it
  under "How this menu was assembled", and the PDF prints it above the candidates. Found by mistyping a
  flag while testing the flag.

- **The committed SVG figures had no freshness guard, so the README's "regenerated byte-for-byte" claim was
  untested.** `docs/assets/figures/*.svg` is committed output of code that keeps changing, and it is
  embedded in the README and the preprint — a stale one shows numbers the pipeline no longer produces, to a
  reader with no way to tell. The existing tests covered determinism and that rendering writes files, but
  never compared against what is checked in: exactly the shape the published JSON Schemas drifted in, where
  `Variant` had been missing a field for several releases before a test was added. The figures happened to
  be current; nothing would have reported it if they were not. `test_committed_figures_match_a_fresh_render`
  now names any stale file and the `make figures` command that fixes it, and is mutation-checked. A sweep
  of the other committed generated artifacts came back clean: the reproducibility golden is gated by CI's
  `reproduce` job, and the benchmark fixtures and splits are content-hashed with the loader verifying the
  dataset hash on load (`SplitIntegrityError`), so drift there already fails loudly.

- **The prime off-target cache was keyed on the spacers but not the loci.** A prime design routinely yields
  hundreds of pegRNAs over a handful of distinct protospacers — every PBS × RTT-homology combination reuses
  one — so `design_prime` caches the merged two-nick report, which is what keeps the vertical affordable.
  The key was `(pegRNA spacer, ngRNA spacer)`. But the cached *value* has each spacer's **own locus**
  excluded from it, and that exclusion is locus-specific: two pegRNAs sharing a spacer pair at different
  loci would share an entry, and the second would be handed a report that dropped a genuine paralogous
  off-target for it — the on-target-as-off-target class inverted. The key now names both placements too, so
  it covers every input the value depends on. **Honest scope:** no locus was found that actually produces
  such a collision (the enumerator's RT-reach window makes one hard to arrange), so this closes a key/value
  mismatch rather than a demonstrated miss; the invariant is pinned by a direct test of the keying function
  rather than by a genomic scenario.

- **`EditFrame` placed a span starting exactly at a pure deletion four bases too early.** A span boundary
  sitting on the edit is ambiguous, and the two directions want opposite answers: when the carried allele
  is empty — the target genome has a pure deletion — index `edit_plus` is simultaneously "just before the
  removed reference bases" and "just after" them. A span *starting* there begins after them; a span
  *ending* there stops before them. One map served both, so a 6-base span at that boundary reported a
  10-base reference footprint whose first four bases are **not in the protospacer at all**. Split into
  span-start and span-end maps, exactly as the off-target module's `_alt_coordinate_lift` already does for
  the same reason ("`lo` for a span start, `hi` for a span end"). Reachable through an *anchorless*
  deletion variant (`alt=""`), which `VariantClass.DELETION` and routing both admit even though
  `normalized()` keeps an anchor. Every existing test still passes — the enumerators are exercised on
  anchored loci, where the two maps agree — which is why the bug needed a direct test of the primitive to
  find.

- **`make ci` now actually mirrors CI, and a test keeps it that way.** The Makefile's header promises
  "CI runs the same commands; this is the local mirror so `make ci` reproduces the gate before a push."
  It was false: `ci` ran `lint type test docs reproduce` and omitted the `examples` job — the one job that
  would have caught the notebook regression in the entry below. `make examples` is now a target, `make ci`
  includes it, and `tests/test_gate_mirrors_ci.py` reads `.github/workflows/ci.yml` and fails if any
  blocking job is missing from the `ci` target. `security` (advisory, `|| true`) and `rust` (needs the
  compiled crate; `make native` covers it) are excused by name, and a second test fails if an excuse names
  a job CI no longer has, so a stale exemption cannot hide the next drift. Mutation-checked both ways:
  removing `examples` from the target fails, and adding a new CI job fails until it is mirrored or excused.

- **A cohort notebook broke on the `worst_offtarget = None` change and was shipped broken for five
  commits.** `03_batch_vcf.ipynb` renders the summary table with `round(s.get("worst_offtarget", 0.0), 3)`
  — and a `.get` default does not fire when the key is *present* with value `None`, which is exactly what
  that field became. CI's `examples` job runs `pytest --nbmake examples/` and would have caught it on the
  first push; the local gate used for those commits had stopped including it. The cell now renders an
  unmeasured axis as `-`, matching how it already renders a missing best chemistry, with a comment saying
  why `0.000` would be the wrong placeholder there. Caught while re-verifying numbers before publishing
  them in `specs/readiness-assessment.md`.

- **An empty benchmark evaluation no longer posts a perfect KL divergence.** `_distribution_metrics`
  averaged its per-example KLs with `if n else 0.0`. `kl` is in `LOWER_IS_BETTER`, so `0.0` is not a
  neutral placeholder — it is the **best possible score**, and a submission evaluated over zero examples
  would have ranked first on the leaderboard. The rest of the metrics suite fails *pessimistically* by
  design (a correlation, an AUROC, or an accuracy of `0.0`), which is safe precisely because those metrics
  are bounded below; KL is unbounded above and so has no pessimistic value to fall back on. It is now
  `None` — undefined — which is what `ece`, computed from the same empty inputs, already returned, and
  what the runner's `float | None` metric type and its "primary metric is undefined for this run" error
  path were already built for. Found by sweeping for the *pattern* behind the previous entry (a numeric
  default standing in for absence on a scored axis) rather than stopping at the one instance; the sweep's
  other hits were checked and are correct, each defaulting to the pessimistic end.

- **A cohort summary no longer reports `worst_offtarget = 0.0` when the off-target search never ran.**
  `_summarize` took the max over candidates carrying a report with `default=0.0`, so a run with
  `--no-offtarget` produced the same value as a run that searched and found nothing — and `0.0` is the
  *reassuring* one. A cohort manifest is triaged by scanning that column, so a whole cohort designed with
  the search off read as "no off-target risk anywhere". It is now `None` when nothing was measured,
  matching `best_specificity`, which already did this correctly. The harm is concrete: in a three-variant
  cohort used to check this, the first variant's **measured** worst off-target is `1.0` — a perfect-match
  hit — and the old code reported `0.0` for that same variant whenever the search was skipped. Found by
  running the real `aforge batch` command rather than by reading the code. Regression test pins both
  directions, since a fix that made *every* run report `None` would be equally wrong.

- **`hdr_donor` no longer builds a repair template over an assembly gap.** Its homology arms reach 50 bp
  either side — far enough to touch a reference `N` the guide itself never sees — and it spliced them in
  unguarded, producing an unsynthesizable oligo that, if forced, would template an ambiguous base into the
  genome **permanently**. This is the R34 prime-RTT `N`-gap class in the one reagent where the ambiguous
  base is written in for good. It now returns `None` there, and `donor_oligo` refuses an ambiguous donor at
  the ordering boundary as defense in depth. Distinguishing the two ways an arm can lack sequence mattered:
  an arm running past a **contig end** is now clamped to the sequence the reference actually provides
  (a short arm is the honest reagent), where before it was `N`-padded — so only a genuine interior gap
  fails closed. Regression test: a gap 30 bp from the edit leaves the guide designable but refuses every
  donor, while the same locus without the gap still yields one.

- **A precise edit no break-free chemistry can reach now routes to nuclease + HDR instead of returning an
  empty menu.** Correcting a 40 bp deletion used to route to *nothing*: beyond prime's RT template budget,
  not an SNV transition, not a knock-out. The user got a blank menu. Now that a precise nuclease candidate
  is a complete reagent (previous entry), the nuclease routes as an explicit **last resort** — offered only
  when neither base nor prime editing can reach the edit. That ordering is the point: HDR is inefficient,
  restricted to dividing cells in S/G2, and the same break yields NHEJ indels as its majority product, so
  it must not crowd menus a break-free chemistry already serves (tested: a small indel, a small insertion,
  and a transition SNV all keep the nuclease out). The 41-base restoration now returns two complete
  candidates, each with a 141 nt donor whose re-cut is blocked by the correction itself. Their cleanliness
  score is 0 because the NHEJ spectrum they carry contains no intended allele — that is the honest number,
  and no HDR efficiency is invented to improve it; the `outcome-is-nhej-spectrum` flag says why.

- **A precise-intent Cas9 candidate now carries the HDR donor that actually makes the edit.** `design_cas9`
  produced bare guides for CORRECT / REVERT / INSTALL intents — advertising a double-strand break as a
  correction it cannot make, since NHEJ repair yields indels, not the intended allele. `DesignCandidate`
  gains `hdr_donor`; the vertical attaches the donor `hdr_donor()` builds (including its PAM-blocking silent
  mutation when the repaired product would otherwise stay a Cas9 substrate), flags which of the three
  states the candidate is in (`hdr-donor:recut-blocked` / `:recut-not-blocked` / `:none`), and flags
  `outcome-is-nhej-spectrum` so the attached distribution is not read as the correction. The report's
  reagent line names the pair, not just the guide. A knock-out candidate is unchanged: it wants the break
  itself, so it carries no donor and none of the flags. **Routing still does not offer the nuclease for a
  precise intent** — that is the remaining step, and the rule's rationale says so explicitly rather than
  leaving the gap silent.

- **A guard that the published JSON Schemas match the code — and ten that had already drifted.**
  `docs/schemas/` is the machine-readable contract AlleleForge publishes, consumed by people who never read
  the Python. Nothing regenerated it automatically and nothing checked it, and the exporter's own docstring
  claimed it was "wired into the docs build" when nothing referenced it. Ten committed schemas were stale;
  most consequentially, `Variant` — the core input type — had been missing its `source_assembly` field for
  several releases, so a consumer validating against the published schema would have **rejected a document
  the library emits**. All ten are regenerated, the false claim is corrected, and
  `test_committed_schemas_match_the_code` now fails (naming the stale files and the regeneration command)
  whenever they fall behind again.

- **An acceptance test carries a small deletion from variant to rendered page.** The unit suites prove
  each hop of the variable-length RT template path; nothing proved the hop none of them own — that the
  edit's *identity*, not just its geometry, survives routing, design, ranking, the report builder, and the
  HTML renderer. A ΔF508-shaped 3 bp deletion now runs end to end in `tests/test_acceptance.py`, asserting
  prime is the only chemistry that delivers, that the top candidate's RT template writes 4 nt and says so
  in its flags, that the efficiency prediction admits its edit-size blindness, and that both the reagent
  line and the flag reach the rendered HTML. Every layer in that chain formerly assumed a single-base
  edit. The preprint's methods section now also states the variable-length RT template and the two bounds
  that actually bind.

- **A geometry-only efficiency score now says what it cannot see.** The default `PridictScorer` is a
  transparent geometry prior — its features are PBS/RTT length, nick-to-edit distance, PBS GC, and the
  epegRNA motif — with **no edit-size or edit-class term**. That was unremarkable while the enumerator
  could only template a single base; now that it writes anything up to a 29 nt insertion, two designs with
  identical geometry receive an identical score whether they install one base or twenty-nine, and the
  RTT-length penalty is the only indirect proxy. Rather than invent a size coefficient the heuristic has no
  basis for, the limitation is now stated in three places a user actually reads: the prediction carries an
  explicit `EDIT_SIZE_BLIND_NOTE` whenever it scores a non-single-base edit, the `pridict2-baseline` model
  card records it as a known failure mode (pointing at the trained `pridict2` model for size-aware
  numbers), and each candidate carries a `templated-edit:<n>nt` flag so a menu shows whether a design
  installs one base or many. The reproducibility golden was regenerated for the model-card line — its
  catching a card edit is the provenance machinery working; the canonical run's numbers are byte-identical.

- **A fourth runnable notebook, `04_indel_prime_correction.ipynb`, demonstrates the variable-length RT
  template on a ΔF508-shaped in-frame 3 bp deletion.** It shows routing admitting prime and only prime
  (with its rationale), designs the correcting pegRNA, reads the RT template apart into *5' homology +
  restored allele + 3' homology* — asserting the restored bases are exactly the reference allele — and
  contrasts `CORRECT` against `INSTALL` on the same variant to show the deleted span costing no template
  length. It is self-contained (a fixed-seed random locus, so its PAMs are real rather than planted) and
  executes in CI with the other three.

- **Prime editing now designs the whole small-edit repertoire — insertions, deletions, MNVs, and delins,
  not just single-base substitutions.** `enumerate_prime` templated an equal-length edit only and returned
  `[]` for everything else, and routing (correctly) declined those classes rather than under-deliver the
  flagship silently. Most of the monogenic disease prime editing exists for is an indel — the CFTR ΔF508
  3 bp deletion is the textbook case — so the flagship chemistry could not design a reagent for any of them.
  The RT template is now **variable-length**: *5' homology (nick → edit) + the whole desired allele + 3'
  homology*. A deleted span therefore costs no template length (a 44 bp deletion is as cheap to write as a
  1 bp one) while a written one costs a base each. Three knock-on contracts came with it:
  - **A second budget, mirrored in routing.** `PRIME_MAX_EDIT` (44 bp) still bounds the reference span an
    edit may replace; the new `PRIME_MAX_TEMPLATED_EDIT` (29 bp = the `RTT_RANGE` ceiling less the minimum
    3' homology) bounds the allele the RTT must *write*. `_prime_eligible` checks the **intent-specific**
    desired allele against it, so routing still never advertises an edit enumeration cannot produce — an
    over-long insertion is declined for `INSTALL` while `CORRECT` on the same variant (which writes one
    reference base back) stays eligible.
  - **Placements are reference footprints.** Enumeration runs over the genome the target actually carries,
    whose coordinates drift from the reference past a length-changing edit. A new `_Frame` maps every
    emitted span to the reference footprint its bases derive from — exact when it does not cross the edit,
    wider across a deletion, narrower across an insertion — and reports **no placement** for a protospacer
    lying wholly inside carried bases the reference does not contain, rather than naming a locus the
    reagent does not occupy. A nicking guide with no reference locus is dropped, not invented.
  - **PE3b classification survives an indel.** Seed disruption is decided by comparing the ngRNA's seed
    *window* in the start and edited genomes (a single-base comparison is meaningless once lengths differ)
    and is confined to the prefix the two genomes share — past a length-changing edit the two strings shift
    apart and the old single-index test would read misaligned windows.

  Verified metamorphically rather than by example: a new suite fetches every emitted pegRNA back and proves,
  with an oracle that shares no arithmetic with the enumerator, that its reverse-transcribed product is a
  unique locus of the edited genome, that its PBS anneals at that same locus in the start genome, that its
  protospacer reads off the start genome behind a real NGG PAM, and that the template spans the edit with
  the minimum 3' homology — across six edit classes, both intents, and both strands. The canonical
  reproducibility golden is unchanged (an SNV run; the SNV path is byte-identical).

- **The Cas9 outcome predictor is no longer handed the right sequence with the break in the wrong place.**
  `_cut_outcome` overlays the carried allele onto the local context before predicting the indel spectrum,
  but it skipped the overlay entirely for a length-changing allele (`len(allele) == len(ref_base)`) — the
  same restriction removed from `_overlay_allele` one function over — so the spectrum was computed on the
  *reference*. Removing that restriction exposed the second half of the bug: a length-changing allele
  shifts everything 3' of itself, **the cut site included**, so overlaying the sequence while leaving the
  cut index alone produces a plausible-looking indel spectrum for a different locus, with nothing to flag
  it. The cut index now moves with the allele when the cut lies 3' of the edit. Two regression tests, using
  a recording predictor that captures exactly what it was asked to score, assert the context is a real
  window of the carried genome and that the recorded cut names the same base the guide's own cut site does;
  both fail under the restored guard.

- **An empty menu now says why.** When no chemistry could make an edit, the rationale read
  `base_abe=no, base_cbe=no, prime=no, cas9_nuclease=no` and stopped — four `no`s and nothing actionable,
  which is exactly the case a reader most needs explained. Correcting a 40 bp deletion hits it: the edit is
  beyond prime's RT template budget, base editors cannot make an indel, and the nuclease is knock-out only.
  The menu now states that no chemistry can make the edit and gives each rule's own reason; the nuclease
  rationale additionally names the route that *does* apply — nuclease-plus-HDR — and declares honestly that
  `enumerate_cas9` and `hdr_donor` build that reagent pair today while the designer does not yet route,
  score, or rank it.

- **The reagent line and design rationale now name the edit, not only the geometry.** A report's one-line
  reagent summary read `pegRNA spacer …; PBS 13 nt / RTT 12 nt; tevopreQ1 motif; PE3` — every field a
  dimension, none of them saying what the reagent *does*. A pegRNA correcting a 3 bp deletion and one
  installing a substitution were indistinguishable on the page a bench scientist actually reads. Both the
  reagent summary (`RTT 12 nt writing 4 nt`) and the design rationale (`RTT 12 (4 nt written, +5
  homology)`) now state the templated length. The canonical reproducibility golden is unchanged.

- **Cas9 correction-intent guides are now enumerated against a length-changing carried allele instead of
  silently falling back to the reference.** The `cas9-design` spec has always required that a precise
  intent enumerate against *the sequence the target genome actually contains* — "a PAM the alternate
  allele destroys SHALL NOT be emitted; a PAM the alternate allele creates SHALL be found." The
  implementation honored that only for length-preserving alleles: `_overlay_allele` returned the window
  untouched whenever `len(allele) != len(ref)`, so a correcting design against a genome carrying a deletion
  or insertion was enumerated on the **reference**. It could propose a guide whose PAM the patient's own
  deletion has removed — a reagent that cannot cut — and miss the PAM the deletion creates at the junction.
  Nothing was flagged; the guide looked ordinary all the way to the oligo order. (Not reachable through
  `design()`, which routes cas9 to knock-out only, but `enumerate_cas9` / `design_cas9` / `hdr_donor` are a
  documented public surface, and cas9+HDR is the standard route for correcting an indel too large for
  prime editing.) The overlay now applies at any length, and the `EditFrame` introduced for prime editing —
  promoted to a shared `enumerate/_frame.py` — maps every emitted placement and cut site back onto the
  reference footprint its bases derive from, dropping a guide that has no reference locus rather than
  placing it on one it does not occupy.

- **`guide_context` now locates the guide in the carried sequence by content rather than by arithmetic on
  its placement.** A length-changing overlay shifts every base 3' of the edit, so slicing fixed offsets
  around a reference placement returned a frame-shifted context — of the wrong length — to whichever
  efficiency model was reading it, including the trained Rule Set 3 30-mer. The window is now anchored on
  the guide's own protospacer+PAM, which is exact regardless of drift, and a guide absent from the sequence
  being scored raises instead of scoring something else. Three regression tests (a PAM the deletion
  removes, a PAM it creates at the junction, and placement + context shape across the length change) all
  fail@HEAD -> pass.

- **The prime-efficiency scorer no longer reads a multi-base edit as farther from the nick than it is.**
  `_nick_to_edit` derived the nick-to-edit distance as `len(rtt) - rtt_homology_3prime - 1`, whose trailing
  `- 1` is the length of the templated allele — true only for an SNV. With the variable-length RT template
  now shipping, that arithmetic absorbs the whole written allele into the distance: a 5 bp insertion reads
  as 4 nt farther from its nick than it is and loses `0.03 x 4` of efficiency logit it never earned, while
  a deletion reads as nearer. Because the distance term is the same constant for every pegRNA of one
  variant, the mis-read is invisible *within* a variant's candidates — it surfaces exactly where it does
  damage, in the composite ranking that puts prime on one footing with ABE/CBE/nuclease in a single menu,
  and in cross-variant comparisons (cohort runs, the benchmark). `PegRNA` now records
  `rtt_homology_5prime` — the 5' arm, mirroring the 3' one it already carried — validated so the two arms
  cannot outrun the template, with `templated_edit_length` derivable from the pair; the enumerator sets it
  and the scorer reads it. Regression test (two pegRNAs, same RTT length and 3' homology, different
  templated-allele lengths) fails@HEAD (identical scores) -> passes. The canonical golden digest is
  unchanged: for an SNV the recorded arm equals the value the old formula derived.

- **The prime enumerator no longer emits a pegRNA whose RT template spans an assembly-gap `N`.** The cas9
  and base-editor enumerators skip any emitted span that covers a reference `N` (an unknown assembly gap),
  and the prime enumerator N-guards the pegRNA spacer and the nicking-guide protospacer — but it omitted the
  **RTT window** (`_enumerate_frame`, `enumerate/prime.py`). A pegRNA whose RT template reached a downstream
  `N` was emitted as a valid design: an unsynthesizable oligo that, if forced, would template an ambiguous/
  uncontrolled base into the genome exactly at the gap. `DNASequence` permits IUPAC `N` (needed for degenerate
  PAMs), so `PegRNA` construction never rejected it and the suite stayed green. The RTT window is now N-guarded
  before templating, mirroring the two sibling enumerators; the shorter RTTs that stop before the gap still
  resolve. Regression test (a contig with a gap `N` inside the RTT reach) fails@HEAD (10 of 80 pegRNAs carry an
  `N` in the RTT) → passes (0). The recurring "wet-lab-relevant defect passing under a green suite" class, in the
  prime-editing flagship. Found by a Round-34 property-based fuzzing sweep that fetched every enumerated reagent
  back against the reference.

- **`BaseEditWindow` now validates its edit positions against the spacer length instead of admitting an
  out-of-range one.** `_check_window` (`types/guide.py`) validated the `window` bounds but not
  `target_positions`/`bystander_positions`, so a position past the spacer was accepted at construction. The
  base-edit outcome predictor then reads `spacer[position - 2]` (`base_outcome.py`), which for a motif editor
  (CBE4max/APOBEC) raises an opaque `IndexError` and for a non-motif editor (ABE8e) silently returns a
  garbage-but-finite score. The enumerate pipeline can't produce such a window, but a hand-built or deserialized
  one can. `_check_window` now rejects any target/bystander position outside `1..len(spacer)`. Parametrized
  regression test (position 0, past-end, one-past-window) fails@HEAD → passes. The R17 type-contract-completeness
  discipline (a model admitting a value its consumers can't handle), on the base-edit window.

- **`PridictEngineAdapter._efficiency` now fails closed on a non-finite PRIDICT2 score instead of laundering
  it into a confident prediction.** `value = min(1.0, max(0.0, score_percent / 100.0))` maps `NaN` to `0.0`
  (because `max(0.0, nan)` is `0.0`) and `±inf` to `1.0` — so a `NaN` cell in the PRIDICT2 output CSV (reachable
  via `_parse_predictions`' `float(row[...])`) became a confident "won't edit" `0.0`, indistinguishable from a
  real low score and ranked last, while `inf` became a perfect `1.0`. A non-finite score is corruption, not a
  prediction. `_efficiency` now raises `ValueError` on a non-finite score, matching the module-wide finiteness
  contract (`Prediction` rejects non-finite bounds; the benchmark metrics reject non-finite inputs). Finite
  out-of-range scores (250, -50) still clamp to `[0, 1]` as documented. Parametrized regression test
  (`nan`/`inf`/`-inf`) fails@HEAD → passes. Extends the finiteness theme (R12/R16/R17/R24) onto the trained
  PRIDICT2 efficiency path.

- **`parse_genomic_hgvs` now fails closed on a reversed range (`end < start`) instead of fabricating a phantom
  variant.** A range operation whose end precedes its start (e.g. `g.5_3delinsAC`, `g.2_0del`) had no guard, so
  `ref_lookup(start, end)` read a backwards, empty Python slice: the deleted/duplicated bases silently vanished
  and a `delins` collapsed into a pure insertion that deletes nothing — a corrupt variant accepted with no error
  (only masked when a real `ref_lookup` is supplied; with `ref_lookup=None` it raised "needs a reference"). The
  parser now raises `ValueError` when `end < start`, allowing a single-base range (`end == start`) as before.
  Parametrized regression test (five reversed forms across del/delins/dup/ins) fails@HEAD → passes; the
  single-base mirror still parses. Real HGVS emitters never produce a reversed range, so exposure is low, but a
  *silent* corruption is the wrong side of the repo's "raise on malformed variant input" line (R18/R27/R33).
  Found by a Round-34 property-based fuzzing sweep of the HGVS parser.

- **`resolve` now fails closed on a wrong-build base hidden in a trimmed position instead of silently
  laundering it.** Reference validation ran *after* parsimonious normalization: the input adapters called
  `Variant.normalized()` eagerly (in `VcfRecord.to_variant`, the `chrom:pos:ref>alt` string parser, and the
  raw-`Variant` branch of `_to_variant`), trimming a shared prefix/suffix base — one where `ref == alt`, so
  it carries no edit — before `_validate_ref` ever saw it. An assertion like `chr2:6 AT>GT` against a
  reference whose span reads `AC` is a textbook wrong-build/`REF_MISMATCH` signal (the unchanged `T`
  disagrees with the reference `C`), but trimming reduced it to `A>G`, whose retained `A` matches, so the
  resolver accepted it **and** changed the caller's requested edit — applying `A>G` (yielding `GC` against
  the real reference) instead of the asserted `GT`. This is the recurring "safety input inert on its consumed
  axis with a green suite" class: the fail-closed check existed but the value it needed was destroyed
  upstream. `resolve` now validates the **full asserted `ref` span, un-normalized**, against the reference
  before `_left_align`/`normalized()` can trim it (the coordinate-family adapters defer normalization to
  `resolve` for exactly this reason; RawTarget and the HGVS path already validated their asserted bases
  pre-normalization, so both were already safe). Regression tests cover the suffix-trim MNV→SNV case, the
  prefix-trim case, and all three coordinate input forms (string / `VcfRecord` / raw `Variant`); each fails
  @HEAD (accepts the wrong build) → passes with the fix, and the legit multi-base mirror (`AC>GT` where the
  span really is `AC`) still resolves. Found by a Round-33 property-based fuzzing sweep of `normalized()` /
  `_left_align` fail-closed behavior (~58,000 examples).

- **`aforge bench run --seed` now records a consistent seed in provenance instead of a self-contradictory
  one.** `run_benchmark` captured the top-level `provenance.seed` from its `seed` argument but the
  `config_snapshot` from the global `get_settings()` singleton — which the CLI callback never updates with
  `--seed` (it exports only `ALLELEFORGE_CACHE_DIR`). So `aforge --seed 777 bench run <task>` produced a
  signed result whose `provenance.seed` was `777` while `provenance.config_snapshot["seed"]` was the default
  `20240501` — an internally contradictory, non-re-derivable provenance block (the signature still verifies
  because it signs the contradictory body, so tamper-detection does not flag it). The design path holds the
  intended invariant by deriving both from one `Settings` object. `run_benchmark` now applies the run's seed
  to the resolved settings before snapshotting, so `provenance.seed == config_snapshot["seed"]` for every
  caller. The built-in baseline is seed-independent so no metric changes, but this is the CLI seam a
  seed-sensitive model's signed leaderboard submission flows through. Regression test (`seed=777` → both
  seeds agree) fails@HEAD → passes. This is the sibling of the Round 15 batch-seed provenance divergence,
  found by a `data`/`bench` CLI-subcommand audit.

- **The VEP live-REST predictor now sends the correct region for an insertion instead of consuming a
  reference base.** `VepRestPredictor.request_url` computed the region end as `start + max(len(ref), 1) - 1`,
  clamping the span to a minimum width of 1. For an insertion (`ref=""`, the canonical form this codebase
  produces — `Variant.normalized()` keeps no anchor base for it) this emitted a 1-base region
  (`17:101-101/ACGT`), which Ensembl VEP reads as a substitution replacing the base at that position,
  returning a consequence for the wrong span. VEP's documented convention for an insertion is a zero-width
  region (`start = end + 1`, i.e. `17:101-100/ACGT`). Dropping the `max(..., 1)` clamp — `end = start +
  len(ref) - 1` — yields the correct region for every class (SNV → `start`, deletion/MNV → `start +
  len(ref) - 1`, insertion → `start - 1`). Regression test (region string for SNV/deletion/MNV/insertion)
  fails@HEAD for the insertion → passes. Found by a VEP live-REST audit (which cleared the deletion/MNV/SNV
  conventions, `parse_vep_response` allele alignment, and transcript selection).

- **`aforge batch` now honors the `chemistry` and `cell_context` config-file keys instead of silently
  ignoring them.** Both keys are whitelisted in `_RUN_PARAM_KEYS` (so no "unknown config key" warning
  fires), and `aforge design`, the web `/api/batch`, and the Python `design_many` all honor them — but the
  CLI `batch` command read only `intent`/`populations`/`weights`/`max_per_chemistry`/`run_offtarget` from
  the config and passed neither `chemistries` nor `cell_context` to `design_many`. So a `config.toml`
  restricting `chemistry = ["cas9_nuclease"]` or setting `cell_context` was silently dropped for a whole
  cohort run — the menus included every chemistry and recorded `cell_context = None` in provenance, diverging
  from the same run via `design`/web/Python, with no signal to the user (the whitelist suppresses the warning
  that would otherwise flag an unread key). `batch` now reads both keys and forwards them to `design_many`,
  a CLI flag still winning. Regression test (a `chemistry`/`cell_context` config restriction actually empties
  a non-matching menu and reaches provenance) fails@HEAD → passes. Found by a cross-interface parity re-sweep.

- **A ClinVar `CLNSIG` carrying a secondary assertion now classifies by its primary clinical class
  instead of collapsing to `OTHER`.** ClinVar joins a variant's primary assertion with secondary ones in
  a single comma-separated `CLNSIG` token (e.g. `Pathogenic,_risk_factor`, `Likely_pathogenic,_low_penetrance`,
  `Pathogenic/Likely_pathogenic,_risk_factor`) — a form carried by clinically major variants such as HFE
  C282Y (`rs1800562`), Factor V Leiden (`rs6025`), and prothrombin G20210A (`rs1799963`). `_normalize_significance`
  did an exact-match lookup against a single-token map and defaulted every combined form to
  `ClinicalSignificance.OTHER`, silently dropping the pathogenic signal a downstream filter on
  `{PATHOGENIC, LIKELY_PATHOGENIC}` would key on. It now classifies by the primary assertion (the token
  before the first comma) while preserving the verbatim `raw_significance` for auditing. Regression test
  (three combined-assertion records → correct primary class) fails@HEAD → passes. Found by a data-population
  ingestion audit (which cleared gnomAD AF selection, dbSNP `chrM` mapping, symbolic-ALT skipping, and the
  registry fail-closed gates).

- **An HGVS `dup`/`delins` that states its bases from the wrong genome build now fails closed, closing a
  hole in the "asserted ref that disagrees is a hard error" guarantee.** A `dup`/`del`/`delins` may state
  its duplicated/deleted bases (legal HGVS, emitted by real tools as `c.4_6dupTGA`). `HgvsAdapter.to_variant`
  short-circuited the reference read whenever bases were stated (`parsed.ref_bases or self._fill(...)`), so
  the stated bases were used verbatim and never checked against `reference[start:end)`. For a `dup` the
  resulting variant has `ref=""`, so the resolver's `_validate_ref` early-returns — the reference is *never*
  consulted. `chr2:g.6_7dupCC` against a reference reading `AC` at that span was accepted, fabricating an
  insertion of the un-checked `CC`; the identical `del` correctly failed closed. A stated-base `delins`/`del`
  additionally discarded the parsed span length, so `g.6_8delAC` (a 3-base span, 2 stated bases) silently
  became a 2-base deletion. `to_variant` now validates stated `dup`/`del`/`delins` bases against the
  reference span (identity and length) when a reference is available, exactly as `sub`/`del` already do.
  Regression tests (wrong-build `dupCC`, span-length `delAC`, wrong-base `delAG` → raise; honest forms still
  resolve) fail@HEAD → pass. Found by a variant-resolution + coordinate audit (which cleared 0/1-based
  conversions, left-alignment, insertion anchoring, VCF multi-allelic/symbolic handling, and liftover
  fail-closed).

- **The off-target search no longer crashes with a `KeyError` when `--maf 0` is combined with requested
  populations a haplotype doesn't carry.** `enumerate_haplotype_sites` filtered the carrying populations
  with `hap.frequencies.get(p, 0.0) >= min_freq`; at `min_freq <= 0` the `.get` default `0.0` satisfied
  `>= 0.0`, admitting populations absent from the haplotype's frequency dict, which then raised `KeyError`
  at `ancestries={p: hap.frequencies[p] ...}` — aborting the entire search. This is CLI-reachable via
  `aforge off-target --maf 0 --populations AFR,EUR,...`, and a region-frequent haplotype carrying only a
  subset of super-populations is the normal case. The filter now requires the population to be *recorded*
  in `frequencies` (a population with no known frequency does not carry the haplotype), matching the robust
  sibling behavior of the population-variant path. Regression test (`min_freq=0.0` with an uncarried
  requested population → one clean site, no crash) fails@HEAD → passes. Found by a cohort/population audit
  (which cleared the de-novo/strengthen nomination gate, indel coordinate lift, minus-strand PAM creation,
  and cohort key injectivity).

- **The design report now marks an uncalibrated interval as nominal instead of presenting it identically
  to a calibrated one.** Every default scorer emits `calibrated=False` (a fixed heuristic ±0.15 band whose
  `interval_level` is a *nominal* target, not measured coverage — the `Prediction` records this "in the
  notes" by contract), yet the HTML and PDF renders surfaced only the `in_distribution` flag and printed
  the band as `@ 80%`, so a reader could not tell a calibrated 80%-coverage interval from an unvalidated
  heuristic one; the TSV/Parquet export exposed `in_distribution` but had no `calibrated` column at all.
  The renders now append `(nominal — coverage not measured)` to an uncalibrated efficiency/bystander line
  (mirroring the existing OOD qualifier), and the flat export gains a `calibrated` column (schema version
  bumped 1 → 2). This reads only the already-correct in-memory `calibrated` field and does not touch the
  deferred `Prediction.calibrated` serialization round-trip. Regression tests (default menu render carries
  the caveat; a calibrated menu omits it; TSV carries the column) fail@HEAD → pass. Found by a report-render
  audit (which cleared HTML/SVG/PDF injection, off-target chart arithmetic, and column ordering).

- **A cached-but-unpinned dataset now fails closed too, closing the same fail-open as the checkpoint
  gate.** `DatasetRegistry.resolve` refuses to *download* an unpinned dataset (`ChecksumError`), but the
  cached branch only re-verified when the descriptor *pinned* a `sha256` (`elif desc.sha256 is not
  None`), so a file at the cache path for an unpinned descriptor resolved **unverified** — contradicting
  the method's docstring and the download branch. Found by a proactive sweep for the "fail-open gate
  that only fires on one branch" class the model-zoo fix (this session) surfaced. The cached branch now
  fails closed on an unpinned descriptor, exactly like the download path; the user-provides-file
  workflow is unaffected (it loads via the loaders' explicit-path API, not this consent-gated fetch, and
  `resolve` has no production callers today). Regression test (a cached file for an unpinned descriptor →
  `ChecksumError`) fails@HEAD → passes; data-registry spec makes the cached-unpinned refusal explicit.

- **A cached-but-unpinned model checkpoint now fails closed, closing a fail-open in the weight-load
  trust gate.** `ModelRegistry.checkpoint` refuses to *download* an unpinned checkpoint (`ChecksumError`,
  "refusing to fetch an unverifiable artifact"), but the **cached** branch only re-verified when the
  card *pinned* a hash (`elif card.checkpoint_sha256 is not None`), so a file already present at the
  cache path for a card with `checkpoint_sha256 is None` was returned **unverified** — contradicting the
  method's own docstring ("ChecksumError: If the card pins no hash") and the registry's "a pinned hash
  is required to load" guarantee. An out-of-band file dropped at the checkpoint path for any unpinned
  card (all cards but `rule-set-3` are unpinned by design) would load unverified. The cached branch now
  fails closed on an unpinned card exactly like the download path. Regression test (a cached file for an
  unpinned card → `ChecksumError`) fails@HEAD → passes; model-zoo spec gains a cached-but-unpinned
  scenario. Found by a model-zoo gate audit (the sibling of the R16 content-addressed-cache fail-closed
  fix — a verify gate that only fired on the pinned path).

- **The web API returns 422 for semantically-invalid ranking weights instead of leaking a 500.** The
  `weights` request field is length-validated (exactly 4) at the schema boundary, but the *values* are
  only checked when `RankingWeights` is constructed inside `_design_options` — which `/api/design` and
  `/api/batch` both call without catching the `ValueError` it raises for a negative, all-zero, or
  non-finite weight. So a well-typed but invalid weights vector (e.g. `[-1, 0.5, 0.5, 0.5]` or
  `[0,0,0,0]`) surfaced as an unhandled 500 server fault rather than a 422 bad request. This is the web
  sibling of the CLI `--weights` hardening — the CLI mapped it to a usage error, the web path did not.
  `_design_options` now catches the validation error and raises `HTTPException(422)`. Regression test
  (negative and all-zero weights → 422 on both endpoints) fails@HEAD → passes; web-api spec gains an
  invalid-weight-values scenario. Found by a web-API lifecycle audit.

- **The global `--cache-dir` flag now actually redirects the cache, instead of being silently ignored.**
  `--cache-dir` was declared and stored on the CLI's global state but read nowhere: `design`/`batch`
  forwarded only the seed into `Settings.load(...)`, and the cache root is consumed process-wide via the
  `get_settings()` singleton (dataset registry, model loader, FM-index, reference index, gnomAD fetch) —
  which the CLI never configured. So a user redirecting the cache (CI, a sandbox, a read-only home) was
  silently sent to the default `~/.cache/alleleforge`, violating the cli spec's "every command accepts
  `--cache-dir`" and "settings resolve through `Settings.load()`" guarantees. The root callback now
  exports `ALLELEFORGE_CACHE_DIR` (the env var the whole settings stack already resolves, env > file >
  default), redirecting every consumer at once with no threading changes — safe because the singleton
  loads lazily, after the callback. Regression test (`aforge --cache-dir X … → resolved cache_dir == X`)
  fails@HEAD → passes; cli spec gains a cache-directory scenario. Found by a CLI end-to-end audit (which
  verified exit codes, weights, config precedence, batch, and verify all correct).

- **Gene-model and ENCODE-track lookups are now contig-naming-independent, closing the last two
  un-reconciled loaders.** `GeneModels` and `EncodeTracks` keyed and queried `_by_chrom`/`_segments`
  by the raw contig, so a bare-named (`11`) query against a chr-named (`chr11`, from a GENCODE GTF or
  ENCODE bedGraph) index returned `[]` genes / `0.0` signal — the `.get()` missed before the
  naming-aware `overlaps` ever ran. `GeneModels` feeds transcript selection in the variant resolver and
  `EncodeTracks` feeds prime-editing efficiency, so a pipeline pairing an Ensembl-named query with a
  UCSC-named annotation silently designed on an empty result rather than a flagged one. Both now key on
  `canonical_contig` (index/construction + lookup), merging two spellings of one contig; this is the
  same recurring reference-vs-source class the dbSNP fix closed, in its final two loaders. Regression
  tests (bare-named query finds chr-named genes/signal) fail@HEAD → pass. The data-registry
  contig-naming requirement already covers these. Found by a genome-access edge-case audit (which
  verified reference fetch edges, N-runs/soft-masking, coordinate math, and liftover all correct).

- **The off-target chart no longer paints an unsearched candidate as the safest guide, and the PDF no
  longer drops the ranking rationale.** Two report-fidelity fixes: (1) the HTML "worst-case off-target
  score by ancestry" figure built a bar trace for every candidate using `by.get(ancestry, 0.0)`, so a
  candidate that was never off-target-searched (`n_offtarget_sites is None`, no ancestry rows) was
  plotted as `0.0` in every ancestry — the lowest, best-looking bar — while the text body correctly
  showed nothing, so the chart could flip a visual ranking toward the least-evidenced guide (the
  recurring "safety unknown masquerading as safety-clean" class). The trace loop now skips unsearched
  candidates; a *searched* candidate with zero sites still legitimately plots `0.0`. (2) The PDF
  renderer never emitted each candidate's `rationale`, though HTML and JSON do and the report spec lists
  it as a per-candidate field — the printable leave-behind a researcher carries into the lab was missing
  the explanation of *why* a candidate ranks where it does. Both regression-tested (fail@HEAD → pass);
  reporting spec gains cross-surface-rationale and unsearched-not-drawn-as-safest scenarios. Found by a
  report-fidelity audit (which verified rank order, worst-ancestry selection, and efficiency/interval/
  specificity agreement across HTML/PDF/JSON/TSV correct).

- **The cloning enzyme screen now catches a Type IIS site at the 3' overhang junction too, so a
  cloning-lethal insert can no longer ship clean on the default scheme.** A prior round fixed the screen
  to cover the 5' overhang/insert junction, but it screened only the `top` oligo (`top_overhang +
  insert`), which stops at the insert's 3' end. In the ligated plasmid the top strand runs `top_overhang
  + insert + revcomp(bottom_overhang)`, so a site straddling the insert's 3' end and the bottom overhang
  was never seen: on the **default** lentiGuide/BsmBI scheme, a spacer ending in `GAGAC` plus the `AAAC`
  bottom overhang reconstitutes `CGTCTC` on the antisense oligo (the plasmid top strand reads
  `…GAGACGTTT`, and `GAGACG` = revcomp of the BsmBI site) — BsmBI would recut the assembled plasmid at
  the junction, a silent Golden-Gate failure, yet no warning was emitted. Now screens the full
  ligated-insert top strand (`top + revcomp(bottom_overhang)`) for both sgRNA and pegRNA inserts;
  `_screen_enzyme_site` already scans both strands, so one pass covers both junctions and both strands.
  Regression test (a `…GAGAC` spacer → the bottom-junction site is flagged) fails@HEAD → passes;
  oligo-output spec now requires screening the full ligated insert. Found by an oligo-cloning audit.

- **A symbolic or spanning-deletion ALT no longer aborts a whole ClinVar/dbSNP parse.** ClinVar's row
  filter skipped only `ALT` in `.`/empty, so a spanning-deletion `*` or a symbolic `<DEL>`/`<INS>`
  (both of which real VCF releases contain) reached the `Variant` allele validator, raised, and aborted
  the entire `from_vcf` — losing every valid record after the bad row. dbSNP had the same exposure;
  gnomAD silently stored the garbage allele instead. Added a shared `is_sequence_allele` helper and
  applied it in all three loaders: a row whose ALT/REF is not a plain `ACGTN` sequence is skipped and
  the parse continues, so one malformed row can no longer discard the rest of the release, and the
  three loaders now agree on what a usable row is. Regression test (a `*` and a `<DEL>` row followed by
  a valid row → only the valid row survives) fails@HEAD → passes; data-registry spec generalizes the
  symbolic-ALT skip. Found by a data-loader ingestion audit.

- **dbSNP lookups are now contig-naming-independent, so a bare-named query and a mitochondrial rsID no
  longer silently miss.** dbSNP was the one loader that never received the contig-naming reconciliation
  its siblings (gnomAD, ClinVar, haplotype panels) all have. Two facets from the same root: (a) a bare
  `MT` rsID was prefixed to `chrMT`, which is not an hg38 contig (hg38 uses `chrM`), so a mitochondrial
  variant resolved via `dbsnp.locus(rsid)` carried a contig absent from the reference — a silent
  downstream miss; (b) `rsids_at` indexed and queried `_by_chrom` by the raw contig, so `rsids_at`
  with a bare `2` interval returned `[]` while `chr2` returned the records (the same bare query
  correctly returns records from gnomAD/ClinVar/haplotypes). Both fixed by keying on `canonical_contig`
  (index + query) and mapping `MT`/`M` → `chrM` when prefixing, mirroring the siblings. This is the
  recurring reference-vs-source naming class prior rounds closed in the other loaders. Regression tests
  fail@HEAD → pass; data-registry spec gains a contig-naming reconciliation requirement. Found by a
  data-loader ingestion audit.

- **A delins is no longer silently corrupted into a wrong-position insertion during left-alignment.**
  `_left_align` ran its "roll the indel left through a repeat" loop for any `len(ref) != len(alt)`, but
  that loop assumes a *pure* indel (exactly one allele empty). A true delins (e.g. `AC>T`, both alleles
  non-empty after trimming) whose alt's last base equals the preceding reference base rolled `ref` to
  `""` — discarding the deleted bases and relocating the variant. `chr2:6:AC>T` against a `TTTTT…`
  lead-in resolved to `pos=0, ref='', alt='T'` (an insertion at the wrong locus) instead of `pos=5,
  ref='AC', alt='T'`; because the mangled `ref` was empty, `_validate_ref` returned early and the
  corruption was accepted with no error. It fires whenever a delins sits near a homopolymer/repeat with
  its alt's last base matching the preceding base — a common ClinVar pattern — and corrupts every
  downstream consumer (working interval, effect prediction, guide design). Fixed: after parsimonious
  trimming, a still-both-non-empty variant is a genuine delins with no anchor to roll, so it is
  returned in its parsimonious form rather than falling into the pure-indel loop. Regression test
  (coordinate and `g.delins` spellings) fails@HEAD → passes; the variant-resolution spec now scopes
  rolling to pure indels explicitly and gains a delins scenario. Found by a variant-resolution
  edge-case audit.

- **The `Prediction` contract now rejects non-finite bounds and values, closing the non-finite class
  at its source.** `_check_interval` validated ordering, level, and point containment but not
  finiteness: a `NaN` value was caught only incidentally (it fails the containment check), and `±inf`
  slipped through entirely — `value=inf` with `interval=(0, inf)` satisfies `low <= value <= high`,
  and a finite value with an `interval=(lo, inf)` bound passed too. No current scorer produces one (a
  scoring-layer overflow audit confirmed every log/exp/sqrt/division is guarded), but a `Prediction`
  is deserializable, so a non-finite one loaded from JSON would flow into the ranking composite (an
  `inf` efficiency scrambles the sort) or a report (a `NaN` breaks JSON) — the same class the metrics
  and leaderboard finiteness guards closed on the benchmark side. Now rejects a non-finite interval
  bound or numeric value at construction/deserialization. Regression tests fail@HEAD → pass;
  uncertainty-contract spec gains a "non-finite bound or value" scenario. This is the source-level
  completion of the finiteness theme (scorers compute finite, the prediction contract rejects
  non-finite, benchmark ingestion rejects non-finite claims).

- **A benchmark result now rejects a non-finite `primary_value`/metric, so a signed `NaN` can't make
  the leaderboard order non-deterministic.** The leaderboard sorts on `primary_value`, and a `NaN`
  there loses every comparison — a single externally-signed submission carrying `NaN` would scramble
  the whole board's ranking order. The computed path is already finite (the metrics guard above), but
  a signed value is a *claim* deserialized from JSON, not a fresh computation, so `BenchmarkResult`
  now validates `primary_value` (and each metric value) finite at construction/deserialization and
  raises otherwise. Regression test (deserialize a result with `NaN` primary_value / `inf` ece →
  rejected) fails@HEAD → passes; benchmark-harness spec gains a "signed non-finite result rejected"
  scenario. Completes the finiteness theme: the metrics *compute* finite, and ingestion *rejects*
  non-finite claims. Flagged as a follow-up by the benchmark scientific-correctness audit.

- **Two concurrency races in the content-addressed cache's `put_bytes` are fixed.** (1) A
  `verify=True` cache wrote the checksum sidecar *after* renaming the payload into place, so a
  concurrent `get_bytes` landing in that window saw a payload with no sidecar and — because the read
  path now fails closed on a missing sidecar — raised `CacheIntegrityError` on perfectly valid,
  freshly-written data (16 threads → 15 spurious errors). The sidecar is now published *before* the
  payload (each via its own temp+rename), so a reader never sees a payload without its checksum and
  the fail-closed check fires only on genuine tampering. (2) The temp-file name used `id(data)`,
  which is unique only among *live* objects, so two threads writing the same key with the same bytes
  object collided on the temp path and the loser's `replace` raised `FileNotFoundError`; the temp
  name now uses a per-write `uuid` token. Race (2) was latent (current callers serialize fresh bytes
  per call) but a landmine for any future caller writing a shared/memoized payload concurrently.
  Non-flaky regression test (16 threads, widened switch interval) fails@HEAD → passes; the
  cache-atomicity spec gains a concurrent-verified-writes scenario. Found by a concurrency audit that
  drove real contention against the cohort parallel path, the web JobManager, and ReferenceGenome
  (all three held: 0 determinism mismatches, cap never exceeded, 0 wrong bytes over 72k fetches).

- **Benchmark metrics now treat `±inf` as degenerate, closing the gap the NaN guard left one value
  short.** A prior round added a `NaN` guard (`v != v`) so corrupt data couldn't score as perfect,
  but `v != v` is `False` for `±inf`, and `inf` is a finite-*ordering* value — it sorts as the
  largest element and satisfies every `<= 0` / `==` degenerate check. So an `inf` score made
  `spearman`/`roc_auc`/`pr_auc` rank corrupt input as a **perfect** `1.0`, made `pearson` return a
  non-JSON-serializable `NaN`, and *crashed* `expected_calibration_error` with an `OverflowError` on
  `int(inf * n_bins)`. Reachable: the `Prediction` contract admits `value=inf` with an `(lo, inf)`
  interval, so a scorer whose point estimate overflows flows straight into the metrics. Broadened the
  shared guard from `is NaN` to `not math.isfinite` (renamed `_has_nan` → `_has_nonfinite` at its five
  call sites); `NaN` is still caught and finite inputs are unchanged. Regression test fails@HEAD →
  passes; benchmark-harness spec gains a "metrics treat non-finite inputs as degenerate" requirement.
  Found by a benchmark scientific-correctness audit (which verified pr_auc/roc_auc/spearman/pearson/
  ECE/KL, splits, leaderboard, and the generalization gap correct on their edge inputs).

- **`aforge verify` now re-hashes pinned datasets, so a tampered CFD matrix no longer passes
  verification silently.** The provenance-reproducibility spec's tamper contract covers "a recorded
  checkpoint *or dataset*" whose bytes no longer match its pinned hash, but `verify` only re-hashed
  `provenance.models` — never `provenance.datasets`. This was reachable, not latent: the vendored
  Doench-2016 CFD matrix (`doench-2016-cfd`, the default off-target scorer's weight source) is a
  registry dataset that carries a real pinned `sha256`, so every off-target-inclusive design records
  it in provenance with a hash — and a tampered CFD matrix, the scientific heart of off-target
  scoring, was undetectable by `verify`. Added a symmetric dataset loop that locates each pinned
  dataset via the registry cache path and re-hashes it (`unpinned`/`unknown`/`not-cached`/`ok`/
  `MISMATCH`, mirroring the checkpoint checks); `--cache-dir` now covers both artifact kinds.
  Regression test (tampered dataset → non-zero exit) fails@HEAD → passes. Found by an audit of the
  `af verify` reproducibility-contract command against its spec.

- **The web API now honors the user config file, matching the CLI and library.** The
  provenance-reproducibility spec requires all three interfaces to resolve settings through
  `Settings.load()` so the config file (`~/.config/alleleforge/config.toml`) applies to web runs too,
  but the module-level `create_app()` default used a bare `Settings()`, which reads `ALLELEFORGE_*`
  env vars yet silently skips the config file. A machine with a `config.toml` seed/threshold saw it
  govern `af design` and the Python API but not the web server — its provenance stamped the default
  instead, a cross-interface reproducibility gap and a spec violation. `create_app()` now defaults to
  `Settings.load()`. Regression test fails@HEAD → passes; the spec gains a "config file governs a web
  run" scenario. Found by the cross-interface parity audit.

- **The report TSV export now strips carriage returns from cells, so a user-influenced value can no
  longer break one row into several.** `report_to_tsv`'s `_cell` neutralized `\t` and `\n` but not
  `\r`, while its sibling `_batch_tsv._cell` already handled all three. A `\r` in a user-influenced
  cell (a `worst_ancestry` label sourced from population input, or a free-form candidate flag)
  survived into the row — Excel, `str.splitlines()`, and `csv.reader` all treat a bare `\r` as a row
  break, so one logical candidate row rendered as several physical lines and `csv.reader` raised on
  the unquoted line break. Added `.replace("\r", " ")` to match the sibling emitter. The pinning test
  shared the blind spot (it split on `\n` and asserted only `\n`-absence); strengthened it and added a
  direct `_cell` guard over every delimiter. Regression test fails@HEAD → passes; reporting spec now
  names carriage returns explicitly. Found by an adversarial output-rendering audit (whose broader
  sweep of HTML/PDF/SVG/leaderboard/provenance escaping came back clean).

- **A cohort/batch run now records the seed that actually governed it, not the process-singleton
  default.** `design_many` stamped the run-level provenance seed from `get_settings().seed` (the
  singleton), while the seed threaded into every per-item `design()` call comes from the `settings=`
  argument the CLI `batch`/web `/api/batch` pass. So `af batch --seed 999888` recorded a run seed of
  `20240501` (the default) even though every per-item menu correctly used `999888` — the run header
  contradicted the items it summarizes and disagreed with what `af design --seed 999888` records. The
  seed is the reproducibility anchor `aforge verify` reads, so a wrong run seed breaks re-derivation.
  Now stamps `(design_kwargs.get("settings") or get_settings()).seed`, falling back to the singleton
  only when no settings are passed (matching `design()`'s own default). Test-invisible before because
  the suite only exercised the default seed, which equals the singleton. Regression test fails@HEAD →
  passes; provenance-reproducibility spec gains a scenario. Found by a cross-interface parity audit.

- **A `verify=True` content-addressed cache now fails closed when a checksum sidecar is missing,
  so deleting the sidecar can no longer silently defeat tamper detection.** The cache re-checks a
  payload against its `.sum` sidecar on read, but only *when the sidecar existed* — a missing one
  fell through and the unverifiable bytes were served. Since a `verify=True` cache always writes a
  sidecar with each entry, an absent one means an incomplete write or a tamper that removed the
  checksum, so `rm *.sum` bypassed the gate the docstring promises ("a corrupted-on-disk entry
  must never be served silently"). `get_bytes` now raises `CacheIntegrityError` on a missing
  sidecar under `verify=True`. Latent today (production callers use the `verify=False` default),
  but `verify=True` is a public, documented constructor option, so this hardens the integrity
  primitive before it is wired up. Regression test fails@HEAD → passes. Found by a file-path / I/O
  trust-safety audit (whose broader sweep — cohort names, split loader, `--out` paths, cache dirs,
  web job ids — came back clean).

- **The pure-Python FM-index fallback now builds the suffix array in O(n) memory instead of
  O(n²), so a native-less install no longer OOMs on a whole-gene off-target search.** The
  fallback built the suffix array with `sorted(range(n), key=lambda i: data[i:])`, which
  materializes every suffix as a sort key — peak memory Θ(n²), and time degrading to Θ(n² log n)
  on repetitive text (microsatellites, tandem repeats, homopolymers). The off-target engine
  auto-enables the FM path for any search region ≥ 1 Mb with no opt-in, so an ordinary search
  over a gene locus / chromosome arm silently triggered the build — extrapolating to ~500 GB
  peak at n = 1 Mb, well below the 50 Mb size warning. This only bit **native-less** installs
  (the documented norm; the native SA-IS kernel, when built, is linear), which is why the green
  suite masked it. Replaced the direct sort with prefix doubling (Manber–Myers): O(n log² n) time,
  **O(n) memory**, and byte-identical output — verified against the direct sort over the
  parity-text set plus 400+ fuzz cases (the SA is unique because the sentinel makes every suffix
  distinct). Measured at n = 16,001 repetitive: 129.7 MB → 4.0 MB peak (33× less, and the ratio
  grows with n). Found by an algorithmic-complexity audit of the internal (non-web-API) paths.

- **The `aforge offtarget` CLI and `/api/offtarget` endpoint now expose the honest effective
  matrix, so an all-approximation table is no longer mislabeled as published CFD.** The design
  report already reconciles the per-site truth via `OffTargetReport.effective_matrix()` — a
  published matrix falls back to the length-relative approximation per off-register (bulged /
  non-20-nt) hit, and the report shows the matrix the reported sites were *actually* scored by.
  But the two standalone off-target surfaces only surfaced the nominal `score_matrix`: the CLI
  payload printed `doench-2016-cfd` (and its per-site dicts omitted the matrix entirely), and the
  web `OffTargetResponse` projected no effective matrix, so a client reading the top-level label
  read an approximation as published CFD — the same computation labeled honestly on one surface
  and dishonestly on another. Added `effective_matrix` to `OffTargetResponse`, a top-level
  `effective_matrix` plus per-site `score_matrix` to the CLI payload, and an "effective …" note to
  the CLI human line when it differs from the nominal. Regression tests fail@HEAD → pass on both
  surfaces; offtarget-scoring spec gains a scenario. Additive (no existing field changed).

- **Re-calibrating an out-of-distribution prediction can no longer shrink its interval below
  the honesty floor.** `ConformalCalibrator.calibrate` computes `new_half = scale * half_width`;
  when the fitted conformal scale is `< 1` (an over-covering scorer — an ordinary case), an OOD
  input that correctly arrived carrying the `OOD_MIN_HALF_WIDTH` floor came out *narrower* than
  the floor. The `calibrated` flag was correctly reset to `False`, but the width axis was left
  unguarded, so an out-of-distribution prediction could present a narrow, confident-looking
  `method=conformal` interval — the opposite of the "OOD widens, never narrows" contract. The
  OOD branch now floors the multiplicative scale at 1, so recalibration can only widen an OOD
  interval, never shrink it. In-distribution conformal behavior is untouched. The gap was latent
  because the only in-repo caller exercises `calibrate` on in-distribution data only — the same
  "real safety input inert on its consumed axis with a green suite" pattern the audit keeps
  surfacing. Regression test fails@HEAD → passes; uncertainty-contract spec gains a scenario.

- **Ranking weights now reject `nan`/`inf`, so a fat-fingered `--weights` can no longer
  silently corrupt the entire ranking.** `RankingWeights` validated that each weight was
  non-negative and not all-zero, but a bare `weight < 0.0` check lets `nan` and `inf` through
  (both compare `False`). The CLI `--weights` flag (and a config file, and the Python API)
  parse those via `float()`, so `--weights 1,1,1,nan` built a weights object whose
  `normalized()` returns `nan` for every objective — turning every candidate's composite score
  into `nan` and scrambling the order — while `1,1,1,inf` collapsed the finite weights to `0.0`.
  `__post_init__` now rejects any non-finite weight up front. Separately, `_parse_weights`
  constructed `RankingWeights` *outside* its `try/except`, so any validation failure (a negative
  weight today, a non-finite one now) escaped as an uncaught traceback with a success exit code
  instead of a clean `USAGE` error; the construction is now inside the guard. Same NaN-poisons-a-
  score class the benchmark-metrics NaN guard closed, on the ranking axis.

- **The lint CI gate now style-checks the example notebooks, so they can no longer drift out of
  compliance silently.** The `examples` CI job executes the three teaching notebooks end to end
  (`pytest --nbmake`), but the `lint` job only ran `ruff check`/`ruff format --check` over
  `src tests scripts` — never `examples`. Execution passing says nothing about style, so the
  notebooks had accumulated unsorted imports, over-length lines, and formatter drift that a
  ruff-branded project should not ship in its front-door examples. Extended both lint commands to
  cover `examples`, added an `examples/**` pydocstyle exemption (teaching cells need no docstrings,
  matching the existing `tests/**` and `scripts/**` rules), and reformatted the three notebooks
  (import sorting plus wrapping long print-calls). Notebook execution is unchanged (`nbmake` still
  green); this closes the same class of *ungated surface rots silently* gap the reproducibility and
  format-check pins closed.

- **The reproducibility golden is refreshed, so the CI reproducibility gate is green again.**
  `scripts/reproduce.py` re-derives the canonical weight-free design menu twice, asserts the two
  runs are byte-identical, and diffs a canonicalized digest against a committed golden manifest;
  the `reproduce` CI job runs it in diff mode (exit 1 on drift). The golden was last regenerated
  before the Round 3–13 correctness series, and a long run of *intentional, reviewed, test-pinned*
  output changes since then — clamping the default efficiency/probability intervals to `[0, 1]`,
  excluding the guide's own on-target from the off-target report, reflecting patient off-targets on
  the safety axis, attributing a hit by the variant's full span, and giving the default heuristic
  scorers their own honest provenance cards — moved the canonical digest without the golden being
  refreshed. The audit therefore failed on `main` even though the run is still deterministic (two
  runs are byte-identical) and the scientific output is sound (one `base_abe` candidate, efficiency
  `0.6` in `[0.45, 0.75]`, `calibrated=False`, honest `be-dict-baseline`/`pridict2-baseline` cards).
  Regenerated the golden to pin the current correct baseline; the audit now passes.

- **A calibrated `Prediction` survives nesting and a trusted round-trip instead of being
  silently downgraded.** The `calibrated` honesty flag was enforced by *mutating* the built
  model (`object.__setattr__` in an `after` validator) whenever the calibration token was
  absent. Two consequences fell out of that: (1) constructing any container around a certified
  prediction — e.g. nesting one in a `DesignCandidate`/`RankedMenu` — re-ran the validator on the
  shared frozen instance and flipped its `calibrated` flag `True → False`, corrupting the original
  in place and baking `calibrated:false` into the serialized menu; and (2) re-reading AlleleForge's
  own output (`af verify` loading a menu whose JSON says `"calibrated":true`) coerced the flag back
  to `False`, so the load-bearing calibration flag was not faithfully round-trippable. The gate now
  runs in a `before` validator on the *raw input mapping* and never mutates a built instance: an
  already-constructed prediction passes through untouched (no nesting corruption), a fresh
  self-declared `calibrated=True` is still stripped (anti-forgery intact), and a new
  `trusted_deserialization_context()` — supplied only where AlleleForge re-reads its own output —
  lets a genuinely certified prediction round-trip while untrusted JSON still cannot forge
  calibration and the `in_distribution=False` guard still holds. Resolves the round-trip finding
  deferred from the deep-audit method as design-sensitive.

- **Every web-API string and list request field is size-capped, not just the batch count.** The
  web-API hardening promised a per-request size cap, but only a variant *count* cap shipped, leaving
  individual field sizes unbounded — a within-count request could still carry a multi-megabyte
  spacer/variant string or a huge populations list into genome-scale off-target work. Generous
  per-field caps now bound every string and list field at the schema boundary (spacer 512, PAM 64,
  variant 8192, build 128, populations 64, chemistries 16, plus per-element caps), all far above any
  legitimate input, so an oversized field is rejected with 422 before any scan while genuine requests
  are accepted unchanged. Resolves the item deferred in the Round 12 audit.

- **Cross-build liftover rejects a balanced interior chain gap.** `lift_interval` fails closed to
  avoid emitting a "scrambled interval" when a chain indel makes the lifted coordinates "no longer
  describe the same bases," but it lifted only the two endpoints and compared the span length. A
  *balanced* chain gap — a source deletion and a target insertion of equal size — leaves both
  endpoints mapped and the span length unchanged while the interior bases map to nothing, so the
  endpoint-only check passed it and returned a divergent interval as if it were a faithful 1:1 image.
  `lift_interval` now lifts every base of the (short) interval and fails closed on any unmapped base
  or contig/strand split. Also guards `GenomicInterval.to_one_based` on an empty interval (which
  1-based-inclusive cannot represent) with the real cause instead of a misleading bounds error.
  (Round 13 property-fuzzing / liftover / encoding pass.)

- **Text I/O is pinned to UTF-8 and strips a byte-order mark.** Data-layer reads (`open_text`) and the
  CLI/cohort file writes were left at the platform-default encoding while the content is UTF-8
  (`model_dump_json` preserves non-ASCII; a VCF/TSV can carry a BOM). A UTF-8 BOM rode on the first
  field, so `'﻿#…'.startswith('#')` was False and ClinVar header detection / source-assembly
  auto-detection silently broke; and the "lossless" JSON export crashed under a non-UTF-8 locale
  (C/POSIX) or wrote mojibake under Windows cp1252. `open_text` now decodes `utf-8-sig` (stripping a
  BOM), and the per-item cohort write and the CLI `write_text` sites pass `encoding="utf-8"`. (Round
  13 property-fuzzing / liftover / encoding pass.)

- **The PDF is encoded as CP1252 to match its declared WinAnsi font.** The PDF declares its font
  `/WinAnsiEncoding` (CP1252) but `_escape` encoded Latin-1, so ordinary punctuation the font renders
  — a curly apostrophe, en/em dashes, the euro sign — was silently replaced with `?`, data loss on the
  printable reagent leave-behind. Both `_escape` and the content-stream serialization now encode
  CP1252; genuinely unrepresentable scripts still fall back to `?`. (Round 13 property-fuzzing /
  liftover / encoding pass.)

- **Benchmark metrics guard NaN, so corrupt input can't score as perfect.** The metrics module
  promises "degenerate inputs (empty, constant) return `0.0` rather than `NaN` so results stay
  JSON-serializable," but the guards test `<= 0` / `==` / emptiness, none of which a NaN satisfies
  (every NaN comparison is `False`). So a NaN flowed straight through: `spearman` and `pr_auc` scored
  a series containing one NaN as a **perfect 1.0** (a NaN-emitting model would top the leaderboard),
  `pearson` returned a non-JSON-serializable NaN, and `expected_calibration_error` crashed on
  `int(nan)`. Reachable via a NaN on the label side. A shared `_has_nan` guard now returns the
  documented degenerate value at each entry — `0.0` for correlation/AUC, `None` (undefined) for ECE.
  (Round 12 never-audited-surfaces pass.)

- **The Markdown leaderboard neutralizes HTML and Markdown markup.** The reporting spec requires the
  leaderboard Markdown render to escape all submitter-supplied cell content, and `_md_cell` promises
  "a cell can only ever be data" — but it escaped only `\`, `|`, and newlines, leaving
  `<img src=x onerror=…>` (raw HTML) and `[x](javascript:…)` (an inline link) intact on the shareable
  Markdown board, which is active content under any HTML-passing Markdown renderer. (The HTML board
  was already safe.) `_md_cell` now HTML-escapes the angle brackets and ampersand and backslash-
  escapes every Markdown inline metacharacter, so a link, tag, emphasis, code span, or table break
  cannot form, while an ordinary name stays readable. (Round 12 never-audited-surfaces pass.)

- **A figure label can no longer break out of the report's `<script>` element.** `_figure_script`
  inlines the Plotly figure JSON in a `<script>` and escaped only `</`. A figure's x-values are
  user-supplied ancestry/population labels, and a label of `<!--<script>` puts the HTML tokenizer
  into script-data-double-escaped state, so the report's own `</script>` no longer closes the element
  and the rest of the document is swallowed — a crafted label defaces the whole report. Replaced with
  the standard safe JSON-in-`<script>` transform (`<`, `>`, `&` → unicode escapes) the client parser
  restores, so no raw `<` survives inside the script. (Round 12 never-audited-surfaces pass.)

- **Cohort per-item output files are collision-free and written atomically.** `_safe_name` mapped
  every non-`[alnum-._]` character to `_`, so two distinct items whose ids differ only in such
  characters (e.g. `chr1:100:A:T` vs `chr1:100:A/T`, both → `chr1_100_A_T`) shared one output file
  and silently overwrote each other — escalated to a torn write when two collided in flight on the
  parallel path (a plain, non-atomic `write_text`). A short digest of the raw id now makes the
  filename injective, and each report is written via a temp file plus `os.replace` (atomic), so a
  reader or crash never observes a partial file. Resume is unaffected (it keys on the manifest's
  `item_id`). (Round 12 never-audited-surfaces pass.)

- **Patient off-targets are no longer masked on the ranking safety axis.** The safety
  objective is `1 - worst-affected-ancestry off-target score`, and `worst_ancestry()` reads
  `ancestry_stratification()`, which credited only reference sites to every ancestry. A patient
  off-target — certain in this individual's genome, so carrying no ancestry frequency — landed in
  no ancestry stratum, so the moment any benign ancestry-tagged population site coexisted,
  `worst_ancestry()` returned the benign score and the far more dangerous patient hit vanished from
  the safety term: a CFD-0.9 patient off-target reported safety `0.70` instead of `0.05`, and
  *adding* a benign off-target *raised* safety (a monotonicity violation on the axis the module
  exists to protect). Reachable in any `design(gnomad=…, patient_vcf=…)` run, where the population
  and patient passes merge into one report. It survived because the design verticals' tests run with
  `run_offtarget=False` and the ranking tests never mixed a patient site with an ancestry-tagged
  one. `ancestry_stratification` now credits a *certain* site (a reference site or any site with no
  ancestry frequency — i.e. a patient site) to the worst case of every ancestry, the same
  discriminator `expected_burden` already uses, so `worst_ancestry()` equals the genome-wide worst
  and the safety score can never understate a patient off-target. (Round 11 metamorphic /
  guarantee-coverage pass — found independently by two lenses.)

- **The candidate ranking is a true total order, independent of input pool order.** `rank_candidates`
  sorts by `(composite, efficiency, safety, simplicity)` and documented a "total and deterministic"
  order, but two distinct candidates with an identical objective vector exhaust that four-key sort
  and fell to the input pool's assembly order. The spec sanctioned relying on deterministic
  enumeration order (so this was latent, not a live bug), but the stronger self-contained guarantee
  is cheap: a final stable reagent-identity tiebreak (the spacer sequence) now orders full ties, so
  the menu — and its Pareto-front indices — are identical regardless of how the candidate pool was
  assembled. (Round 11 metamorphic / guarantee-coverage pass.)

- **The guide's own on-target is no longer counted as an off-target.** The reference always
  contains the guide's own protospacer, so the genome-wide off-target scan nominated it as a
  perfect (CFD 1.0) match at the guide's exact placement. That self-match pegged every candidate's
  `worst_score` at 1.0 — leaving the ranking safety axis (`1 − worst`) inert at 0.0 for *every*
  guide — and capped `specificity_score` at 0.5 for even a perfectly clean guide, though the
  offtarget-scoring spec promises the CRISPOR/Hsu aggregate, which excludes the on-target. No test
  caught it: the design verticals' tests run with `run_offtarget=False` and the ranking tests build
  synthetic reports, so the real pipeline was never driven with off-target search on. `search()`
  now takes an opt-in `on_target` locus; when supplied it drops the single site at exactly that
  locus (naming-aware on the contig, exact — a *paralogous* perfect match at any other locus is a
  real off-target and is retained) from both the reported sites and the sub-threshold tail. The
  three design verticals pass each guide's protospacer placement. Reproduced end-to-end: pre-fix
  every candidate carried a score-1.0 site at its own placement; post-fix the safety axis
  discriminates and a clean guide reports `specificity=1.0` / `worst=0.0`. (Round 10 adversarial /
  unhappy-path / end-to-end pass.)

- **The haplotype panel reconciles contig naming, so it isn't silently empty.** `HaplotypePanel`
  indexed `_by_chrom` by the raw contig and looked the bucket up by the raw query contig, so a
  bare-named ("1") 1000 Genomes / HGDP panel queried with a chr-named ("chr1") hg38 interval missed
  its bucket and returned no haplotypes — the haplotype-aware off-target pass then ran over an empty
  list and contributed zero sites, the reference-bias fail-open the module exists to catch. The
  Round 3 `reconcile-assembly-coordinates` change made `overlaps` naming-aware and fixed
  gnomAD/ClinVar but never reached here, because the bucket `.get()` runs first. Both the index key
  and the query are now canonicalized via `canonical_contig`, mirroring `GnomadDB`. (Round 10
  adversarial / unhappy-path / end-to-end pass.)

- **The outcome-distribution KL metric is byte-deterministic.** `kl_divergence` summed
  `pk·log(pk/qk)` over a bare `set(p) | set(q)`; set iteration is `PYTHONHASHSEED`-dependent and
  float addition is non-associative, so the KL value's low bits (and the `_normalize` totals) varied
  run-to-run — perturbing the un-rounded metric in the signed `BenchmarkResult` body, against the
  metrics module's "bit-stable numbers across machines" contract. The Round 9 `ensemble_outcome`
  fix closed the sibling; this one was left, saved only by the cross-platform digest's 6-decimal
  rounding absorbing the ~1e-15 noise. The key union is now sorted once (`keys = sorted(...)`),
  fixing both the summation order and the normalization totals. (Round 10 adversarial /
  unhappy-path / end-to-end pass.)

- **The default Cas9 efficiency interval is now clamped to `[0, 1]`.** The wired-default
  `EnsembleEfficiencyScorer` built its predictive interval as `mean ± z·std` (further widened
  out-of-distribution) through `ensemble_prediction` → `to_prediction`, neither of which clamped
  to the efficiency domain — so about 14% of guide contexts emitted an interval bound above 1.0 or
  below 0.0 (e.g. `AAGAAGTTTAGGGCAAAGGGACC` → `[0.45, 1.011]`). Every sibling efficiency/probability
  scorer already clamps; this was the lone unclamped emitter, and the invariant was pinned for the
  base-outcome sibling but not here. An opt-in `bounds` clamp is now threaded through
  `to_prediction`/`ensemble_prediction` (applied after OOD widening; default keeps the helper
  scale-agnostic) and the scorer passes `bounds=(0.0, 1.0)`. (Round 9 invariant-oriented pass.)

- **PE3/PE3b off-target reports keep their scorer/matrix label and sub-threshold tail.** Every
  two-nick pegRNA merges its pegRNA-nick and ngRNA-nick reports via `_merge_offtarget`, which
  rebuilt a fresh report and dropped `scorer`/`score_matrix` (so the "off-target scoring basis"
  line vanished for the flagship chemistry — a published-CFD table looked identical to an
  approximation-scored one) and `subthreshold_score_sum` (so `specificity_score` overstated
  specificity). The merge now carries the scorer/matrix and sums both nicks' sub-threshold tails.
  (Round 9 invariant-oriented pass.)

- **Contig naming is reconciled in the haplotype, gnomAD, and population off-target passes.** Three
  sibling call sites compared contig identity by raw string, so a panel or database named in the
  other style ("1" vs "chr1") than the reference silently matched nothing — gnomAD population
  augmentation went empty and every haplotype/variant was skipped, the reference-bias blind spot
  those passes exist to catch. The same class as the Round 3/7 `_working_interval`/`in_region`
  fixes, three sites they missed. All three now reconcile via `canonical_contig` and rebind to the
  reference's naming (skipping only a genuinely absent contig). (Round 9 invariant-oriented pass.)

- **`ensemble_outcome` merges byte-deterministically.** It built the merged allele distribution as
  a dict comprehension over a `set` of allele names; set iteration is `PYTHONHASHSEED`-dependent,
  so the dict insertion order — and therefore the float summation of `total`, the probability-tie
  order, and `EditOutcome.most_likely` on a tie — varied process-to-process, breaking the
  determinism the provenance contract promises (it failed under 5 of 6 hash seeds). It now iterates
  a sorted allele set with a total sort key. (Round 9 invariant-oriented pass.)

- **The default heuristic scorers carry their own honest model cards.** The default prime, base-edit,
  and nuclease-outcome scorers reported the *trained* model's card, so a default design stamped a
  trained checkpoint (HEK293T/K562 training data, "Trained on…" failure modes) into provenance
  although a transparent heuristic that was never trained produced the numbers — a re-run from that
  checkpoint reproduces different numbers. The cas9-efficiency default already handled this with a
  bespoke card; the other three now get `pridict2-baseline` / `indelphi-mh-baseline` /
  `be-dict-baseline` cards describing the heuristic honestly, while the opt-in trained adapters keep
  the trained cards. (Round 9 invariant-oriented pass.)

- **A population/haplotype off-target is attributed by the variant's full span.** `_touches` tested
  only the variant's anchor position against the hit's protospacer+PAM window, so a multi-base
  deletion or MNV whose *other* changed bases reached the window — while the anchor sat just
  outside — was dropped from nomination, a false negative in the safety-critical path. It now tests
  half-open overlap of the variant's `[pos, pos+ref_len)` span (identical to the point test for
  SNVs). (Round 9 invariant-oriented pass.)

- **The report's "scoring basis" line shows the effective off-target matrix.** It used the scorer's
  *nominal* configured matrix, so a table whose above-threshold hits all fell back to the
  approximation (bulge-collapsed / off-length) still read "published CFD" while every displayed
  score was the approximation — the per-site effective matrix from the Round 7/8 fix was present but
  never surfaced. `OffTargetReport.effective_matrix()` now reconciles the per-site truth (the shared
  matrix when sites agree, both when mixed, the nominal matrix when there are no sites). (Round 9
  invariant-oriented pass.)

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

- **Out-of-range CFD/Cas12a mismatch weights are caught at scoring time.** An
  injected mismatch- or PAM-weight table with a value outside `[0, 1]` previously
  produced a specificity score `> 1.0` that only failed downstream, as an abort in
  the `OffTargetSite` validator. `cfd_score` / `cas12a_cfd_score` now validate each
  weight as it is applied and raise a clear `ValueError` naming the offending weight
  (base substitution and position), so a bad table is a scoring-time error, not a
  late crash. (Part of the in-progress `ship-published-cfd-matrix`; vendoring the
  authentic Doench 2016 matrix as the default remains blocked on an authoritatively
  sourced, cross-verified copy — it must not be fabricated.)

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

- **Ship the PEP 561 `py.typed` marker.** The package declared the
  `Typing :: Typed` classifier and is `mypy --strict` clean, but shipped **no**
  `py.typed` marker — so a downstream type-checker silently ignored every one of
  its types (the metadata claimed typing support the distribution did not deliver).
  Added `src/alleleforge/py.typed` (hatchling bundles it into the wheel and sdist
  automatically) and a packaging test that guards the marker — plus the bundled
  model cards, benchmark splits, and web frontend — against silent removal.

### Security

- **The web app now sends security headers; it sent none.** A Content-Security-Policy is the structural form
  of a promise the project already made in prose — *"the served frontend loads no third-party scripts"* —
  which was violated for as long as the rendered report carried a `cdn.plot.ly` script tag, because nothing
  enforced it. `script-src 'self'` with no inline or `eval` allowance, `default-src 'self'`,
  `object-src 'none'`, `base-uri 'none'`, `form-action 'none'`, `frame-ancestors 'none'`; inline *styles* are
  permitted because the shell and the report each carry a `<style>` block. A `srcdoc` frame inherits its
  parent's policy, so this governs the embedded report too: verified live that an injected
  `<script src="https://cdn.plot.ly/…">` produces **zero network requests**. Also `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer` (a local deployment's URL is not JBrowse's business) and
  `X-Frame-Options: DENY`.

- **The report iframe is sandboxed, and its one external link no longer hands over the opener.** The frontend
  embeds a server-generated report — HTML assembled from user-supplied strings — with `srcdoc` in a frame
  that had no `sandbox`, so it ran with the application's own origin. It is escaped and, since the previous
  entry, script-free; the sandbox is what makes an escaping bug in the renderer unexploitable rather than
  merely unlikely. `allow-scripts`, `allow-same-origin` and `allow-forms` are all denied (the two popup
  tokens keep the report's JBrowse link clickable), and that link gained `target=_blank rel="noopener
  noreferrer"`. Verified live: the report renders, the parent can no longer read the frame, zero off-origin
  requests.

- **Every rendered report fetched a script from `cdn.plot.ly`.** The README, the deployment guide and the
  served page all promise *"no outbound network call"* and *"the served frontend loads no third-party
  scripts"*. `render_html` emitted `<script src="https://cdn.plot.ly/plotly-2.35.2.min.js">`, so a lab
  opening the local UI to analyse a patient variant issued a request to a CDN at that moment — and the web
  frontend embeds the report in an **unsandboxed same-origin iframe**, so that third-party script ran with
  the app's privileges. The module's own docstring defended the choice as "a static script, never sequence
  data"; the request itself is the disclosure, whatever it carries. Charts are now inlined SVG from
  `alleleforge.viz.svg`, the repository's own dependency-free renderer, and a rendered report contains no
  `<script>` element at all. Found by running the web app and reading the DOM; R151's guard had scanned the
  static asset directory, which the generated report is not in, and a separate test had *pinned* the CDN —
  two tests asserting opposite things, both passing.

- **`ALLELEFORGE_API_TOKEN` was inert on the documented deployment path.** The variable was read only inside
  `resolve_serve_token`, which only `serve()` calls — and both the deployment guide and the Dockerfile run
  `uvicorn alleleforge.web.api.app:app`, which binds the module-level app directly. So the guard that refuses
  a non-loopback bind without a token never ran there, and an operator who published the port and set the
  variable believing it protected the service got a **fully open API**: a `/api/resolve` request with no
  `X-API-Token` header returned `200`. `create_app()` now defaults the token from the environment, so it is
  enforced on every path. The deployment guide's quickstart binds `127.0.0.1` (with a documented token form
  for anything else), and `docker-compose.yml` maps `127.0.0.1:8000:8000` rather than every host interface.

- **Bumped PyO3 `0.22.6` → `0.24.2`** in the `aforge_native` crate, resolving
  [GHSA / Dependabot #1](https://github.com/clay-good/alleleforge/security/dependabot/1)
  (risk of buffer overflow in `PyString::from_object`, fixed in PyO3 0.24.1). The
  crate's source already used the modern `Bound` API, so the upgrade was a clean
  dependency bump — verified with `cargo check`, `cargo clippy`, and a full
  `maturin develop` round-trip of `aforge_native.version()`.

[Unreleased]: https://github.com/clay-good/alleleforge/commits/main
