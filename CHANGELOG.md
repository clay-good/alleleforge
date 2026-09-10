# Changelog

All notable changes to AlleleForge are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The
project is in the `0.x` series until the three launch modalities pass
acceptance.

## [Unreleased]

### Added
- **Every surface says whether this install runs the native kernels.** The Rust kernels are held to a parity suite proving they return exactly what the Python implementation returns — the right requirement, and what made them invisible: an install without the extension, or with a **stale** one older than the crate source beside it, produces identical output an order of magnitude slower on the off-target hot path, and nothing said which install you had. `aforge --version` now prints a second line (the version stays alone on the first, for `head -1`), `GET /api/health` reports `native_kernels`, and both read one sentence from `alleleforge._native.acceleration()`. The stale case is called out by name because the kernel it hides is the off-target evaluation path, whose whole safety argument is that parity suite — and those tests skip themselves when the kernel is absent.
- **`--cache` and `--genome-index` say whether they reused anything.** The flag's whole purpose is not recomputing a scan, and its output is byte-identical whether or not any reuse happened — deliberately, since `scripts/reproduce.py` requires a cached run and a computed run to be the same document. So from outside, the flag was unfalsifiable: a key that stopped matching (a genome re-copied to a new path, a namespace version bumped under the user) looks exactly like a warm cache, and the only symptom is a run that is no faster than before. `OffTargetCache` counts hits and misses and `GenomeIndex` counts contig-strands mapped against built, each wording its own account once (`usage()`); `aforge design`, `batch` and `offtarget` print them under `--verbose`, and never in the artifact. The index is the larger stake — a cold build is minutes and several gigabytes per contig-strand on a real genome, a warm map is milliseconds — and the two runs are the same document.
- **Every documented input is executed, not just read.** Four guards read this project's prose and a fifth runs the `aforge` commands it documents — all of them about what a reader *invokes*. What a reader **submits** had no check: the `curl` bodies in `README.md` and `docs/api/web.md` (every request model sets `extra="forbid"`, so a renamed field turns a documented body into a 422, and those models gained or lost fields three times in the last dozen rounds) and the `config.toml` in `docs/api/cli.md` (an unknown key produces a warning nobody sees and a run that silently ignores what the reader asked for). Both are now submitted: the bodies to the endpoints they name, and the config through `aforge design --config`, with every key it sets required to appear in the run's own `config_snapshot`.
- **The examples the served page shows are submitted, not just spell-checked.** A previous round checked that no placeholder *offers a form this deployment refuses* — a check on the shape of the string — and the second half of the variant box's `chr2:71:A>C · 2 71 . A C` answered `unrecognized variant input` for as long as it had been there, because nothing typed it. Every example in an input whose `name` matches a request field is now posted to that field's endpoint and must be readable: the population comes from the page, the `·` and newline separators are split (each is an example a reader copies alone), and a locus no test genome can hold is allowed to fail on the *reference* but never on the parse.
- **A VCF record is finally an input form, on the surfaces that promised it.** The served page's variant box carries the placeholder `chr2:71:A>C · 2 71 . A C`; its help says "Coordinates ... or a VCF record"; `DesignRequest.variant` and `BatchRequest.variants` say it; `aforge design --help` and `aforge resolve --help` say "a VCF record work[s] everywhere". Typing the placeholder into the box the placeholder is in answered `unrecognized variant input: '2 71 . A C'`. A `VcfRecord` is a *Python object* the resolver has always accepted, and the string parser had no pattern for the text form — so three of the four audiences could not use what five documents promised. A data line now resolves wherever a coordinate does: whitespace of any kind between the fields (a row pasted out of a terminal has lost its tabs), trailing QUAL/FILTER/INFO/sample columns ignored, and the ID column carried when it is an rsID. A row whose ALT is symbolic (`<DEL>`, `<DUP>`, a breakend, a spanning `*`) is refused by name rather than called unreadable — the same rows `iter_vcf` skips with a counted reason when reading a file.
- **The committed benchmark data is checked against its generator.** `scripts/make_benchmark_fixtures.py` writes the five dataset fixtures and five frozen splits every score, every split integrity hash and the whole leaderboard read, and claims in its docstring to be "fully deterministic ... re-running produces byte-identical files". Nothing ran it: it is not in `make ci`, no CI job invokes it, and of the nine scripts in the repository it was the only one with zero references anywhere in the suite. A fixture edited by hand — or a generator changed and not re-run — left committed data nothing could reproduce, and the split's recorded dataset hash catches a fixture edited *alone* but not a fixture and its hash edited together. The generator now runs in a temporary tree on every suite run, and the committed files must match it byte-for-byte, in both directions, twice.
- **`ALLELEFORGE_MODEL_USE` — the licence gate is reachable from a shell.** Every model card carries an SPDX-style licence, `ModelUse` is the axis it gates on, and `ModelRegistry.checkpoint(..., use=...)` raises `LicenseError` for a model whose licence forbids that use. Every trained adapter takes the same argument. All of it defaulted to `research` and no shell could set anything else, so a company running `aforge design --trained-prime` loaded a research-only checkpoint with no refusal on any surface — the gate only ever protected a Python caller who already knew to ask for it. The declaration is the operator's (`ALLELEFORGE_MODEL_USE=commercial`, or `model_use` in the config file), never a per-request field: whether the work is commercial is a fact about who runs the tool, which a client of a deployment cannot answer for them. It is recorded in the run's provenance, and a refused model declines with the licence named in the menu's own rationale.
- **`aforge models list` / `models show`, and `GET /api/models` / `GET /api/models/{name}` — the model zoo is reachable from a shell.** The *dataset* registry has been answerable on four surfaces for several phases, all reading one derivation so they cannot disagree. The **model** registry had none: the cards carrying each model's licence, its intended use, its out-of-scope use, its known failure modes and its pinned checkpoint hash were reachable from Python alone — while every trained-model opt-in is a consent gate on those cards, the leaderboard refuses a submission whose card is incomplete, and `GET /api/health` lists which trained models an operator enabled. A user could opt into a model and read nothing about what they were opting into. `model_status()` derives the same presence-versus-permission split the dataset surfaces were corrected for, with one case sharper: a cached checkpoint whose card pins no hash is **not** usable, because the registry refuses to load an unverifiable artifact exactly as it refuses to fetch one — so "the file is on disk" would be the wrong answer, and a test plants a file at that path to prove all four surfaces still say NO.
- **`aforge design/batch/resolve --hgvs` — coding and protein HGVS inputs are reachable from the CLI.** A `c.`/`p.` expression was the one input form no shell could resolve, excused on the grounds that a projector "is not a dependency and has no file a flag could name". Both halves are true and neither is a reason: this CLI offers every other optional capability behind a boolean flag and a named `MissingDependencyError` — `--trained-efficiency`, `--trained-prime`, the Parquet writers, the VCF fast path. The flag targets the *run's* assembly rather than the `hgvs` library's `GRCh38` default, because a `c.` expression projected onto GRCh38 and then designed against an hg19 or T2T FASTA is a wrong locus every later check would take at face value. Without the flag, the refusal now names it — and names the coordinate form for the surfaces that have no such flag, like every other resolver refusal.
- **The web API says which assembly it serves, instead of calling every genome hg38.** `ALLELEFORGE_REFERENCE_FASTA` said which *file* to serve and nothing said which *assembly* it is, so the label was the literal `"hg38"` — and `POST /api/design` resolved every request against that same constant — while the CLI has taken `--build` since it shipped. The label is not decoration: it is stamped into every report's provenance, it is what the off-target engine compares a prebuilt index against, and it is the answer to the question that makes a coordinate a locus, since `chr7:5,530,601` is a different base in hg38 than in T2T-CHM13. New `ALLELEFORGE_REFERENCE_BUILD` (default `hg38`) sets it, `GET /api/health` reports it as `reference_build`, the served page names it beside "reference loaded", and a request may now state its own `build` — matching the served assembly in any spelling is answered, any other is a 422 rather than a result silently relabelled.
- **The privacy guard derives which modules can reach the network.** The check that any no-egress claim must name its exceptions knew those exceptions — consequence annotation and a trained-model checkpoint fetch — from a hand-written list, which is the shape this project has repeatedly found going stale. What cannot go stale is which modules import a network client: four do, and the two that are not request-time exceptions (`data/registry.py`, `genome/reference.py`) are excluded on the claim that only a Python caller invokes them deliberately. That claim is now itself a test — no module under `cli/` or `web/` may call `from_build(` or `from_registry(` — so the day a shell reaches one, the guard fails instead of the privacy statement quietly becoming wrong.
- **`alleleforge.cache_sweep.verify_stores()` — the integrity sweep is a library call.** `aforge cache verify` was built in the CLI, whole: the walk over every content-addressed namespace, the FM-index load and optional reconstruction, the re-hash of every pinned dataset and checkpoint, and the pass/fail/nothing-checked distinction. So a Python caller holding a suspect cache directory — or the web API, or a deployment's own health check — had to reimplement it. That is this project's most productive finding class in its mirror image, produced by the round that closed the same gap for `FMIndex.verify()`, and it is what `SPEC.md`'s sixth principle forbids: "the library is the source of truth; CLI and web are thin shells". The command now renders the library's result and picks an exit code, and a test asserts its body contains no hashing, no store walk and no registry.
- **The cohort's bounded-memory guarantee is now checked, through its premise.** `design_many` opens by promising that "each ranked menu is summarized (and optionally written to disk) and then released, so peak memory does not grow with the cohort size" — the reason `aforge batch` can be pointed at a whole VCF — and `CohortItemResult` says "never the full menu" in its first line. Nothing checked either. Peak memory is not testable here, but what the claim rests on is exact: **no ranked menu, candidate or off-target report may be reachable from a finished `CohortRunReport`.** A new test walks the returned report's object graph and fails if one is, with a companion that smuggles a menu in to prove the walker can see it. Retaining a menu is the single change that would falsify the guarantee, it is the change someone would make for a good reason, and it would be invisible until a 300-variant run on a real genome — a per-item summary is ~540 bytes against 1.25 MiB for a menu.
- **The per-read checksum on the off-target cache now states what it costs.** Turning verification on was argued for at length and priced nowhere. Measured: a stored report is 521 bytes at the median (880 largest) because it holds the nominated *sites* and not the genome they were found in, so re-hashing one is microseconds inside a warm hit of 0.08 ms — against 3.7 ms for the scan it replaces on a 30 kb contig, a ratio that only grows with the reference since the hit is `O(entry)` and the scan is `O(genome)`. A new test pins the *premise* rather than the timing (timings on a shared machine are not baselines, as this repo's own notes say): a cached report must stay small and must not carry reference sequence, which is what makes the check free.
- **`aforge cache verify` reports what the on-disk stores weigh, and that nothing evicts them.** Both cross-run caches are content-addressed and append-only *by design*: a changed input is a new key, which is exactly what makes a stale hit impossible and also means the old entry stays forever. An FM-index over a whole genome runs to several gigabytes per contig-strand, and editing the reference mints a new one beside the old rather than replacing it. That is the right correctness trade and the wrong thing to leave invisible in a tool whose caches a user opts into with a flag, so the sweep that already walks these files now says how large each store is, that none of them evicts, and that deleting any of them is safe.
- **A generated index of the round log.** `openspec/changes/README.md` is this project's primary knowledge artifact and a megabyte of narrative: four hundred and fifty-odd rounds, each with its evidence, its measurements and what it ruled out. That shape is right for writing a round and useless for finding one — a reader asking "has anyone looked at cache integrity" had no way in short of a full-text search over prose that quotes its own historical mistakes. `openspec/changes/ROUNDS.md` is one row per round: its title and the first sentence of the **Lesson** it was written to leave behind, quoted rather than paraphrased and checked to appear verbatim in the round it came from. Generated by `python scripts/round_index.py` (with a `--check` mode) and held to the log by a test, because a hand-maintained index of a thing that grows every round is a list that goes stale by construction.
- **The example notebooks' prose is read by the prose guards.** Eleven kilobytes of reader-facing markdown live in `markdown` cells inside four `.ipynb` files — the coordinate-convention warning among them — and no link, command, flag or module-path check had seen a character of it: every guard called `read_text()`, which on a notebook returns JSON, and `test_examples_teach_the_contract` reads only the *code* cells. The meta-guard added one entry earlier, whose whole subject is documents being invisible, took its population from `git ls-files "*.md"` — blind for the same reason, one file extension over. Both now go through `tests.prose.prose_text`, which unwraps a notebook's markdown; its code cells stay out, since the gate already executes them with `pytest --nbmake`, which is stronger than reading them.
- **Every tracked markdown file is opened by some test, or recorded with the reason it is not.** Three consecutive rounds found a guard reading a subset of this repository's prose — one of two spec directories, every surface except the canonical one, `README.md` + `docs/` and not the `CONTRIBUTING.md` whose broken link that same guard's docstring cites. Each was fixed by editing a list, and the list is the defect: written once by someone looking at the files in front of them, inherited forever. This is the check one level up. It cannot say a document is checked *well* — the guards above it do that — only that it is not invisible, which is the failure mode that kept recurring. `RELEASE.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `openspec/AGENTS.md` and `openspec/project.md` joined the prose corpus in the process; the two recorded exceptions are `CHANGELOG.md` (its own structural guard) and the audit log (which quotes historical mistakes verbatim, so checking its prose against today's code would fail by design), and the archived change folders are excluded as history rather than description.
- **The prose guards read every surface a reader can reach.** The link, module-path, documented-command and snippet-import checks scanned `README.md` + `docs/` — the population of the round that wrote them, not of the question they ask. They now also read `CONTRIBUTING.md`, the two root specs, the seven planning documents in `specs/`, and `src/alleleforge/benchmark/README.md`, which the top-level README links to and which carries the submission snippet a would-be leaderboard entrant copies first. (`openspec/changes/README.md` stays out: it is the audit log and quotes historical mistakes on purpose.) The sweep over the new files is clean, which is the good outcome and not the point — the constraint is what stops the next rename from landing there unseen. That package README also still described the board as displaying "accuracy, calibration and split version", which has been three of five since the out-of-distribution share was added and four of five since an unrankable entry started being listed rather than ranked.
- **The specification guard reads both specification directories, and checks that a spec's cited proof exists.** `test_the_specs_name_real_things` swept `openspec/specs/` and not `specs/` — seven more requirement documents (the readiness assessment, the model- and scorer-integration plans, the distribution plan) citing the same identifiers with, in this guard's own words, "the most authority and the least readership". The sweep over them is clean apart from exemptions worth recording: upstream PRIDICT2 symbols the integration spec names because AlleleForge would have to call them, third-party packages the distribution plan names as dependencies or as things deliberately not taken on, base-editor *names* (data, like the PAM motifs already exempted), and `--timestamp` — a flag the readiness assessment names in order to say a user must not be able to forge a run's clock, now recorded as deliberately absent with a companion check that it stays absent. New: specs cite tests as their evidence, and this repo renames tests as it sharpens what they claim, so every `test_…` a spec names must resolve to a test function or a test file.
- **`aforge cache verify` covers all four stores, not two.** Its first version swept the two caches holding *work* a run reuses — the off-target reports and the FM-indexes — and said nothing about the two holding pinned *artifacts* it was given: the dataset cache, the checkpoint cache, and the datasets that ship inside the installed package. Those are re-hashed on every resolve, which is stricter than either work cache and just as reactive, so a damaged checkpoint still announced itself in the middle of the run that needed it — the exact defect the command was written to fix, in the command that fixed it. Sweeping two of four while reporting "ok" is also the honesty failure this project spends its effort on, so the output now separates three things it used to blur: a pass, a failure, and **nothing checked**. An unpinned artifact or a pinned one that is not on this disk is counted apart with a sentence saying so, since almost none of the registry ships or is downloaded by default and absence is the ordinary state of most of that list.
- **`aforge cache verify` — the two on-disk stores a run reuses work from can now be checked before a run instead of during one.** Each already knew how to detect a corrupted entry and neither could be *asked*. The off-target report cache re-checks its checksum only when a design happens to read that entry, so a damaged cache announces itself in the middle of the run that needed it. The FM-index gets constant-time structural checks on load, and those are honest about their reach — a flipped byte leaves every structural fact intact — while `FMIndex.verify()`, which reconstructs the text and re-hashes it, is the only check that catches an index reporting positions that are not occurrences. It is `O(n)`, so it cannot run on every load, which is exactly what a command is for; there was no command, only a Python method, in a tool whose users are told to use a CLI. `--deep` runs it, and a sweep without it says the indexes got their structural checks only rather than printing "ok". Nothing is repaired or deleted: both stores are content-addressed, so removing a named entry is always safe, and which to remove is the operator's call.
- **The cohort table has both encodings now: `aforge batch --summary-parquet` and `POST /api/batch?format=parquet`.** The per-candidate table — the one a human scrolls — has shipped as TSV *and* Parquet for months. The cohort table, one row per patient and hundreds of rows long, is the more pipeline-shaped of the two and had only the text form. `BatchFormat`'s own docstring recorded the deferral and named its price: adding Parquet meant a writer **plus** the guard that its columns match the TSV's in order, this project having already shipped two tables of the same numbers disagreeing about their columns. Both exist now. `COHORT_COLUMNS` and `COHORT_COLUMN_TYPES` are declared once and both encodings are built from them — types declared rather than inferred, for the reason the per-design writer records: on a real cohort the first rows are not representative, so an inferred schema either fails or gives two runs of the same tool files a pipeline cannot union. Numbers stay numbers; the three structured columns render exactly as the TSV renders them, including `offtarget_sources`' "reference-only", so the two encodings cannot disagree on the one axis where "we did not look" must never read as "we looked and found nothing". The `#` note block travels as file-level key/value metadata, ordinal-prefixed so sorting the mapping reproduces the document order.
- **`GET /api/jobs/{job_id}/result?format=…` — a finished job is a result you can ask for, in every format its blocking twin offers.** The async doors are the ones the documentation sends a client behind a proxy timeout to, and the ones the served page uses for a cohort. They returned **one** rendering — the JSON envelope `GET /api/jobs/{id}` carries — of the six `POST /api/design` has and the two `POST /api/batch` has. So the client whose run is long enough to *need* a job was the only one who could not have the PDF, the flat per-patient table, or the untruncated menu shipped a round earlier. The page showed what that cost: **Download TSV** re-`POST`ed the whole cohort to the blocking `/api/batch?format=tsv` — the endpoint the comment three functions above it says "fails exactly on the cohorts this panel exists for" — spending the entire run again (its own note measures a 300-variant cohort at 3m 40s) to format a result already sitting in the browser, over a connection the panel had already concluded could not be held open that long. A job now stores everything its result can be *rendered* from rather than the one document the envelope carries, and the synchronous endpoints and the job result share one renderer apiece, so an async client cannot be handed a different document than a blocking one. `409` while a job is unfinished or failed (carrying the failure reason), `422` for a format that kind of job does not have — a cohort has no PDF, and says so.
- **`POST /api/design?format=menu`, `aforge design --format menu`, and a "Download full menu" button — the full outcome spectrum reaches the browser and the file system.** Every truncated outcome table says the rest of the alleles are on the ranked menu and names `aforge design --json` — a *terminal* command, rendered into the HTML the served page displays, to the audience the README describes as "users who will not touch a terminal". And there was nowhere for it to point: **no HTTP route returned the menu** — not any `format`, not the async job result, since every one is built from a `DesignReport`, which is where the truncation happens. Verified by driving the page in a browser and capturing what "Download JSON" writes: `outcome_top: 3` of `n_outcome_alleles: 4`. The new format returns the menu uncapped and untruncated, as a `Response` so `response_model=DesignReport` cannot reshape it into the thing it is not, and the page offers it beside the report — two documents on purpose, the report being the richer presentation and the menu the richer data. Confirmed end to end in a browser: the downloaded file carries `intended`, `scaffold_incorporation`, `partial_rtt` and the withheld `indel`. The shell-parity guard then failed, correctly: the two shells were spelling one capability two ways. The CLI could produce the menu — `--json`, fixed a round earlier — but only onto stdout, so it was the one output with nowhere on disk to land and no provenance sidecar. `menu` is now an `OutputFormat` too, written and sidecar'd like every other format; `--json` remains its stdout shorthand.
- **A command named inside a message the tool prints must be one the tool has.** Command references have three populations — `--help` text (guarded by `test_help_text_names_real_flags`), the documentation (guarded by `test_a_documented_command_survives_a_shell`), and the *remedy inside a refusal*, which nothing looked at. A rename of `--chain`, `--from` or `--to` would leave the build-mismatch refusal — the one whose whole purpose is stopping a design at the wrong place in the genome — pointing a stuck user at a command that does not exist. The new guard reads every `aforge …` out of the string literals in `src/` and checks the command and its flags against the real CLI, taking the longest matching command path so `aforge bench run --out` is not read as the `bench` group's. It is honest about its reach: it catches the name being wrong, not a command that exists and does the wrong thing. Written after running all fourteen mentions by hand — seven distinct commands, all working, including all three routes the build-mismatch refusal offers.
- **A CI job that runs the contributor path end to end: `make install` then `make ci`.** Two rounds found the same defect twice — the documented install could not run the test member (missing `core`, so `pytest` failed at collection) and then could not run the docs member (missing `docs`, so `mkdocs` was not found) — and **CI could not have caught either**, because every job installs its own subset and runs one member. That is right for parallelism and blind to the question `CONTRIBUTING.md` makes a promise about: can the command we tell a newcomer to run, run the gate we tell them to run? No job built the environment the question is about. The new `gate` job does, duplicating work on purpose. `test_gate_mirrors_ci` records why it is not mirrored locally (mirroring it would be circular — it *is* `make ci`), and a second test pins it to exactly those two commands, so narrowing it back into a per-member job cannot happen quietly. Verified by hand first: a clean venv built from the documented extras runs `make ci` to exit 0.
- **"Check a spacer" — the served page can now run a standalone off-target search.** The guard added a round earlier recorded `POST /api/offtarget` as a **GAP, not a decision**: `aforge offtarget` is a first-class command, the endpoint is a first-class endpoint, and checking a guide you already hold is the commonest off-target question there is — but the page could only run the search *inside* a design, so the one audience with no terminal could not ask it. The new tab posts to `/api/offtarget` and renders the site count, worst score, specificity, expected burden and the effective scoring matrix, with the search-budget sentence, the coordinate convention and the disclaimer that travel with every other surface. The ancestry table shows the frequency-weighted burden **beside** the per-ancestry worst score rather than the worst score alone, because a CFD score is a property of the sequence and not of who carries it, so the worst-score column is usually identical across ancestries and reads as "risk is spread evenly" — the opposite of the finding this search exists to reproduce. The on-target locus is four inputs (contig / start / end / strand) rather than one `chr2:1000-1020(+)` box: the API takes a structured locus, so a text box would mean a second coordinate parser in the page, and the label carries the 0-based half-open convention where a reader sees it. Verified in a browser end to end — the search returns 3 sites, giving the on-target locus drops it to 2 and lifts specificity from 0.354 to 0.549, and a pasted FASTA header comes back as the sentence the API refuses it with. `OffTargetRequest` is now held to the same field-parity rule as the other two panels.
- **A parity guard for the one shell pair that had none: the API and the page it serves.** The project guards library→CLI, library→web *request fields* and benchmark→`aforge bench`, each on the stated principle that a gap must be a decision rather than an oversight — and nothing checked *endpoints*, so the served page reached five of eleven with no reason recorded for the other six. Five are decisions and now say so; one is recorded, in those words, as a **GAP, not a decision**: `POST /api/offtarget` has no page surface, so the audience with no terminal cannot check a spacer it already holds, which is the commonest off-target question there is. Each reason must begin `decision:` or `GAP,` and run longer than a line, because an allowance list is where a gap goes to look like a choice. Four of the guard's checks keep the list honest rather than the code: no reason may outlive its endpoint, none may excuse an endpoint the page does reach, and the reader must find a real `fetch` or it is measuring nothing.
- **`POST /api/jobs/batch` — the async path now covers the operation that actually takes minutes.** The job machinery was wired to the single design, which finishes in seconds, and not to the cohort, which does not: a 300-variant run through `POST /api/batch` held one connection for 3m 40s, past any ordinary reverse-proxy or browser timeout, and this project's stated cohort size is larger than that. The only way to run a cohort over HTTP was the one way that cannot survive it. Submitting returns `202` and a job id, polled at the same `GET /api/jobs/{job_id}` a design job uses. The status endpoint serialized its result with `isinstance(result, DesignReport)` — correct while a design was the only job kind, and silently wrong the moment it was not, since a cohort job would have reported `done` with `result: null`; it now names both shapes. Both entry points run the cohort through one function, so the two doors cannot come to disagree about which configured sources a run was given — a mistake this endpoint has already made once.
- **`aforge bench gap` — the cross-cell-type generalization gap, which no shell could reach.** `benchmark.generalization_gap` is exported, tested, plotted in the paper and reported by the calibration study; it is the question a cross-context split exists to answer, since a single test-split number says how a model does on the contexts the benchmark happens to hold out and not whether it transfers at all. From any shell there was no way to ask it. The command scores an in-context fold and a held-out one, prints both values and the orientation-corrected gap (positive always means worse held-out, whichever way the primary metric ranks), carries the same synthetic-fixture caveat `bench run` does, and refuses an unknown fold with a usage error. The benchmark package now has the guard the design entry point has had since three of its capabilities went missing the same way: every exported operation is a command or a recorded reason.
- **The ancestry axis now says how *often*, not only how *bad*.** `ancestry_stratification()` reports the worst-case CFD score per ancestry — and a score does not depend on ancestry, only on the sequence. So on the reference-bias finding this engine exists to reproduce, the CLI printed `worst off-target score by ancestry: afr 1.000, amr 1.000, nfe 1.000` over carrying frequencies of 0.105, 0.012 and 0.001: three identical numbers, reading as risk spread evenly across populations, which is the opposite of the published finding and of the site line beneath it. The blindness was already named one method up — `expected_burden`'s docstring says it separates a rare-variant off-target from a universal one "which the frequency-blind `worst_score` and `specificity_score` cannot" — and the ancestry axis, the one thing the population-aware search is for, was reported with the frequency-blind statistic. `ancestry_expected_burden()` is the frequency-weighted companion, on the CLI (human and JSON), the HTML and PDF reports, and `/api/offtarget`. Added, not substituted: `worst_ancestry` still drives the ranking safety axis untouched, because "is there a dangerous site at all" and "how often is it actually there" are two questions and only the second had no answer.
- **What ClinVar says about the variant now reaches every surface, not only the prose ones.** The classification is why anyone types an accession rather than the coordinates it stands for, and it reached the menu rationale — so the HTML, PDF and report JSON — and nothing else. `aforge resolve`, whose whole job is saying what an input means, reported `source: clinvar` and not one word of what ClinVar said; the flat TSV and Parquet showed a table of pegRNAs correcting a variant that could equally have been Benign; the cohort summary, the artifact a run of accessions produces, had no column for it. All of them now state it, with the review status alongside on `resolve` (the same class "reviewed by expert panel" and "no assertion criteria provided" is very different evidence), and an absent classification stays distinct from a benign one.
- **A caller-supplied source is marked as one.** `--gnomad`, `--clinvar` and `--haplotypes` are pinned in provenance by content hash like any other dataset (`--patient-vcf` deliberately is not — fingerprinting it would put an identifier for a person's genotypes into a shareable report — but it is marked too, since it is the one row that can never be re-checked from anywhere), and `aforge verify --cache-dir` went looking for them in the registry cache — where they can never be, since the bytes are on the caller's disk — and reported `not-cached`, which reads as "you have not fetched it yet". Nothing is fetchable there. `DatasetVersion.caller_supplied` now records the difference: verify reports `caller-supplied` and names the check the reader *can* run (compare the file's SHA-256 with the recorded one), and the provenance footer every render shares marks the row, because reproducing a run that used one means obtaining that same file rather than fetching a release.
- **`aforge verify` now says how much it actually checked.** It already refused to call a run verified when it had re-hashed *nothing* — the note exists and its comment says why. The partial case was never written, so a real run (two baseline models with no checkpoint hash, plus a user-supplied ClinVar release that lives on the caller's disk and can never be in the registry cache) re-hashed one artifact of four and closed with the same sentence as a fully checked run. It now states the coverage and names what it did not check. Each row also says whether it is a `model` or a `dataset`; every row previously began with the word "checkpoint", datasets included, while the line above them counted the two separately.
- `aforge lift` and `aforge verify` appear in the CLI reference's own command table, and `--format` there lists Parquet. Both commands were shipped, tested and documented in the README — and absent from the page a reader opens to find out what the tool does. The guard that exists to catch undocumented commands concatenates the README with every page under `docs/`, so a command named anywhere counted as documented everywhere; the table is now checked as its own surface.
- **The flat table now says what it is a table of.** `DesignReport` carries nine fields and the TSV/Parquet notes were built from two, so the format a scientist opens in a spreadsheet and forwards showed a ranked list of pegRNAs with no statement of the variant they edit, the intent they were designed for, or the ranking weights that produced the `rank` column they are sorted by — all three of which sit on the HTML and PDF header line. The `locus` column was not the missing fact: it says where each *guide* sits, and an accession input makes the gap plain, since no locus in the document is the edit.
- **A cohort row now says which variant it is about.** `item_id` is the string that was typed: an accession or an rsID names no locus, and left-alignment routinely moves a coordinate away from what was typed — so the summary TSV, the per-item menu JSON, `/api/batch` and the browser's cohort table all identified a row by an input string and nothing else. `RankedMenu` carries the resolved variant (a menu did not say what it was for; `build_report` takes the variant from *its* caller, which is why the single-design path looked complete), and every cohort surface shows it beside the input. The browser table's first column was even *headed* "variant" while holding the input; it is now two columns.
- The cohort run header pins the datasets its items actually read, in a deterministic order, so a cohort resolved through a ClinVar release names that release and one made population-aware by a gnomAD file names that file. It pinned the reference genome's shape and nothing else, while every per-item menu recorded the lot — and nobody opens 500 menus.
- **The four trained models are reachable over HTTP and from the served page.** `design()` takes five scorer overrides; the web-parity guard excused all five as "a Python object, not expressible in JSON" — true of the object, and beside the point, since `aforge design --trained-efficiency` had reached the same capability with a boolean all along. Every menu the API returned was scored by the weight-free baseline, and nothing on it said so or that a trained model existed. The operator lists what this deployment offers (`ALLELEFORGE_TRAINED_MODELS`, or `create_app(trained_models=...)`) because the weights are a consent-gated download onto their disk; a request picks one per call with `trained_efficiency` / `trained_outcome` / `trained_base_outcome` / `trained_prime`, the same names the CLI uses as flags. `GET /api/health` lists them under `trained_models`, the page's *More options* panel greys out the ones this deployment lacks, and asking for one that is not enabled is a 422 rather than a silent fall back to a different model.
- **`--clinvar` and `--dbsnp` on `resolve`, `design` and `batch`**, so a ClinVar accession (`VCV…`) or a dbSNP rsID (`rs…`) is a usable input on the command line. Every shell had refused both on the grounds that the lookups were "Protocols with no shipped implementation" — `ClinVarDB` and `DbSnpDB` had shipped all along, exported and tested, satisfying those Protocols method for method. They are file-backed like `--gnomad`: nothing downloads a release, you supply one. The project's own flagship example, `aforge design VCV000012345`, had never run. With the flag, ClinVar's classification reaches the menu rationale, which is the whole reason to type an accession rather than the coordinates it stands for.
- The lookup release a run resolved through is now pinned by content hash: in the menu's provenance `datasets`, and under `resolved_from` on `aforge resolve --json`. Two dbSNP builds can place one rsID at two loci, and naming the input *form* ("rsid") could not tell those two runs apart.
- **Download TSV** on the cohort panel: `/api/batch` renders the flat per-patient table and the page could only take away the nested JSON, though a cohort is exactly the result someone opens in a spreadsheet.
- **Download HTML** on the served page: the one rendering it could not give you was the one it was showing you, through a fixed 1400px frame onto a report that is routinely tens of thousands of pixels tall. The page now also says the frame is not the whole report.
- A deployment can enable off-target scan reuse (`ALLELEFORGE_OFFTARGET_CACHE`, `ALLELEFORGE_GENOME_INDEX`, or `create_app(...)`), and `GET /api/health` reports which under `scan_reuse`. The shell-parity guard had recorded reuse as the operator's call rather than the client's while no operator could make it.
- `aforge design` and `aforge batch` can reuse a reference scan too (`--cache`, `--genome-index`), which is what the cross-run cache was built for — a cohort re-runs the same guide against the same reference constantly. Neither changes a result.
- `aforge offtarget --cache` and `--genome-index` expose the two ways to avoid repeating a reference scan — a cross-run report cache and a persistent memory-mapped FM-index — which existed, were parity-tested, and could be reached only from Python.
- The scope decision that says which trained adapters are real models and which are deliberate placeholders is now checked against the code: a supported model must implement a forward pass, an out-of-scope one must not, and a newly added adapter cannot go unclassified. One integration spec's header had claimed for three months that work its own execution log recorded as shipped was still next.
- Consequence annotation over HTTP and in the served page, behind two keys: the operator enables it (`ALLELEFORGE_VEP`) because their server makes the outbound request, and the client asks per request (`annotate_consequence`) because the variant is theirs. `GET /api/health` reports `vep_enabled`, and a deployment that enables it stops claiming that no sequence data is transmitted externally.
- `--vep` on `resolve`, `design` and `batch` annotates the variant's predicted molecular consequence, the last thing `design()` could do that no command-line user could reach. `design()` now refuses a resolver backend it would have silently dropped, which is why no such flag could have worked before.
- The readiness assessment's list of what no CLI user can reach is now derived from the code instead of remembered: every entry on the old list had shipped to the command line within two days of it being written, and its verification numbers were three months stale.

- **Nine capabilities the API accepted and the served page could not ask for.** `readForm()` sent five
  fields; `DesignRequest` has fourteen. Four of the missing ones changed what a run could *reach*:
  `allow_ng` / `allow_spry` (without them a locus with no NGG guide returns an empty menu and the page
  offered no remedy), `cell_context` (the input that raises the out-of-distribution flag on a prime
  efficiency prediction), `chromatin_track` — which the status line *already named for this deployment*,
  so the page was listing a capability it could not use — and `vector_scheme`. All four are now in a
  *More options* panel, the track list filled from `/api/health` and disabled when the deployment has
  none. The remaining four are recorded with reasons, and the check reads the request body the page
  actually builds, so a field added to the API and not to the page fails in the suite rather than in
  someone's browser.

- **Removed a stray file named `G` from the repository root.** One line of captured stderr — `error:
  unrecognized variant input: 'chr1:144500000:A'` — from a shell redirection typo during an earlier
  round, swept in by a `git add -A` and shipped in every clone since. Nothing was going to notice: it
  broke no test, imported nowhere, and a one-character filename is the least conspicuous thing in a
  listing next to `CHANGELOG.md`. The root now has an explicit inventory — every tracked file named with
  what a repository root has it for — so a stray is a failing test and a genuinely new root file is a
  decision.

- **An on-target exclusion now says how much it removed.** `--on-target` drops the guide's own
  protospacer from the count, correctly — and nothing constrained how wide that interval may be, so
  `--on-target chr1:0-3000` excluded every nominated placement and reported `0 site(s), specificity
  1.000`, byte-identical to the same guide excluded precisely. The realistic mistake is a gene span
  pasted instead of the 20-nt protospacer, or a liftover that returned a generous interval, and the
  result is a guide that looks perfect. Every other route to that number on this report explains itself
  — an unsearchable scope, a hidden sub-threshold tail, a source that contributed nothing — while this
  one said `on_target_excluded: true` and no count. `OffTargetReport` now carries
  `on_target_excluded_placements` and the search description states it, so it reaches every machine
  surface; nothing is said when nothing was excluded. Export schemas regenerated.

- **A cloning vector no candidate could use now says so.** `--vector-scheme px330-bbsi` on an all-prime
  menu is inert: an sgRNA acceptor has no pegRNA 3'-extension overhangs, so every candidate stays on the
  pegRNA acceptor — deliberate, since failing the whole report would be worse. The consequence is that a
  pX330 user's inserts were screened for **BsaI**, not their BbsI, and the only signal was a scheme name
  they would have to notice differed from the one they typed. This report states an inert input
  everywhere else it has one (a cell context prime alone consumes, a PAM fallback only the nuclease takes);
  a vector is the same shape with a sharper consequence. The rationale now names the requested vector, the
  scheme used instead, and the enzyme the screen did not run against — and says nothing when the vector
  was used or no oligos were built.

- **The empty-interval rule is now enumerated rather than claimed.** Three surfaces take an interval
  from outside the process — a locus string, a web request region, a BED row — and each refuses a
  zero-width one in its own words. They agree today; the BED reader did not until the previous round,
  and `GenomicInterval.parse`'s docstring had claimed to be "shared by every surface that accepts a locus
  from a user", which was true of the surfaces its author had in view. The surfaces are now a list a test
  walks, so a fourth one has to appear there, and each is checked to refuse an empty and an inverted
  interval and to accept a real one.

- **Fixed: `chr1:100-100` was a usage error and the same interval in a BED file was accepted.**
  `GenomicInterval.parse` refuses an interval naming no bases and says why it exists — "shared by every
  surface that accepts a locus from a user, so the CLI and the web API cannot drift into accepting
  different spellings". The BED reader was written inline in `cli/main.py` and constructed intervals
  directly, so it never reached that check: one command, one restriction, two answers — and a scope of
  zero bases reports every guide as perfectly specific. BED reading moves to
  `alleleforge.genome.read_bed_intervals`, both spellings go through one function, and a malformed row
  is refused by line number (a panel file is long, and "invalid literal for int()" is not a location).

- **`aforge offtarget --json` now carries the search description.** A BED panel of zero-length intervals
  restricts a scan to nothing, and the tool catches it: the human line reads "NO SEQUENCE WAS SEARCHED —
  … this is not a clean result, it is an empty one". Two of the three machine surfaces carried that
  sentence — the design report's JSON in `offtarget_search`, the web response in `search_description` —
  and the CLI's own payload carried `searched_bases: 0` and no sentence. Its comment says exactly why
  that number is there, so the inputs to the inference shipped and the inference did not, on the surface
  most likely to be scripted against. The sentence now sits beside the structured budgets, and one guard
  covers all three surfaces.

- **`POST /api/batch?format=tsv` serves the per-patient table.** The summary having moved into the
  library, the cohort endpoint can now return the same file `aforge batch --summary-tsv` writes — one
  row per person with the disclaimer, the coordinate convention, the reference identity and the seed —
  instead of leaving an HTTP client to rebuild the flattening and the note block. Both shells call one
  function, and a test asserts their headers are byte-identical. No `html`/`pdf` (a cohort has no single
  document) and no `parquet` yet, with the reason recorded on the enum: there is no cohort Parquet
  writer, and adding one needs the guard that its columns match the TSV's in order — a defect this
  project has shipped once already.

- **The cohort summary moved out of the CLI into the library.** About 170 lines that flatten a
  `CohortRunReport` into one row per patient and lead the table with the research-use disclaimer, the
  coordinate convention, the reference genome's identity and the seed — all of it in `cli/main.py`, in a
  project whose README says of both shells that they carry "no business logic of its own". That table is
  a product: it is the file a run over a patient VCF gets forwarded in, and a Python caller had to
  re-implement it, note block included, while `/api/batch` could not serve it at all. The single-design
  flat table went through this same correction on the argument that a flat table is what a pipeline
  reads; a per-patient table is more pipeline-shaped than that one. Now `alleleforge.design.cohort_rows`
  and `cohort_to_tsv`, called by the CLI, with the two existing guards (API-reference coverage and
  package re-export) catching the new public module on the first run.

- **Fixed: the build-mismatch refusal offered one remedy, usable by one of three callers.** It is raised
  in the resolver, so it reaches a Python caller of `resolve()`, an `aforge design` user and an HTTP
  client alike — and it named only `aforge lift`. A library caller has `Liftover.from_chain_file` and no
  reason to shell out; an HTTP client has no shell on the server and there is no lift endpoint. This is
  the refusal whose whole purpose is stopping a design at the wrong place in the genome, so it is the
  last one that should leave two of its three audiences without a next step. It now names all three,
  including that HTTP callers must lift before sending — and a guard fails if a lift endpoint is ever
  added, since the message would then be stale.

- **Fixed: `aforge offtarget --scorer mit` refused with a Python keyword as the remedy.** One of the
  three advertised scorers fails on the default bulge budget — correctly, since the MIT score is
  undefined for bulged alignments — and the message said "set dna_bulges=0 and rna_bulges=0", which is
  not something a command line can be given. Worse than it looks: that refusal is what a caller meets the
  *first* time they choose that scorer, and the check was deliberately moved out of the CLI into the
  engine so every caller would reach it, which makes a Python-only spelling reach further. It now names
  both spellings, and a guard runs each CLI-reachable refusal, checks it offers no bare `keyword=value`
  outside quoted code, and runs the remedy it names to confirm it works.

- **Fixed: the flagship CLI example in the README could not run.** `aforge design VCV000012345
  --reference-fasta hg38.fa …` answers `error: resolving a ClinVar accession requires a clinvar=
  database`. `ClinVarLookup` and `DbSnpLookup` are Protocols with no shipped implementation, the CLI has
  no code path that constructs one, `create_app` takes no such argument, and the registry lists no
  fetchable ClinVar or dbSNP release — so three of the five input forms the argument help advertised
  cannot be used from either shell, and two CLI examples plus one `curl` example used the first of them.
  The refusal made it worse by naming `clinvar=`, a *Python keyword argument*, to a caller who arrived
  from a command line. It now says no shell can supply a lookup and why, and names the coordinate form
  every surface accepts; both argument helps say the same; the examples use coordinates; and a guard
  rejects any documented shell example whose input form that shell cannot resolve unaided. The Python
  snippets that pass `clinvar=clinvar_db` are correct and stay.

- **The site-rows note now names the population-aware fields.** It listed "locus, PAM, mismatch and
  bulge counts, per-site score and matrix" — every one of which exists, and which left out `origin`,
  `ancestries` and `frequency`: the columns that separate a rare-variant off-target from a universal one,
  and the reason this tool exists. An accurate enumeration that omits the important entries reads as a
  complete description of the row. The guard now checks both directions — every field the note promises
  exists on `OffTargetSite` and is populated in the export the note names, and the population-aware ones
  are named.

- **Fixed: one page said 30 candidates are missing from the exports, and that none are.** The report has
  two caps meaning opposite things about the data. `max_candidates_per_chemistry` removes candidates
  during ranking, before the menu exists, so they are in no export — its note says so. The render cap
  draws the top 50 plus the Pareto front and everything is still exported, and its note said "no export
  is capped — every candidate is in the JSON report": true of the render cap, and phrased as a claim
  about exports in general. With `--max-per-chemistry 60` on a 90-candidate menu both fire and a reader
  gets both sentences. Scoping the second to *this menu* makes them true together, which they always were.

- **`aforge resolve` now says that its own output is not its own input.** It prints `chr1:1017:T>A` for
  the input `chr1:1018:T>A` and said only "coordinates 0-based half-open (BED-style)" — a statement about
  loci, which is true, and which intervals satisfy by round-tripping unchanged. The variant is the one
  printed locus that does not, and `resolve` is the command whose entire purpose is handing a caller a
  normalized variant, so it is the surface most likely to have its output pasted straight back in. It was
  the last one saying nothing, after the refusal message and both renders had been given the sentence.

- **The example notebooks now state the coordinate convention they encode.** Both notebooks that print a
  resolved variant had the 1-based-in / 0-based-out conversion right and unexplained — `chr2:71` for the
  base at offset 70 in one, a bare `EDIT_POS + 1` in the other — and then printed a position one lower
  than the string the cell above built, with nothing said. A reader who copies that printed variant
  designs one base away: the failure `aforge resolve` now names in its refusal and both renders carry a
  note about, absent from the file people are most likely to paste from. Pinned by the notebook-contract
  test, over prose as well as code, since markdown is where a reader will actually meet it.

- **Fixed: a failed async job reported the running progress value, forever.** `progress` is documented
  as three values — "0.0 queued, 0.1 running, 1.0 finished" — with an explicit instruction to render it
  as a state rather than a percentage. The 0.1 is assigned on entry to the run and only the success path
  replaced it, so `{"state": "error", "progress": 0.1}` showed as *running* to any client that followed
  that instruction, for a job that had finished and would never advance. `state` was right the whole
  time; the field the documentation says to display was not. A terminal job now reports `1.0` whatever
  kind of terminal it is, and the field's description says so.

- **Fixed: printing the HTML report cut 340px off every cloning duplex.** The report had no `@media
  print` rules at all, and the oligo block is a horizontally scrolling box — an affordance paper does not
  have. Measured at a 624px print column, with the print rules applied and removed on the same page: 876px
  of sequence in a 536px box, so 340px hidden on screen and 0px with the rules in place. That is the third
  route by which this report has handed someone a truncated sequence, after the PDF's right margin and its
  page breaks. Sequences now wrap on paper (recoverable) while still scrolling on screen (so a copyable
  sequence stays on one line); candidates, figures and tables are kept off page seams; and the panels that
  separate a cloning-lethal warning from a footnote are marked to print, since browsers drop backgrounds
  by default and would otherwise undo that distinction on paper.

- **Fixed: a 180-nt donor could be divided by a page break.** Pages were a blind fixed-size chunk of the
  line list. A long HDR donor wraps to three lines, and with the right amount of content above it those
  land at 46, 47 and 48 — two at the foot of one page, one at the head of the next. The person copying
  that donor into a vendor form off the printed sheet has to notice it continues overleaf, and the
  failure when they do not is a truncated reagent: the same consequence measured line wrapping was
  introduced to prevent, by a different route. A sequence run that would straddle a break now moves whole
  to the next page; prose still flows across breaks, and a run longer than a page is emitted as it comes.
  Checked at every offset that can produce the collision, for no lost line, no over-long page and no
  divided run.

- **Fixed: the chart ignored the responsive rule written for it.** `.chart { width:100%; max-width:760px;
  height:320px; }` says the intent plainly — but the chart is an *inlined* SVG carrying its own
  `width="720" height="380"`, and those win. Measured in a browser: a 320px box around a 380px drawing,
  so 60px of chart painted over the heading below it; and on a 375px viewport the 720px SVG made the
  document 744px wide, so the whole page scrolled sideways to show a figure that has a `viewBox` and
  could have scaled all along. Styling the element rather than the box gives 760x401 on a desktop and
  327x173 at 375px with no sideways scroll — both states measured on the same page, before and after.

- **Fixed: a 180-nt HDR donor ran 110pt off the right edge of the page it is printed on.** The PDF wrapped
  at a fixed character count — `_WRAP = 92`, "characters per line at 10pt Helvetica within the margins".
  Helvetica is proportional: 92 characters is 460pt of lowercase prose and 614pt of upper-case DNA, on a
  504pt column. An HDR donor is a single unbroken token of the widest glyphs in the face, and it is the
  sequence a bench scientist copies into a vendor form off the printed sheet — it was cut off at the
  paper's edge. The `=` rule under the title overflowed by 33pt on the first page of every report ever
  produced. Wrapping is measured now, against real Adobe Helvetica advance widths; an over-wide token is
  broken at the last character that fits and is checked to reassemble exactly, and the section rules fill
  the column without exceeding it. Two PDF tests that asserted on raw bytes were rewritten to reassemble
  the text runs — a byte-substring check against a hard-wrapped document is really an assertion about
  where the line happens to break.

- **Fixed: a chart with more than ~120 candidates rendered as an empty frame.** The 2px bar inset assumed
  a wide bar, so past that point `bar_w - 4` went negative: a 150-bar chart emitted 150 rects of width
  `-0.6` and a 470-bar one — an ordinary large prime menu, where every PBS x RTT x PAM combination is its
  own pegRNA — emitted 470 of width `-2.9`. A negative `width` is invalid SVG and browsers draw nothing,
  so the efficiency figure came out as axes with no bars: no error, and nothing on the page saying the
  picture was missing. The inset now scales with the bar and the width is floored above zero; a 470-bar
  chart draws its whole distribution, and the guards check every count from 1 to 2,000 for a positive
  width and for neighbours that do not overlap.

- **Fixed: the report's headline chart was an unreadable smear and its caption ran off the image.**
  Measured on an ordinary 90-candidate prime menu: 90 x-axis labels at 6.9px pitch each ~44px wide, and
  95 value labels at 0.0px minimum spacing — printed on top of one another. Rotation was the only
  crowding relief the renderer had. Every bar is still drawn (the bars are the distribution); what is
  capped is the labelling, and the chart says which — "every 5th of 90 bars is labelled" — while per-bar
  values are omitted rather than stacked. The subtitle, 243 characters carrying the calibration and
  trained-model qualifiers, was one unwrapped line running 735px past a 720px chart; it now wraps and the
  plot moves down. Regenerating the committed docs figures caught a wrong model in the fix itself:
  rotated labels collide by perpendicular baseline distance, not width, and the width rule had started
  hiding half the task names on a five-bar chart.
- **Fixed: the report scrolled sideways.** The rationale is one long line per routing decision in a
  `<pre>`, which defaults to `white-space: pre` with no overflow rule: 5,903px laid out in a 1,217px
  column, pushing the *document* to 5,927px and dragging the disclaimer, the charts and every candidate
  off-screen. The two `<pre>` blocks want different answers and now get them — the rationale wraps; the
  oligo block keeps its lines and scrolls inside its own box, because a spacer broken across two lines is
  one someone mis-copies into a vendor form.

- **Fixed: a caveat pointed readers down at a table both renders draw above it.** "the outcome
  distribution below is the NHEJ indel spectrum" — and `_candidate_html` and `_candidate_lines` both
  build the allele table first and the caveats afterwards, so "below" sent a reader looking past the
  flags, the oligo block and the score line for something they had already scrolled by. The sentence was
  written where the flag is *set*, in `cas9.py`, which is the one place with no view of where it lands.
  The guard forbids *deictic* use specifically, not the words: `offtarget-high` legitimately says a site
  "scores at or above the triage band", and a check that could not tell the two apart would need an
  exception list that hides the next real one.

- **Fixed: the search description pointed at rows one of its two readers does not draw.** It is composed
  once by the engine and rendered both by `aforge offtarget`, which prints a row per nominated site, and
  by the design report, which prints none. Two clauses were written for the first reader and shipped to
  both: "each site's own PAM is on its row", and a sub-threshold tail that "is not shown". On the report
  a reader checking the PAM of a low-stringency hit was sent to a table nobody rendered, and "not shown"
  contrasted a hidden tail with a visible list that was also absent. Both now describe the data — a site
  records the PAM it was found with; a sub-threshold placement is not among the nominated sites — which
  is true on both surfaces and loses nothing on the one with rows.

- **Fixed: the ranking rationale described two mechanisms whether or not either had run.** It said "the
  safety term uses the worst-affected ancestry and the efficiency term is uncertainty-discounted"
  unconditionally. Both are conditional in the code: `_safety` takes the worst-affected ancestry only
  when the off-target report carries ancestry annotation and the worst nominated site otherwise, and
  `_efficiency` discounts only an out-of-distribution prediction. So a reference-only run — the common
  case, whose search description two lines away says `reference-only` in as many words — asserted the
  population-aware behaviour this project exists to provide, and a run with no OOD candidate claimed a
  discount nothing received. Each clause now describes what happened and names the mechanism that did
  not apply, so "did not apply" is distinguishable from "does not exist".

- **An objective weighted zero is now said out loud.** `--weights 1,0,0,0` is a legitimate request and
  may put the least specific guide first. The only disclosure was `safety 0.00` inside a parenthetical —
  in a sentence that goes on to explain how the safety term works, for a term that contributed nothing to
  the order it describes. The rationale now names the zeroed objectives, says the ordering does not
  reflect them, and points at the Pareto front, which is computed on all four objectives regardless of
  the weights. Nothing is said when every objective carries weight. The guard pins the second half too:
  if the front ever starts depending on the weights, the sentence pointing readers at it becomes false
  and a test fails rather than the prose rotting.

- **Fixed: the README's provenance example named two models no default run invokes.** The one line
  demonstrating `menu.provenance.models`, commented "every model invoked", showed `['be-dict',
  'pridict2']`. Both are real model cards — the *trained* ones. A default run records
  `be-dict-baseline`, `pridict2-baseline`, `prime-outcome-baseline`, and that suffix is the load-bearing
  part of this project's stance: it is how an artifact says the number did not come from the published
  model. The example now shows what a default run produces and says why the suffix matters, and a guard
  rejects any snippet that presents a trained model's name as example provenance output. The
  self-contained snippets are also executed now and their stated outputs compared — a `# → value` comment
  is a claim and nothing was reading them (all of them were correct).

- **A PAM fallback that applied to one chemistry now says so.** `--allow-ng` reads as a statement about
  the run — "fall back to SpCas9-NG guides when no NGG guide is actionable" — and is routed to the SpCas9
  nuclease vertical alone. Prime and base editing never see it, and prime's decline reason is a bare "no
  PAM match at this offset", so a caller who enabled the flag, got an empty prime menu and read that
  sentence had no way to learn the flag never applied. The nuclease vertical names the fallbacks it did
  *not* use, which is what made the gap visible: two chemistries decline for the same reason and only one
  explains itself. The rationale now says when an enabled fallback was inert, and the scope is stated in
  `design()`'s docstring, both CLI helps and both request models. Widening the fallbacks to prime is a
  scientific decision — a PE-NG pegRNA is a different reagent and the efficiency scorers are trained on
  SpCas9 PE2 — so this states the scope rather than quietly changing it.

- **One account of what each export carries, instead of four.** Grepping for the *sentence* rather than
  the bug turned up "lossless" in four more places, all describing `report_to_json`. It is the complete
  serialization of the report and the report is a summary, so the word was true of the candidate list
  and false of the per-allele and per-site detail — including in the note added two rounds earlier to fix
  the same claim, which then sat on the same page as two notes saying that detail is elsewhere. The
  ranked menu (`menu_to_json`, `aforge design --json`) is the lossless form and is now named as such in
  the module docstring, the API reference and the two withheld-detail notes; the candidate note says the
  narrower thing that is entirely true — the render capped, no export did. A guard rejects the word in
  any render's prose.

- **Fixed: an off-target site count with no route to the sites.** A candidate's safety section gives a
  count, a specificity, the scorer, the matrix and the search budget — and no site rows, by design, since
  the report summarises. `--format json` writes that same summary: `CandidateReport` has
  `n_offtarget_sites` and no `sites`. A comment beside the code said "the lossless export has the sites",
  which is true of the ranked menu one level up and not of the file a reader opens. For a safety artifact
  that is the wrong thing to leave implicit — "2 nominated site(s)" is a number acted on and not
  checkable — so both renders now name where the rows are, sharing one constant with the allele note that
  was fixed the same way. Only where sites exist: nothing nominated, nothing to point at.

- **Fixed: a capped menu reported the count it discarded.** `--max-per-chemistry 2` produced a result
  with two candidates whose rationale said `cas9_nuclease: 23 candidate(s)`. The run notes are written by
  each vertical as it finishes, so they report what was *enumerated*; the cap runs afterwards, during
  ranking, and nothing said so. This is not the render cap, which keeps every candidate in the export and
  says where they are — this one removes them from the result and every export of it, so there is no
  other copy to point at. The rationale now names the number dropped and says they are not recoverable
  from this result; a cap that removes nothing says nothing.
- **`config_snapshot` now records the inputs that decide what the menu is.** The chemistry restriction,
  the per-chemistry cap and the two PAM fallbacks were read at the top of `design()` and never written
  down, so a re-run from the record returned a different — larger — result. Each is recorded, and each
  is routed in `CONFIG_SNAPSHOT_ROUTES` to where a reader can actually see its effect, which is this
  project's standing rule for that dict.

- **A scored run now records the weight matrix that scored it.** `aforge design --region ...` labelled
  every candidate `matrix doench-2016-cfd`, with the citation, and its provenance said `0 dataset(s)`.
  The matrix is a registered dataset with a pinned sha256 and it is the only one whose bytes actually
  ship. So the footer that "names the datasets and tools a run consumed" named none, and — the part that
  matters — `verify --cache-dir` re-hashes `provenance.datasets`, meaning the tamper contract did not
  cover the file that produced every safety number on the result. The matrices are read off the reported
  *sites*, not the scorer's configuration (a fixed published matrix falls back to the length-relative
  approximation per hit, and that approximation is code with no bytes to pin), and a run with no search
  records none.
- **Fixed: `verify` reported the one always-available dataset as `not-cached`.** `bundled` said the bytes
  ship inside the installed package and nothing said *where*, so every consumer looked in the cache — the
  one place a bundled file never is. `DatasetDescriptor` now resolves its shipped path, `verify` hashes
  it there, and a test pins that path equal to the one the scorer loads, since two paths to the same
  bytes are two paths that drift.

- **`aforge verify` now checks the record against the result.** Every check it ran was verifiable from
  the provenance block by itself — a version string, a config snapshot, a name and version on each entry
  that is *listed*. Nothing looked at the artifact the block is attached to, so emptying `models` (one
  edit, in the obvious place, on a report full of efficiency predictions in the same file) still reported
  "provenance is complete and consistent". A prediction implies a scorer ran, and provenance's whole job
  is naming what produced the numbers; that case is now a refusal with exit `4`. The bare
  `.provenance.json` sidecar has no result to cross-check and is still accepted — it is the only
  machine-readable provenance the tsv, html and pdf formats leave behind.

- **Fixed: on the HTML report, a cloning-lethal hazard was typeset as de-emphasis.** Measured in a
  browser, `oligo warning: internal-BbsI-site` computed to 13.6px in grey on no background — it carried
  `class="muted"`, and so did every neighbour: the "showing 3 of 54 alleles" pagination note, the flag
  list, and the ligation-prep reminder. The same was true of every `caveat —` line, which is the *hazard
  subset* of the flags and exists so that hazards do not read with the weight of `epegRNA:tevopreQ1`.
  Hazards now use the amber the research-use panel at the top of the page already uses, at full size and
  full ink; the routine notes stay muted. The guard pins the relationship, not the hex: a hazard may not
  be smaller or greyer than the paragraphs it sits among.

- **Fixed: the printable order sheet buried its hazards and printed half of them twice.** The oligo
  block read header, `top`, `bottom`, U6 note, `WARNING: internal-BbsI-site`, prep — so the line saying
  the assembly enzyme cuts this very insert sat *below* the two sequences a person copies into a vendor
  form, in the same indent as the note and the ligation prep. Hazards now come first, directly under the
  block header. And a precise nuclease candidate printed every donor hazard twice, once as `WARNING - `
  from the donor block and once as `WARNING: ` from the consolidated list, differing by one character:
  four hazards on the page where there were two. The donor block no longer repeats them, and the
  promotion is prefixed `donor:` — which `SgRnaOligos.warnings` already documented and did not do —
  because consolidated with the guide's own hazards, "is 250 nt, beyond what most vendors synthesize"
  does not say which reagent is too long, and the flat table's `oligo_warnings` column has no other
  column to say it either.

- **The cohort panel now offers what the single-variant one does.** The round that gave the served page
  its *More options* controls gave them to one tab. `aforge batch` and `BatchRequest` are each guarded
  against falling behind their single-variant sibling — the page was not, and fell behind immediately. A
  cohort is where these matter most: a variant with no NGG guide is the row that comes back empty, and a
  run left going over a whole VCF is not one anyone re-runs to change a setting they could not find. The
  cohort form now carries cell context, chromatin track (filled from `/api/health` for both tabs from one
  place) and the two PAM fallbacks; the cloning vector stays single-variant-only with the reason
  recorded, and the guard compares the two forms' request bodies directly.

- **Fixed: the served page offered three Download buttons before anything had been designed.** The page
  hides sections with the `hidden` attribute, which works by a user-agent `[hidden] { display: none }`
  rule that *any* author rule setting `display` outranks — and `.actions { display: flex }` did. Both
  download bars were `hidden === true` and `display: flex` at once, so the page opened offering *Download
  PDF / JSON / TSV* for a result that did not exist, and pressing one returned in silence. The stylesheet
  now neutralizes the collision for every element toggled that way, and both handlers say why they are
  doing nothing (the cohort one on the cohort's own status line, not the single-variant one that is not
  even on screen). Found by opening the page.

- **Fixed: the CRISPR-Bench leaderboard page was unreadable in dark mode too, and the guard for that
  could not see it.** The report and the frontend were fixed by painting the ground their palettes
  assume; the board failed the same way for the opposite reason — it declared no colours at all, which
  is not neutral: with no `color-scheme` the user agent applies its default *light* text rules while the
  browser paints a dark canvas, so the board rendered dark grey on near-black. The guard added in the
  previous round read *stylesheet sources*, so a page with no stylesheet was invisible to it. It now
  renders each of the three pages and asks of the document what a reader would — does it say which
  scheme it was drawn for, and does it paint its own ground — and is verified to fail on the old board.

- **Fixed: `--json` produced a stream no parser accepts.** `aforge design --out report.json --json >
  menu.json` wrote the `wrote <path>` confirmation and the ranked-menu JSON to the same stream. The test
  covering that path documented the defect instead of failing on it — it dropped the first line before
  parsing — and it kept passing after the fix because `result.output` is click's *mixed* stream, not
  stdout. Every `wrote <path>` line now goes to stderr, where every other status message in this CLI
  already goes, and the guards assert on `result.stdout`.

- **Fixed: the withheld alleles were not in "the lossless export".** A Cas9 spectrum routinely has 65
  alleles; the renders show three and used to say the rest were in the lossless export. `--format json`
  writes `report_to_json`, whose `outcome_top` is the same three — a reader chasing the other 62 opened
  the file and found the page again. The full spectrum lives one level up, on the `RankedMenu`
  (`menu_to_json`, `aforge design --json`), and both renders now say so. The PDF said the count and
  nothing about where the rest went; it says both now. Pinned as a fact about the data rather than a
  string match, so if either export's truncation changes the note fails.

- **Fixed: a render told readers to look in an export that does not exist.** Both render caps ended
  "the remaining N are in the lossless JSON/CSV export" — wrong twice. There is no CSV export (the
  formats are JSON, TSV, Parquet, HTML, PDF), and "lossless" is true of the JSON alone: the flat tables
  carry one scalar row per candidate, without the allele spectrum, the oligo sequences or the off-target
  site list. A reader chasing a withheld candidate's details looked for a file that is not written and,
  settling for the TSV, read a row that cannot answer. One shared sentence now names the lossless form
  and the complete-but-flat ones separately, and a new guard rejects any format name in a render's prose
  that this tool does not write — verified to fail on the old string.

- **Fixed: the report's headline chart was titled *Calibrated efficiency* on a page where nothing was
  calibrated.** Every candidate underneath it prints `(nominal — coverage not measured)` and
  `(heuristic point estimate — not from a trained model)`, because with the bundled models `calibrated`
  and `point_from_trained_model` are both `False`. The chart is the first thing a reader looks at and it
  asserted the opposite of every line below it — the honesty machinery reached the prose and stopped at
  the figure. The title now tracks the bars (*Predicted efficiency* unless every one is calibrated) and
  the subtitle carries the same qualifiers the text does, quantified when only some bars are affected so
  a report mixing a trained prime scorer with the heuristic Cas9 one is not described by either extreme.

- **Fixed: pasting the tool's own printed variant back into it blamed the build.** `chrom:pos:ref>alt`
  is *read* as a 1-based VCF record and *printed* with a 0-based position, both documented — but the
  printed form is syntactically the input form, so `aforge resolve chr1:1018:T>A` prints
  `chr1:1017:T>A`, and handing that back either failed with `(wrong build?)` — the one thing that was
  not wrong — or, when the neighbouring base happened to match, silently designed an edit one base
  away. The refusal now checks whether the asserted ref sits one base to either side and, when it does,
  names the convention and hands back the string that works; a genuine mismatch still blames the build.
  The HTML and PDF renders carry the warning beside the variant, where the surprise is, rather than
  relying on the footer's general note about loci. The comment above `COORDINATE_NOTE` claimed every
  printed locus round-trips; it now records the one exception.

- **Fixed: the HTML design report rendered as a blank page in dark mode.** The same defect as the served
  frontend and a worse consequence: the report is the artifact a collaborator is *sent*, opened on a
  machine whose theme the author never sees. `body` carried `color: #1a1a1a` and no background, so it
  inherited the user agent's — dark ink on a dark ground. (Its charts were fine; the inlined SVG paints a
  white rect first.) The report now declares the light scheme its palette assumes and paints its own
  ground, and the mechanical rule — a `body` rule that sets a foreground sets a background, and the
  scheme is declared not inherited — now covers every stylesheet the project ships.

- **Fixed: the served page was unreadable in dark mode.** `styles.css` is a light design throughout and
  set `color: #1a1a1a` on `body` without ever setting a background, so `body` inherited the user agent's
  — near-black text on a dark ground. Every field label, every help line and the tagline were invisible,
  and the form controls rendered dark against the white panels for want of a `color-scheme`. Found by
  loading the page in a browser; the frontend tests read it as text, which is the right trade for a
  build-free page and blind to exactly this. Two mechanical guards stand in for a renderer.

- **The served page can hand a user the flat table.** Its export buttons were *Download PDF* and
  *Download JSON* — a printable document and a nested object — so the one format a bench scientist opens
  in a spreadsheet had to be produced from another shell, which for a browser user means not at all. A
  *Download TSV* button now sits beside them, and a test pins the two properties that matter: every
  `?format=` the page requests is one the API accepts (a mismatch fails only at runtime, in the browser),
  and each one actually returns a body.

- **The flat table now names the enzyme that cleared each insert.** `oligo_warnings` is the ordering
  hazard a pipeline filters on before placing a DNA order, and it became interpretable only against a fact
  the table did not carry the moment the cloning vector became the caller's to choose: an empty cell means
  "clean for **this** enzyme", and pX330's BbsI and lentiGuide's BsmBI clear different sequences. One report
  can even mix them — an sgRNA-only vector cannot receive a pegRNA extension, so those rows stay on the
  pegRNA acceptor — which is the `offtarget_worst_matrix` situation and is solved the same way, per row.
  New `oligo_scheme` and `oligo_enzyme` columns, empty alongside `oligo_warnings` when no oligos were built.
  Export schema version 11 → 12.

- **The flat table a pipeline reads is now obtainable from both shells.** `report_to_parquet` was
  reachable from Python alone — so the round that gave Parquet its disclaimer, reference build and
  coordinate convention improved a file no shell could produce, while `docs/api/cli.md` documented it under
  `--format`. And the web API offered `json|html|pdf` only, leaving the one audience that cannot open an
  HTML page with nothing to read over HTTP. `aforge design --format parquet --out menu.parquet` now writes
  it (requiring `--out`, since the notes live in the file's metadata, and leaving the same
  `.provenance.json` sidecar every other format does; exit `4` naming the extra when `polars` is absent),
  and `POST /api/design?format=` accepts the same five formats the CLI does, pinned equal by a test.

- **Fixed: the TSV and the Parquet disagreed about column order.** They are documented as the same table.
  The TSV projects each row onto `TSV_COLUMNS`; the Parquet writer handed polars a list of dicts and took
  whatever order `_row` built, which had drifted by one adjacent swap — `offtarget_specificity` and
  `offtarget_expected_burden`, two numbers on unrelated scales, at the same index in the two files. A
  positional reader (`frame[:, 17]`, `df[[18]]`) silently read the wrong one. The guard that existed asked
  `set(TSV_COLUMNS) <= set(frame.columns)`, true under any permutation; both halves are now pinned as
  sequences, and the empty-table branch — built from the constant, so already ordered differently from a
  populated file written by the same function — agrees with the populated one by construction.

- **The cloning vector is now the caller's to name, and the ordering-hazard screen follows it.** Every
  insert is screened for a copy of its scheme's Type IIS recognition site — the classic Golden-Gate
  failure, where the enzyme that assembles the construct also cuts it and the clone silently dies. That
  screen is only as right as the scheme, and the scheme was a Python-only argument to `build_report`: the
  CLI and the web API always screened for lentiGuide's BsmBI. pX330 / pSpCas9(BB) is the other standard
  sgRNA protocol and cuts with **BbsI**; its overhangs are the same `CACC`/`AAAC`, so the printed oligos
  are correct to order either way, and a spacer carrying `GAAGAC` came back clean. `aforge design
  --vector-scheme px330-bbsi`, the `vector_scheme` request field on `POST /api/design`, and the
  `vector_scheme` config key now select it; an unknown name is a usage error (or a 422) listing the
  registered schemes, and the OpenAPI enumeration is derived from the registry rather than retyped beside
  it. An sgRNA-only vector has no 3'-extension overhangs and cannot receive a pegRNA, so selecting one
  leaves pegRNA candidates on the pegRNA acceptor instead of failing the whole report — every candidate's
  block names the scheme it was built with. `aforge batch` is exempt with the reason recorded: the cohort
  path writes raw ranked menus and builds no oligos at all, so it has nothing to screen.
- **`build_report()` is now under the same shell-parity check `design()` and `search()` are.** Two entry
  points had a test asserting that a parameter a shell does not forward is a recorded decision rather than
  an oversight; the third — the one that decides what the *document* says — had none, which is how
  `scheme` stayed library-only. Adding the check immediately paid: the repository's own cohort-parity
  guards then failed on the new option and forced the exemption to be written down.

- **The Parquet export states its own provenance.** The flat table grew a leading `#` note block in
  schema v6 so the one surface a result gets forwarded in would not show efficiencies, specificities and
  genomic loci with nothing saying they are uncertain predictions, against which genome, in which
  coordinate convention. Parquet holds the same columns and is the format a *batch* consumer reads, and it
  carried none of those notes — it has no comment lines. It now carries them where Parquet puts them, as
  file-level key/value metadata (`disclaimer`, `provenance_1..n`, read with
  `polars.read_parquet_metadata`). Both writers draw from one source and a test pins the reverse direction,
  so two tables of identical numbers cannot disagree about which genome they are against. Export schema
  version 10 → 11; the optional `polars` floor rises to 1.30, the first release whose Parquet writer accepts
  file metadata.

- **The chromatin adjustment is reachable over HTTP, and `/api/batch` uses every configured source.** The
  accessibility tracks are operator-configured (`ALLELEFORGE_ENCODE_TRACKS`) while the track *name* is
  per-request, since one bedGraph holds several cell types; `GET /api/health` lists the names a client can
  choose from, and an unknown one is a 422 carrying the vocabulary rather than the CLI's old failure mode
  (an empty menu and a success status). The cohort endpoint builds its design call separately from the
  single-variant one and was still running reference-only after the sources were wired into the latter — a
  cohort row and a one-variant result look identical either way.
- **The haplotype-aware pass is reachable over HTTP too.** The population source's sibling, wired the same
  way (`create_app(haplotypes=...)` or `ALLELEFORGE_HAPLOTYPES`) and reported the same way
  (`haplotypes_loaded` on `/api/health`). It finds a site that exists only on a co-inherited combination of
  alleles — something no single-variant source can nominate — and wiring one ancestry source without the
  other would have left the capability half-reachable.
- **The population-aware off-target search is reachable over HTTP.** `OffTargetRequest` accepted
  `populations` and `maf` but no population source, `create_app` took none, and no environment variable
  supplied one — so every API scan was reference-only whatever ancestry labels a client asked for, and every
  breakdown came back empty, which reads as "no ancestry-specific risk" rather than "nothing was searched".
  The same gap was found and closed for the CLI rounds ago; the web shell kept it. The source is
  operator-configured (`create_app(gnomad=...)` or `ALLELEFORGE_GNOMAD_TSV`) because a client-supplied path
  would be an arbitrary file read, and `GET /api/health` now reports `gnomad_loaded` so a client can tell
  which deployment it is talking to.
- **Every native kernel's speedup is re-measurable.** `scripts/native_speedup.py` timed four things while
  the crate exposed six, and the R223 contig fold was timed by nothing — so several claims in the round log
  existed only as prose. It now also times the bulged-alignment kernel (R208), the per-anchor evaluation
  kernel (R224) and the fold to the index alphabet, each against the fallback it replaced: **9.5x**, **8.9x**
  and **13.5x/19.4x** on this machine. A `TIMED_KERNELS` map ties each function registered in
  `rust/src/lib.rs` to the section that times it, and a test fails in both directions — a kernel with no
  section, or a section naming a kernel that no longer exists.
- **The specificity says what else went into it.** `specificity_score()` is
  `1 / (1 + Σ reported + subthreshold_score_sum)`: the tail is deliberate, so a guide does not become clean
  because the caller asked to see fewer of its off-targets. Nothing disclosed it, so the headline number could
  not be derived from the printed rows — and with the cut-offs raised past every hit the report read
  `0 site(s), worst score 0.000, specificity 0.130`, three numbers of which only the unexplainable one carried
  the risk. The description now names the suppressed tail's placement count (recorded as
  `subthreshold_placements`, because `0.19` of mass is one near-miss or twenty faint ones) and its
  contribution, and states that raising the cut-off cannot improve the specificity.

- **The off-target report says when it broadened the PAM.** `search()` widens SpCas9's `NGG` to `NRG` so
  low-stringency `NAG` sites — which SpCas9 cuts, less efficiently — are nominated rather than missed. That is
  deliberate and specified, and no surface said it: a report headed `PAM NGG` listed sites reading `pam=CAG`
  with nothing reconciling them, while the search description enumerated every *other* condition the numbers
  rest on. It is load-bearing — over a CAG repeat, 24 of 25 sites are NAG, so the specificity is almost
  entirely produced by low-stringency PAMs — and both available readings (real NGG hits, or a bug) were
  wrong. `OffTargetReport.scanned_pam` records it and the description states it, only when the scan really
  did broaden.

- **The identifiers the capability specs name are checked against the code.** Across 4,400 lines of spec
  there are 467 backticked tokens — CLI flags, class names, enum members — and nothing verified that any of
  them still named something real. All of them do today, so this is preventive and mutation-verified: renaming
  a cited enum member in a spec fails it. The resolver understands enum members (`ZERO_BASED_HALF_OPEN`,
  `NOT_PROVIDED`, `PATHOGENIC`), which are most of what a requirement cites and none of which is a
  module-level name, and an exemption list covers tokens that look like code and are not — DNA motifs, VCF
  column values, and the browser APIs the web spec names to promise the frontend avoids them.

- **The capability specs are checked against the shipped CLI.** `openspec/specs/` holds nineteen
  specifications — the requirements a change folds into when it ships — and no test in the suite read them.
  `aforge lift` shipped with a CLI test, a README row and a docs entry and appeared in none of them, while
  the CLI spec's own subcommand requirement enumerated five commands for a tool that ships eight. The `lift`
  requirement is now written (and was checked against the real command, including `UNMAPPED` and its non-zero
  exit), and a new check runs both directions: a command the specs name must exist, and a command that exists
  must be named. The exit codes the requirement lists are compared to the `ExitCode` enum.

- **The design principles agree with themselves.** `openspec/project.md` — the file the tests call the source
  of truth — still stated *"Population-aware by default. Off-target search covers population variation and
  stratifies by ancestry"*, the overclaim the README and docs had already been corrected for; the guard
  against that claim read `README.md` and `docs/index.md` and not the canonical file. The source of truth now
  carries the honest wording, the guard reads it, and a new check requires the README's restatement of the
  principles to match it. `_PRINCIPLE_EVIDENCE` also now records the *title* each entry was written against,
  not just the number, so rewording a principle cannot silently transfer its evidence.

- **A `genome-light` extra names the set every build was assembling by hand.** `"pyfaidx>=0.8"
  `"pyliftover>=0.4"` was appended to an extra in seven CI jobs, the Makefile and the Docker image — the
  light half of `genome` (pure-Python FASTA reader and liftover, without the compiled pysam/cyvcf2/mappy
  chain), described in prose by the Dockerfile's own comment and nameable by nobody outside the repository.
  `genome` is now defined in terms of it so the two cannot diverge, and a new check fails any `pip install`
  line in the Makefile, Dockerfile or workflows that names a package dependency beside an extra — such a line
  is either an extra missing something (which broke `pip install "alleleforge[web]"`) or a set that deserves
  a name.

- **`pip install "alleleforge[web]"` can actually serve.** The extra was `fastapi`, `uvicorn`, `httpx` — no
  FASTA reader — so the documented three-line quickstart died at import on
  `uvicorn alleleforge.web.api.app:app`, because `create_app()` runs at module scope and reads
  `ALLELEFORGE_REFERENCE_FASTA`. The Dockerfile already compensated by adding `pyfaidx` by hand, with a
  comment explaining that the API needs only the light reader and not the heavy pysam/cyvcf2/mappy chain;
  that reasoning now lives in the extra, the image no longer re-adds it, and a test pins that it does not
  come back. The web app's reference loader also catches `ImportError` alongside `OSError`, so an
  environment that cannot supply a reader leaves a running service with a recorded reason rather than a
  traceback in a container log.

- **`aforge bench` explains a missing optional dependency instead of tracebacking.** On a
  `pip install "alleleforge[cli]"` — a documented install — `design`, `batch` and `offtarget` all report
  *"needs the optional dependency pyfaidx … pip install 'alleleforge[genome]'"* and exit 4; all four `bench`
  subcommands died with a raw `ModuleNotFoundError` and exit 1, because `_missing_dependency` — the handler
  written for exactly this — was wired into three of the four places that needed it. Verified against a wheel
  installed into a clean interpreter, not only in-process. Two links of the underlying import chain were also
  removed: the `enumerate` modules annotate with `ReferenceGenome` and now import it under `TYPE_CHECKING`,
  and `alleleforge.genome` defers its `reference` re-exports (PEP 562) so importing any genome submodule no
  longer pulls in pyfaidx.

- **A symbol a documented snippet imports must exist.** The docs already check every CLI command the prose
  invokes, every flag it names, every local link and every module path it cites; the `from alleleforge… import
  X` lines inside the Python fences were the one unchecked claim, and only their modules were verified. A
  renamed export would have left every documented snippet importing a name that is not there, with the suite
  green and an `ImportError` on the reader's first line. All eighteen resolve today, so this is preventive —
  and mutation-verified, after a first attempt that edited `__all__` and proved nothing (it does not bind or
  unbind names, only `import *`).

- **The shipped Docker deployment starts without a pre-built `.fai`.** Opening a reference writes
  `<fasta>.fai` beside it when none exists; the bundled `docker-compose.yml` mounts the reference read-only
  (correctly) while calling the index optional (wrongly). Without one, `uvicorn alleleforge.web.api.app:app`
  — the command in the deployment guide and the Dockerfile — **died at import**, because `create_app()` runs
  at module scope; the CLI relayed pyfaidx's advice about a Python API it already passes; and nothing named
  the remedy. `ReferenceIndexError` now names the missing index, why it cannot be created and the
  `samtools faidx` that fixes it; the web loader catches it so the service starts and answers `503` with that
  text; and the compose header and deployment guide say the index is required on a read-only mount.

- **A corrupt FM-index cache is refused instead of answering "no occurrences".** The cache directory is named
  for the sequence hash, so a wrong *directory* was impossible and a corrupt *file inside the right one* was
  never checked: a truncated `bwt.bin` loaded silently and reported zero hits — which renders as
  "0 site(s), specificity 1.000" — and a one-byte tamper dropped a real occurrence while returning two
  positions that are not occurrences. `FMIndex.verify()` catches both and **nothing called it**, so its
  documented "fails closed" guarantee held for nobody; it is `O(n)` and cannot run on every load, so
  `FMIndex.load` now checks in constant time what `meta.json` already records — the BWT's length, and that
  `c_table` is a non-decreasing set of offsets inside it. Same-length tampering still needs `verify()`, and
  the check says so.

- **The native FM-index says which cache arguments it ignores.** With the Rust crate built — the configuration
  the README recommends for real genomes — `FMIndex.build` dispatches to the in-memory kernel and silently
  dropped `cache_dir`, `rebuild`, `occ_rate` and `sa_rate`, so a caller passing `cache_dir=` (or
  `search(..., fm_cache_dir=...)`) got no cache, no error, and a rebuild on every call. It now warns, naming
  the dropped arguments and `prefer_native=False`, and only when one was actually supplied.

- **One check over every artifact the tool writes.** Four rounds running found the same missing
  document-level context one artifact over, each missed because the existing check is keyed to a *type*.
  `test_every_artifact_says_what_it_is` enumerates the writers instead: the design HTML/PDF/TSV/JSON, the
  cohort summary, the off-target payload and both leaderboard renders are produced through their real CLI
  paths and asserted to say what they are. Two artifacts are exempt with recorded reasons — the signed
  benchmark result (adding a prose field would invalidate every previously signed result's signature) and a
  cohort's per-item menu JSON (a library type, with the context beside it in the summary and manifest).

- **The CRISPR-Bench leaderboard says what it is.** The artifact most likely to be published, linked and
  quoted marked its synthetic splits — the fact it most needs — and carried no research-use statement, no
  version and no generation time. Both renders (and the empty board, the one most likely to be published
  first) now lead with a shared context block. `RESEARCH_USE_DISCLAIMER` is split into a
  `RESEARCH_USE_CORE` true of every artifact plus the design report's fuller sentence, because reusing the
  full one verbatim put "The candidates below are ranked…" at the top of a board of *models*; the board adds
  that a benchmark score on a frozen split is not evidence a model is fit for a therapeutic decision.

- **`resolve` says when a variant changes nothing.** `chr1:1000:A>A` — reference and alternate identical —
  came back as `[snv, build hg38, from coordinates]`, because `variant_class` is computed from allele
  *lengths*: one base against one base is an `snv` whether or not they differ. The design path already refuses
  to build a reagent for such an input, by name and with a non-zero exit; `resolve`, the command whose job is
  to say what an input means, was silent. Both shells now report `changes_the_sequence`. Reported rather than
  refused — a reference call is a legitimate VCF row and `aforge batch` reads VCFs.

- **`P(intended)` ships with its uncertainty, like the two numbers beside it.** A candidate carried
  `efficiency` and `bystander_burden` as `Prediction[float]` and `p_intended` — the probability the edit
  produces the allele you asked for, the number a reader is most likely to act on — as a bare float on every
  surface. It was not missing but *discarded*: `PrimeOutcomePredictor` returns a `Prediction` for it that
  `prime.py` dropped in one line, and base editing's `p_intended_exact` never reached the candidate; both were
  recomputed downstream as a plain sum. `DesignCandidate.p_intended` now carries the scorer's prediction, the
  HTML and PDF show its interval and flags, and the TSV gains `p_intended_low/high/in_distribution/calibrated`
  (`EXPORT_SCHEMA_VERSION` 7). SpCas9's outcome predictor makes no such prediction, so there the field is
  `None` and the renders say *derived from the outcome distribution; no calibrated interval* instead of
  inventing a band.

- **`aforge verify` names the three artifact shapes it accepts.** It parsed everything as a `RankedMenu`, and
  a `DesignReport` — what `design --format json` actually writes — had been validating as one by structural
  coincidence, so `verify` was reading a different object than the file described. Adding a field to
  `DesignCandidate` ended the coincidence and would have made `verify` reject the tool's own primary output;
  it now tries `DesignReport`, `RankedMenu` and the bare `Provenance` sidecar explicitly, and the middle one
  is pinned so it is accepted on purpose.

- **Every closed-set refusal names the values it accepts.** Three of the CLI's five did (`--scorer`,
  `bench run`, `data show`); `--intent` and `--chemistry` — the flags on the primary command a first-time
  caller most often gets wrong — did not. The chemistry message echoed pydantic's `'PRIME' is not a valid
  Chemistry`, which names the *class* rather than a word from the caller's vocabulary, and reported only the
  first bad value of a repeatable flag. Both now list the accepted values, on the CLI and on the web API,
  where it matters more because there is no `--help` on the other end of a `422`. All five are pinned by one
  parametrized test, so the next closed-set input joins the list or fails.

- **An unexamined ancestry now names the labels that would have worked.** `docs/data.md` documents three
  ancestry vocabularies (gnomAD `afr`, 1000 Genomes `AFR`, HGDP `africa`), so `--populations AFR` against a
  gnomAD slice whose columns are `afr`/`nfe` produced a true but unactionable warning: the request went
  unexamined, and the report — which had computed the backed set to decide that very sentence — did not say
  what the sources carry. `OffTargetReport.available_populations` now does, and where no ancestry source was
  supplied at all it says that instead, since an empty list of alternatives would read as "these exist and
  yours is not among them". The labels are deliberately **not** case-folded: gnomAD's `afr` and 1000 Genomes'
  `AFR` are different groupings, and matching them would silently answer a question about one with data about
  the other.

- **A reported locus is named the way the searched reference names it.** The same off-target site in the same
  genome was called `chr2:43-63` unscoped and `2:43-63` when scoped with `--region 2:0-183`: unscoped the
  contigs come from the reference, scoped they carried whatever the caller typed, so **the identity of a site
  depended on an unrelated flag** and two runs over one genome produced lists that do not join or
  deduplicate. Nothing was mis-searched — `canonical_contig` reconciles the styles — but the name written down
  afterwards was the caller's, not the genome's. Regions are now renamed where they meet the reference in
  `search()`, and a variant in `resolve()` when a reference is supplied, so a `2:71:A>C` input against a
  `chr2` genome no longer yields a candidate at `2:43-63` beside off-target sites at `chr2:…`. The rename is
  always toward the supplied genome: a bare-named FASTA yields bare-named output, `resolve` without a
  reference renames nothing, and an unknown contig is still refused rather than renamed onto another sequence.

- **A fifth native kernel: the per-anchor protospacer evaluation.** `_evaluate` runs once per PAM-positive
  anchor — 500,000 times over 2 Mb — doing the ungapped comparison in Python and crossing the FFI boundary
  twice more for the two bulge directions. `rust/src/evaluate.rs` does the whole decision, so a scan crosses
  once per anchor instead of three times: **a 2 Mb scan goes ~1.25s to ~0.89s, 28%**, measured as interleaved
  A/B pairs, with the specificity identical to nine decimal places. Same contract as every other kernel — an
  unbuilt crate changes the speed of a run and not its results, pinned by a parity suite.

  Writing the port forced two decisions the Python had never made, both off-contract and both worse than an
  error: `pam_at` past the end of the sequence raised `ValueError` from a `zip` three frames down, and the
  same with an *empty spacer* returned a zero-mismatch hit at a coordinate outside the sequence. Both paths
  now refuse. Nothing in contract changes.

- **Folding a contig to the index alphabet runs in C, not per base in Python.** `_sanitize` maps every base
  outside `ACGTN` to `N` so the linear scan and the FM-index path agree about what a window holds; it did so
  with `all(b in _INDEX_ALPHABET for b in seq)` plus a comprehension — one pass of interpreter overhead per
  character of a reference, once per sequence per `search()`, uncached, with `search()` running per candidate.
  Two `str.translate` calls replace it: **2 Mb 59.8ms -> 3.3ms (+94.5%), 20 Mb 775ms -> 35ms**. The
  substitution derives its table from the offending characters themselves, which keeps it faster on every
  input distribution (clean +92%, one stray base +94%, a synthetic 44%-IUPAC sequence +78%) rather than
  trading the clean path against the dirty one, and cannot mishandle a non-ASCII byte the way a fixed
  256-entry table would. Equivalence is pinned by property tests against the previous implementation. The
  end-to-end 2 Mb scan does not visibly move — 56ms is below this harness's ±7% noise — so the case is the
  scaling, not a stopwatch on a toy contig.

- **The browser cohort table shows specificity and the off-target basis, not a bare worst-case score.** The
  column beside the one an earlier round fixed for bare efficiency estimates rendered `worst off-target 0.000`
  alone — the most reassuring number the system can produce. The batch response also carries
  `best_specificity` and `offtarget_sources` (`{}` when nothing backed the scan, which over HTTP is always,
  since no file-backed population source can reach a deployment), and the table ignored both, so every cohort
  row in the browser showed a reference-only result as a clean one. It now shows the specificity and marks the
  basis `reference-only` in the error style. Verified by driving the served SPA in a browser and reading the
  rendered row back from the DOM, not only by asserting on `app.js`.

- **A standalone off-target result says which genome it searched.** `aforge offtarget --json` and
  `POST /api/offtarget` carried extensive per-search honesty (`on_target_excluded`, `searched_bases`,
  `effective_matrix`, the ancestry stratification) and no document-level context at all: no reference
  identity, no coordinate convention, no disclaimer. Two scans over different FASTAs give different
  specificities and produced indistinguishable payloads, and the `locus` strings are 0-based half-open with
  nothing saying so. Both shells now carry `reference` (the shape descriptor), `coordinate_system` and
  `disclaimer`; the CLI prints one line under the search description rather than repeating it per site. The
  HTTP surface is where this matters most — a client cannot see the FASTA the server opened.

- **The cohort summary TSV carries its caveats, and the run records which genome it screened against.**
  `aforge batch --summary-tsv` — the file a whole-cohort run is read through, one row per patient — carried no
  disclaimer, no coordinate convention, no reference identity and no seed. It now leads with the same `#` note
  block the per-design export got, so the column header is still the first non-comment line. Building those
  notes exposed the second half: `CohortRunReport.provenance` is a dict the cohort assembles by hand, and it
  recorded `reference_build` (a label) and nothing about the genome — the same gap the design path closed
  earlier, still standing here because the fix landed on an object the cohort does not use. The run header now
  carries the same shape descriptor. Under `--max-workers` there is no run-wide reference, and the summary now
  says each item's own result records the genome it used, rather than printing `reference build None`.

- **Every render of a report is checked to state the same whole-document facts.** A `fact x surface` table
  (disclaimer, coordinate convention, reference identity, build, seed, models across HTML/TSV/JSON/PDF) is now
  a test with an explicit, reasoned omission list, so a fact added to one render cannot quietly skip the
  others. Writing it found the last gap: `report_to_json` stated **no coordinate convention at all** — its
  `locus` is a formatted string and the embedded `Provenance` has no coordinate note, because that note lives
  in a render helper the JSON never calls. `DesignReport.coordinate_system` (`"0-based-half-open"`) is now a
  field rather than a sentence, since the consumer of that surface is a machine; it reaches `/api/design` too.

- **A malformed gnomAD sites file is refused with the line and the reason.** `--gnomad` was the one
  user-supplied format whose parse errors escaped as a bare traceback (`KeyError: 'af'` on a row with its
  trailing columns lost, because `zip(..., strict=False)` truncates silently and `_load_gnomad` catches only
  `OSError`/`ValueError`) — and it is the input that makes a scan population-aware. Three cases now get three
  answers: a header missing a core column prints the expected header, a row that cannot supply the core
  columns names the line and its field count, and a header naming the same column twice is refused rather
  than silently keeping the last of two frequencies for one ancestry. A row omitting only trailing population
  columns stays legal.

- **The specificity scorer is reachable over HTTP, and unknown request fields are refused.**
  `OffTargetRequest` had no `scorer` field, so `POST /api/offtarget {"scorer": "cfd-cas12a"}` returned `200`
  scored by the SpCas9 CFD matrix — pydantic ignores an unknown key by default. Because `pam` *is* settable,
  a Cas12a search was already reachable and came back labelled `doench-2016-cfd`, the published matrix, where
  the CLI labels the same run `cas12a-analog-approximation (unvalidated)`: a wrong honesty label on the
  surface most likely to be read by a machine. `scorer` now resolves through the same `scorer_for` the CLI
  uses (an unknown name is a `422` listing the valid ones), and **every** API request model now forbids
  unknown fields, so `populatoins`, `intnet` or `buidl` is a `422` naming the key rather than a `200`
  describing a run the client did not ask for.

- **The accessibility track is pinned in provenance, and its name is checked.** Two runs over bedGraphs
  differing only in signal produced different efficiencies (0.484 vs 0.457) and identical provenance with an
  empty `datasets` list: `_attach_source` pins gnomAD and the haplotype panel by content hash, and the ENCODE
  loader was the one that never called it, so `_collect_datasets` looked for a descriptor the CLI never
  attached. Recording `chromatin_track` — a name the caller chose — cannot tell two accessibility files apart.
  Separately, `--chromatin-track` naming a track absent from the file raised `KeyError` inside the chemistry,
  which caught it as a decline reason: an **empty menu and exit 0**, with the cause buried in a rationale
  paragraph. The name is now validated where it is supplied and the refusal lists the names the file has; a
  bedGraph that parses to no tracks at all is refused too, explaining that lines beginning `track`, `browser`
  or `#` are skipped as UCSC directives.

- **Provenance identifies the reference genome, not just its label.** Two designs over two different
  reference FASTAs produced byte-identical provenance while their safety verdicts differed twofold
  (specificity 0.879 vs 0.468), and `aforge verify` called both complete: the block recorded
  `reference_build`, a label that stays `hg38` whatever FASTA is opened, and `_collect_datasets` names the
  reference only for a registry-resolved build, never for the `--reference-fasta` path everyone uses.
  `config_snapshot.reference` now carries build, contig count, base count and a hash of the canonicalized
  `name:length` list, read from the `.fai` so the cost is O(contigs) — exposed as
  `ReferenceGenome.contig_lengths()`. It pins the reference's *shape*, and says so in the record and in the
  report footer (`pins contig names and lengths, not the bases`), because two FASTAs with the same contigs
  and lengths are indistinguishable to it and a digest that overclaims its reach is worse than none.

- **A run-config TOML can be written as TOML.** `weights` and `populations` are whitelisted config keys —
  so `--config` accepted them without a typo warning — and both were then handed to a parser that only knew
  the CLI's comma-separated string, crashing with `AttributeError: 'list' object has no attribute 'split'` on
  the natural TOML spellings. The `[weights]` table is exactly the shape a result's own
  `provenance.config_snapshot` records, so the user most likely to hit it was the one reconstructing a run
  from its provenance. Both keys now accept either spelling (weights also as a 4-element array), a malformed
  one is a usage error naming what was expected instead of a traceback, and the three weight spellings are
  pinned as producing the same run. `docs/api/cli.md` now shows the run-config file it referenced in three
  places and never displayed, and a test extracts that block from the markdown and runs it.

- **The API reference lists every endpoint, and a check keeps it that way.** `docs/api/web.md` heads a
  table "Endpoints" and omitted `POST /api/batch` — cohort design over a variant list, a whole capability —
  while the README's copy of the same table had it. Nothing was broken, which is why nothing caught it: the
  route works and its tests pass, and the omission is visible only by diffing two documents. A new check
  asserts every `/api` route the app serves appears on both surfaces, normalizing `{...}` so a renamed path
  parameter is not a failure. It is the mirror of the environment-variable check: that one asks whether every
  documented name is real, this one whether every real name is documented.

- **The documented environment variables are checked against the ones the software reads.**
  `docs/deployment.md` named the reference build `ALLELEFORGE_REFERENCE_BUILD`; the `Settings` field is
  `reference`, so the real variable is `ALLELEFORGE_REFERENCE` and exporting the documented name silently left
  the build on `hg38` — a deployer aiming at mm39 would have had every downstream coordinate interpreted
  against the wrong genome, with nothing said. The table also omitted `ALLELEFORGE_ALLOW_NETWORK` and credited
  the cache directory to `XDG_CACHE_HOME` alone when `ALLELEFORGE_CACHE_DIR` takes precedence. All three are
  fixed, and a new check fails the suite for any `ALLELEFORGE_*` name in the docs that is neither a `Settings`
  field nor read from `os.environ` in `src/`, with three variables additionally exercised end to end so the
  derived "honored" list cannot drift into agreeing with a wrong table.

- **CLI help is checked against the flags it names.** `--region`'s help on `design`, `batch` and
  `offtarget` warned that the locus is 0-based "unlike `--variant` and `--pop-freqs`" — two flags that do not
  exist (the variant is a positional argument; the frequency file is `--gnomad`), a wrong pair repeated in
  `docs/data.md`. The sentence is the tool's only warning about the coordinate convention that, mixed up,
  moves a scan one base off target, so an unfollowable version of it is worse than none. A new check walks
  every command and requires each long option named in its help to be its own or qualified by the command that
  owns it; it also caught `lift`'s bare `--region` and, in `verify`, `--format`/`--out`, which belong to
  `design`. What is true is now stated too: `--gnomad` and `--patient-vcf` take 1-based VCF positions, and
  `--haplotypes` is 0-based in both its span and the `pos` of each `chrom:pos:ref>alt`.

- **`aforge verify` reads the provenance sidecar `aforge design` writes.** `design --out X` leaves a
  `X.provenance.json` block beside the result; `verify` — the command that turns provenance from a record into
  a checkable contract — parsed only a full `RankedMenu` and rejected that sidecar with a pydantic error about
  a missing `candidates` field. For `--format tsv`, `html` and `pdf` the sidecar is the *only* machine-readable
  provenance a run produces, so the contract was out of reach of three of the four output formats, and the
  error named the wrong file. Every check `verify` performs reads the provenance block and nothing else, so it
  now accepts either shape and reaches a byte-identical `--json` report from both. A file that is neither is
  still a usage error and now names both accepted shapes; a result whose `provenance` is `null` is still
  reported as unverifiable rather than mistaken for a bare block.

- **A fourth native kernel: the scan's innermost bulged alignment.** `_best_with_removed_base` was 57% of the
  off-target scan's self time after the cheaper Python wins — a million calls over 2 Mb, two per PAM-positive
  anchor — and the previous round measured three Python variants that all bought the reject path with the
  survivor path and shipped none of them. Moved to the Rust crate (`rust/src/align.rs`) behind the same
  fallback-plus-parity contract the FM-index, k-mer and haplotype kernels keep: **43% off a whole scan**, with
  byte-identical results pinned by a 30,000-case differential against the Python path, which is itself pinned
  against the naive definition. A scan that took 2.62 s at the start of this work now takes 1.16 s.

  Writing the kernel surfaced a latent trap in the Python it mirrors. The function documented but never
  checked its precondition that `longer` is exactly one base longer than `shorter`; violated, it raised
  `IndexError` for most shapes and, for a two-base-longer input, silently returned a **wrong alignment**
  (`("ACGTAC", "ACGT")` gave `(0, "ACGTC")`). Unreachable from the scan, which slices the window to exactly
  `n + 1` — but the native kernel had to decide what to do off-contract, and making both refuse is what lets
  the parity claim hold everywhere rather than only where the caller happens to be correct.

- **Capping the menu is pinned as returning a prefix of the full ranking.** `--max-per-chemistry` is applied
  after the composite sort, so "the top three" means the first three of "all of them" rather than three of
  them. That the cap keeps the *best* of each chemistry was already covered; that it keeps them *in order* was
  not. The fixture lists candidates out of ranked order deliberately — sorted, it cannot distinguish a cap
  applied before the sort from one applied after.

- **Two documented "this must not matter" claims are now checked.** `--render-candidates` caps the drawing,
  not the data: the CLI help, the web request model and a handler comment all say the JSON and TSV exports are
  never capped, and nothing checked it. A prime design yields ~90 candidates; a leak would have written three
  of them to the JSON a pipeline consumes, with only the HTML mentioning the other eighty-seven. And a cohort's
  written artifacts must not depend on worker count — the existing parallel-vs-sequential test compares
  in-memory summaries and never uses `output_dir`, which is the surface the temp-file collision fixed in the
  previous round actually lived on. Both hold; both are pinned.

- **The specificity score is pinned as independent of the display filter.** `specificity_score` is
  `1 / (1 + Σ reported + subthreshold_score_sum)`, and the second term exists so the reporting cut-off decides
  what is *shown* and not what is *counted*. Measured across the whole range on a reference carrying four
  graded near-matches: the displayed site count falls from 5 to 1 while the score stays at 0.216718 to six
  decimals, the tail absorbing exactly what leaves. The pieces were unit-tested — the formula includes the
  tail, merging two nick reports sums it, the engine produces a non-zero one — and the property they exist to
  produce was not. Its failure has a direction: without it, raising `--cfd-threshold` would drop sites out of
  the sum and the aggregate safety number would go **up**, so a guide could be made to look more specific by
  asking to be shown less. Pinned as an equality across thresholds and, separately, as the inequality that
  showing less must never score better.

- **`aforge lift`'s documented promises are now checked.** Its help says the output "pipes straight back in"
  to `--region`, that an unmappable locus prints `UNMAPPED` rather than being dropped ("a shorter list is a
  smaller search"), and that the run exits non-zero. All three held and none were tested; the two commands sit
  on opposite sides of the tool, one formatting a `GenomicInterval` and the other parsing one, and the promise
  is the only reason the liftover is usable from a shell.

- **Five checks that could pass while examining nothing now have a floor.** A test whose only assertion is
  that a scanned collection is empty — `assert not broken` — is satisfied perfectly by finding nothing to
  check, and that is invisible in a green run. Measured, not argued: neutralizing the prose corpus in
  `test_readme_documents_the_cli.py` left **five of its six tests green**, including "every local link
  resolves" and "every module path the prose cites is importable" — both had been checking zero of each.
  Floors added to the two prose scans, the docs cross-reference scan, both shell-parity parameter sets, and
  the cohort/design parity check, each mutation-checked by neutralizing its own extraction. The rule is
  recorded in `openspec/project.md`, since the next check of this kind is written next round.

- **The README's CLI claims are now checked.** 1,400 lines of specific, checkable assertions and nothing
  checked any of them. Three guards: every command the README *invokes* exists (read from shell fences and
  inline code, so prose and mermaid node labels are not mistaken for commands), every `--flag` it documents
  exists on some command (with the flags belonging to docker, ruff, pytest, uvicorn, maturin and mypy listed
  by owner), and the cell-context claim names the vertical that consumes it. Two claims were verified in
  passing and hold: every `design()` capability really is reachable from `aforge design`, and all eight
  documented commands exist.

- **The cohort endpoint now accepts everything the single-design one does.** Checking `design()`'s parameter
  list against each shell is the query that has found the most in this project. Run against the web API it
  turned up a gap inside the API: `DesignRequest` carried four options `BatchRequest` did not, all four of
  which `aforge batch` has had all along. `offtarget_regions` — so the most expensive path was the one that
  could not be scoped; `allow_ng` / `allow_spry` — a cohort is where a variant with no actionable NGG guide is
  certain to turn up, and the fallback built for that case was unreachable, so the item came back empty with
  nothing the caller could do; and `cell_context`, so no out-of-distribution flag was obtainable on the batch
  path. A structural test now fails when an option is added to one request model and not the other.

- **Every setting recorded in provenance is now pinned to a route that reaches a reader.** The report footer
  is a curated summary, and `PROVENANCE_FOOTER_OMITTED` is the mechanism that forces "every omission must be a
  decision". It had one entry — `config_snapshot`, excused as "rendered inline beside the results". The
  snapshot holds eight keys; two are rendered inline, and the footer was skipping all eight on the strength of
  those two. `CONFIG_SNAPSHOT_ROUTES` now records where each key reaches a reader, every route verified by
  varying the setting and reading the rendered page, and a test fails when a new key is added without one.

- **Every candidate now says where in the genome it edits.** A prior round labelled the report's coordinate
  convention on the reasoning that "a printed cut site is the number a reader pastes into a genome browser" —
  and then the coordinates themselves went unaudited. SpCas9 printed `cut 117` inside the reagent line, a bare
  integer with **no contig**. Prime editing printed no genomic coordinate at all: five candidates differing
  only in RTT length, none saying where the edit lands. Base editing gave a protospacer-relative window and no
  locus. Rendering a report and searching the whole page for a contig name returned nothing — not one `chr…`
  token anywhere, while the provenance block described the convention those absent coordinates were in. A
  locus without its contig cannot be opened in a browser and is not even unique in a cohort report spanning
  genes. `CandidateReport.locus` now carries the contig-qualified interval plus the cut or nick site, on all
  three chemistries, and reaches the HTML page, the printable PDF and a new `locus` TSV/Parquet column
  (`EXPORT_SCHEMA_VERSION` 4 → 5). An unplaced candidate still reports `None` rather than inventing one.

- **A non-finite allele frequency is pinned as rejected.** `nan > 1.0` and `nan < 0.0` are both False, so a
  range check written `if af > 1 or af < 0` admits `NaN` — which then compares False against every MAF
  threshold and silently drops the variant from the search. The validator is written `not 0.0 <= af <= 1.0`,
  whose negation catches it: correct by construction and one refactor away from not being. The same property
  already cost this project a fix in `RankingWeights`. Pinned for gnomAD and for the haplotype panel, which
  feeds the same ancestry stratification.

- **The OOD detector's conservative degeneration is pinned.** Checked alongside the conformal shortfall,
  since both ask what a mechanism claims when the data is too thin: with a one- or two-point reference the
  threshold collapses, and it collapses toward refusing to vouch for anything rather than toward vouching
  for everything. A far input is never called in-distribution. Now a test, not a check done once.

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
- **The scan kernels release the interpreter, so a threaded cohort actually scales.** `aforge batch --workers 4` ran at **1.6x**, not because the work was serial but because a PyO3 function holds the GIL unless it says otherwise: four worker threads were taking turns to run Rust that never touches a Python object, and 80% of a run is inside that Rust. `scan_strand`, `evaluate_anchors`, `fm_build` and `fm_suffix_array` now release it for the duration (`Python::detach`), borrowing their sequences through `PyBackedStr` so a contig is not copied per call — a copy per scan would trade the GIL for a memcpy of the genome. On a ten-variant cohort over a 2 Mb contig, in one process: **1.75x on two workers, 2.92x on four, 3.98x on eight**, with byte-identical per-item summaries.
- **A design scans each spacer once, in every vertical.** `RunScanner` binds the ten run-wide arguments every off-target scan shares — the reference, the population and haplotype sources, the patient VCF, the region restriction, the two reuse stores — and memoizes on the two that vary: the spacer, and the locus excluded from its own report. Two verticals were paying twice. Prime memoizes its *merged* report under the pegRNA pair, so a peg spacer paired with two nicking guides was scanned twice and a shared nicking guide once per pegRNA (1 of 6, 4 of 10 and 1 of 4 scans on three measured loci). Base editing scans per window, and two deaminases over one protospacer are two windows with one spacer (1 of 2 at a measured locus). Across a ten-variant cohort: **81 whole-genome scans became 58, every one of them distinct**. The nuclease vertical had no duplicates and goes through the same scanner, so a future enumerator that repeats a spacer cannot pay for it twice unnoticed.
- **The off-target scan is ~6x faster on a 2 Mb contig** (0.647s to 0.108s profiled, 1,996,749 Python calls to 341), with every step byte-parity-pinned against the pure-Python path: per-anchor waste removed, evaluation batched into one FFI crossing, the whole strand scan moved into the kernel, and the searched-base count folded into one pass. A full `design()` with the off-target search on now spends 81% of its time inside the kernel and 0.13s in everything else the library does.
- **The searched-base count is one pass, not eight.** `_resolved_base_count` is what a report means by "over N bases" — the unambiguous A/C/G/T of the region actually scanned, so an `N`-padded assembly gap cannot be counted as searched — and it made eight `str.count` passes over the contig, deliberately not upper-casing first because a copy of a chromosome is a quarter-gigabyte transient in a bounded-memory path. That trade was measured and argued when eight passes were negligible beside the scan; three rounds of scan work later they were about a fifth of it. The native kernel does the same count in one pass, also without copying (**~7x** on a 2 Mb contig), and both cases stay counted on both paths, because the upper-casing on the way in is a `pyfaidx` default rather than an invariant here.
- **The whole strand scan runs in the native kernel, anchoring included.** Batching the evaluation left the anchor *enumeration* in Python — a `re.Match` and a method call for every PAM occurrence, 250,000 per 2 Mb strand — which profiling then showed as the single largest cost in the scan, above the kernel it was feeding. `scan_strand` does the loop: IUPAC PAM matching at every position (overlapping, as the zero-width lookahead it replaces), the alignment, and the `N`-window rejection, returning only the hits. **2.4x** on a 2 Mb strand at the default budget against the loop as it stood two rounds ago, and 1.7x against the batched-evaluation version — paired, alternating, minimum of eleven, one process on a loaded machine. Byte-identical on 200 randomized strands including `N`-rich sequence, spacers longer than the contig and four PAM patterns; the seed-prefilter path (tight budgets) keeps the Python loop, and an extension built before this kernel falls back to it by name.
- **The off-target scan crosses into the native kernel once, not once per anchor.** `evaluate_anchor` is called for every PAM occurrence in a contig — 250,000 on a 2 Mb strand, roughly 180 million on hg38 — and the scan keeps two of them, so every rejected anchor cost a Python frame, an argument tuple and an FFI crossing on its way to being discarded. The new `evaluate_anchors` kernel takes the whole anchor list in one crossing and returns only what scored, with the anchor position carried in the tuple. **1.47x** on a 2 Mb strand at the default budget (paired, alternating, minimum of fifteen, one process on a loaded machine — read the ratio, not the milliseconds); **1.09x** at a tight budget, where the seed prefilter dominates and there is little left to win. Hits byte-identical, pinned by a randomized parity test against the per-anchor kernel including the shapes that port had to decide about, and the FM-index scanner batches the same way. An extension built before this kernel falls back to the per-anchor path by name.
- **The off-target scan does no per-anchor work that only a hit needs.** `_scan_one_strand` walks every PAM occurrence — 498,957 of them on a 2 Mb contig, about 180 million on hg38 — and for each one it called `_evaluate` (whose only job is to re-answer "is the native kernel built?", one answer per scan), materialized `match.group(1)` (the PAM string, used only if the anchor becomes a hit), and sliced `seq[start:pam_at]` to look for an `N`. The dispatch is now made once per scan, the PAM string is read only for a hit, and the `N` check is a `find` over the same span with no copy. **1.33x** on that contig at the default budget — paired, alternating, minimum of seven, one process, loaded machine, so read the ratio and not the absolutes — with the hit tuples byte-identical and the FM-index path given the same treatment.
- **`aforge --cache-dir` redirects a process that has already read a setting.** The flag exports `ALLELEFORGE_CACHE_DIR`, which every consumer resolves through the settings singleton, and its own comment said that is "safe because the singleton loads lazily, after this". True of a fresh `aforge` process and false in a notebook, an embedded caller or a test suite: those already hold a singleton, so the flag silently redirected nothing and the run read and wrote the *default* cache while the user believed otherwise. It now drops the loaded singleton as well. Found because a test asserting a cold genome index passed alone and failed in the suite — it had been mapping an index out of the developer's own cache.
- **The supply-chain audit can fail again.** `pip-audit --strict --desc || true` and `cargo audit || true` exit 0 whatever they find, so a run that found advisories reported a green "Supply-chain audit" to anyone reading the checks list — the one place a reader looks for exactly that answer. The intent was right (the advisory databases move independently of this code, so a newly-published advisory must not turn an unrelated PR red) and the mechanism was not: the job is now `continue-on-error: true`, which is non-blocking *and* visible. A guard refuses any workflow step that discards its command's exit status, and requires the job excused from `make ci` for being advisory to actually be marked advisory.
- **The conda recipe ships the same `aforge` as the wheel.** `pyproject.toml` points the console script at `alleleforge.cli:run` — a shim that answers a missing `typer` with the install line instead of a raw `ModuleNotFoundError` traceback, which is the whole reason it exists. `conda/meta.yaml` pointed at `alleleforge.cli.main:app`, the target the shim replaced. It worked only because the recipe happens to require typer, so the defect the shim prevents was one `run:` edit away from returning on the channel where a user is least likely to have the extra — and conda-build generates that script over the one the recipe's own `pip install .` already installed. The guard derives the expected target from `pyproject.toml`.
- **An undefined generalization gap is a result, not a usage error.** `aforge bench run cas9-efficiency` prints `spearman=undefined`, says why, records `primary_value: null` and exits 0. `aforge bench gap cas9-efficiency` exited **2** — this CLI's *usage* code, meaning the caller invoked it wrong — for the same fold of the same task scored by the same model. The caller invoked it correctly: the reference baseline predicts the train-fold marginal by construction, so its rank correlation is undefined on every dataset, and two of the five shipped tasks are permanently in that state. `GeneralizationGap` now carries `gap: float | None` with `undefined_fold` and `undefined_reason`, `generalization_gap()` returns the absence instead of raising it, and the command prints a NOTE and exits 0 (an unknown fold name is still a usage error). The calibration study, which had rebuilt the honest row by catching that exception, now reads it from the library.
- **Provenance names the sequence backbone that produced the embeddings.** `EnsembleEfficiencyScorer` is projection heads over an embedding; with a real backbone — Nucleotide Transformer, Caduceus, Evo2, each with its own card, licence and pinned checksum, each resolved through the consent-gated model zoo — the embedding is what the numbers are made of. `backbone_checkpoint()` exists, says "for provenance" in its first line, and had no caller: `cas9_model_checkpoints` stamped the ensemble card and stopped, so a menu scored through gated, licence-checked, checksum-pinned weights named none of them. `CachedEmbedder` — the documented way to use a real backbone — also forwarded `name`, `version` and `context_window` but not `model_checkpoint`, so even a caller who asked got `None`. Both fixed, with the weight-free stub still adding nothing.
- **The cache sweep explains the artifacts it could not check.** `aforge cache verify` counts what it did not check and then sent the reader to `aforge data list` — a sentence written when the dataset registry was the only one with a shell, and stale from the moment the model zoo got one, in the round that gave it one: two thirds of the unchecked rows are model checkpoints that command has never listed. `cache_sweep.UNCHECKED_REMEDIES` maps each `CacheCheck.kind` to the command that explains it, the sweep's caller prints one line per kind it actually counted, and a guard derives the kinds that can be reported unchecked from the sweep's own source, so a new store cannot be counted without a reader being told where to look.
- **An empty flat table now says why it is empty.** `DesignReport.rationale` describes itself as the field "without [which] a report can be empty with no explanation anywhere in it ... every renderer would otherwise drop it" — and the TSV and Parquet exports dropped it, because the `rationale` they carry is a *per-candidate* column. A run that produced no candidates wrote a header row and nothing else, which reads as "no design exists for this variant" when what happened may have been that a chemistry never ran: its trained model refused by the licence gate, its package not installed, its search hitting a defect. The `#` comment block (and Parquet's file-level metadata) now carries the run's whole account when there are no rows, and, when there are, only the lines saying a chemistry could not run — a skipped prime vertical is invisible among cas9 rows, and the full rationale on every export would bury the result the reader came for.
- **Provenance no longer names a model that scored nothing.** `_collect_model_checkpoints` stamped a card for every *eligible* chemistry's scorers, and a chemistry can be eligible and never run: `_run_chemistry` catches an expected failure, writes a `skipped` note and returns no candidates — most often because the trained model itself was turned away by the licence gate, a missing extra, or an unverifiable checkpoint. So one artifact said both things: `prime: skipped (LicenseError: license 'research-only' forbids commercial use of model 'deepprime')` in the rationale, and `models: [deepprime, ...]` in the provenance block a reader consults to learn what a result was scored by. A vertical that raised now records no card, and the note explaining why is unchanged.
- **A parallel cohort now records which genome it screened against.** `design_many` takes a `reference_factory` when `max_workers > 1`, because a pyfaidx handle is not thread-safe to share — and the run header treated that as "there is no run-wide reference to describe", recording `None` for the build, the reference shape and the file identity. So a parallel `aforge batch` wrote a cohort summary that could not say which genome the cohort was screened against while the identical serial run could, and three of the seven inputs `_refuse_a_mismatched_resume` compares were `None` on both sides — including the two that tell two same-shaped FASTAs apart, which is the case that guard exists for. The factory is already opened once before any worker starts (to build the `.fai` rather than let the workers race for it); that open now describes the run.
- **A resume the manifest could not vouch for now says so.** `design_many` refuses to resume a manifest opened under different result-determining inputs — a different genome, seed, intent or ClinVar release — by comparing its `_run` header against this run. It compares what is *there*, so a manifest written before the header existed, or by a version missing one of the critical keys, returned quietly: exactly the run whose provenance nobody recorded. Those manifests stay resumable on purpose (making old work unusable would be worse), but a skipped item reads as work already done, and `skipped: 14` was indistinguishable from fourteen verified skips. The run now records why the check could not run in its provenance under `resume_unverified` — carried by the summary TSV, the cohort JSON and the web batch response — raises a `UserWarning` for a Python caller, and prints it on stderr from `aforge batch`, not behind `--verbose`.
- **An index and a reference now have to agree without being labelled.** `search(..., genome_index=...)` anchors PAMs over the index's sequence while reading bases and coordinates from the reference, so an index of a different genome yields hits silently in the wrong place. The guard on that seam compared build names under an `if` requiring both to be present — and the index nobody wrote the genome down for is the one most likely to be the wrong genome. Contig lengths are recorded per index, cost nothing to compare and depend on no name (chr1 is 248,956,422 bases in hg38, 249,250,621 in hg19, 248,387,328 in T2T-CHM13), so a mismatch is refused whatever either side is called. `GenomeIndex.disagreement_with(reference)` is the library form of the question, for a caller holding an index and a FASTA.
- **`design(build=...)` defaults to the reference's own label, and refuses one it contradicts.** `build` says which assembly the input's coordinates are in; a `ReferenceGenome` carries the assembly it is. When they disagreed, exactly one was wrong and nothing said so — resolution used the argument, the provenance recorded the reference's label, and the run came back stamped with an assembly nobody asked for. The default made the reverse worse: `build` defaulted to the string `"hg38"`, so a caller who labelled their genome `mm39` and never touched `build` was resolving every ClinVar accession and rsID against hg38. It now defaults to `None`, meaning "whatever the reference is", and a stated build the reference contradicts is a `ValueError` naming both.
- **Two spellings of an assembly the alias table does not know are one assembly.** `canonical_assembly` lowercases its lookup key, so aliased names have always compared case-insensitively — and returned the *unaliased* name as written, so `GRCh38.p14` and `grch38.p14` compared unequal. Everything reads that as "different assemblies": a refused design, a rejected genome index. A new guard also derives the population the table must cover from `BUILTIN_BUILDS`, so a build added to the download registry and not to the comparison fails rather than silently comparing by spelling.
- **The off-target scan no longer auto-engages the FM-index past 1 Mb — it made the default path several times slower.** The threshold's stated justification was that the index build "only amortizes at contig scale". Measured on the real default path with the native crate present: 1 Mb one guide, linear 1.77s vs 4.85s (2.7x slower); 2 Mb, 3.61s vs 9.69s (2.7x); 8 Mb, 14.22s vs 65.19s (**4.6x**); and five guides sharing one 1 Mb contig, 9.75s vs 21.56s, so it does not amortize across guides either. The justification was backwards — it diverges with size rather than converging — and `scripts/native_speedup.py` had been printing `SLOWER` for this pair all along: the number was in the output and the decision was in the prose. The path itself stays, exact and parity-pinned, reached by asking (`use_fm_index=True`, or a supplied `genome_index=`). Hits are byte-identical either way, and the reproducibility golden is unchanged. Not measured, and so not claimed either way: a persistent cross-process index whose build is fully paid in an earlier run.
- **Breaking (pre-1.0), Parquet metadata keys:** the export's notes are keyed `note_NN_<name>` instead of `disclaimer` / `provenance_1..n`, so sorting the mapping — which is what a Parquet reader gets — reproduces the order the TSV prints the notes in. Until now document order and alphabetical order agreed only by coincidence. `schema_version` is `13`.

- **The TSV export leads with `#` note lines, and `EXPORT_SCHEMA_VERSION` is now `6`.** The HTML, PDF and
  JSON renders of a report all carry the research-use disclaimer, the coordinate convention and the
  provenance footer; the TSV carried none of them, so the one format a reader opens in a spreadsheet showed
  efficiencies, specificities and genomic loci with nothing saying they are uncertain computational
  predictions, against which genome, in which coordinate convention. (The README claimed the convention was
  "stated in the report's own provenance block" for the TSV, which has no provenance block.) The notes lead
  the file as comments, as in VCF, GTF and bedGraph, so the column header is still the first non-comment line
  and a comment-skipping reader — `polars.read_csv(..., comment_prefix="#")`,
  `pandas.read_csv(..., comment="#")`, `read.delim(..., comment.char="#")` — gets a byte-identical table,
  which is checked by parsing the file both ways and comparing. A reader that skips nothing sees a different
  first line, which is what the schema version leading every row exists to signal.

- **Complementing a sequence uses `str.translate` instead of a per-base dict lookup.** The off-target scan
  takes whole-contig reverse complements, and the generator behind them ran **four million times** on a 2 Mb
  reference — the third-largest cost in a profile. 96% faster (27×) in isolation, on both plain ACGT and the
  full IUPAC alphabet. `translate` leaves an *unmapped* character unchanged where the dict lookup raised, so
  this is equivalent only while every base a `DNASequence` accepts has a complement entry; the two sets are
  equal, and a test now holds them equal, because the failure mode of adding a base to one and not the other
  is a wrong sequence rather than an error. Together with the early-exit above, a default 2 Mb scan went from
  **2.62 s to 1.90 s (-27%)** on the same machine, with the reproducibility golden unchanged.

- **The innermost comparison of the off-target scan stops once the mismatch budget is blown.**
  `_best_ungapped` priced all twenty positions with a `sum()` over a generator and then compared against the
  budget — about half a million calls over 2 Mb, and 10.5M generator iterations, the largest single cost in a
  profile of the scan. Stopping early is exactly equivalent, since an over-budget alignment is discarded and
  its true count never read; on random sequence a 4-mismatch budget is blown after about six positions.
  Measured **60% faster in isolation** at the default budget (51% at 6), and **10–16% off a whole scan**
  depending on the bulge configuration. Results are byte-identical — the reproducibility golden is unchanged —
  and a randomized differential against the naive full-count definition now pins that. The same reasoning was
  already written out in `_best_with_removed_base` directly below it, which stops its prefix pass on the same
  condition; this function had simply never been given it.

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

- **The honesty principle claimed every prediction ships with a *calibrated* interval. Out of the box, none does.** A design over a 200-candidate menu reports `calibrated=False` on every efficiency and every `p_intended`, with `method=heuristic` — which is correct: the flag exists precisely so a scorer can say it has not fitted its interval against held-out coverage, and conformal recalibration and the trained models are what set it true. Four documents asserted the one thing the flag exists to deny — `SPEC.md` and `CONTRIBUTING.md` (where a contributor learns what honesty means here), `openspec/project.md`, and the README, twice. All now say what ships: an interval, the method behind it, and a `calibrated` flag. An interval *asserted* to be calibrated when it is not is the confident wrong answer wearing the honest one's clothes, which is the failure mode the principle is written against.
- **"Population-aware by default" said a bare install searches population variation. It does not.** Nothing of gnomAD ships, `design()` takes `gnomad=None`, and a scan with no population source is reference-only — which the code says in the report's search description, in `offtarget_sources`, and in a warning when ancestries were requested that nothing could answer. The README has a whole note headed "The three safety inputs are opt-in files, and the scan is reference-only without them." The two places that *define* the principle — `SPEC.md` and `CONTRIBUTING.md` — stated it as something the tool does by default. Both now state what is true and keeps the principle's force: population-awareness is the default **behaviour** when a source is present, not a default **dataset**; an empty ancestry breakdown means *not measured*, never *clean*. Derived guard: while `design()`'s population source defaults to `None`, no document may claim a default run is population-aware without naming the file requirement.
- **`SPEC.md` required a result to be re-derivable from its provenance block; it is not.** `Provenance` carries the version, seed, reference build, timestamp, pinned datasets and checkpoints, and a config snapshot — and no **variant**, which `build_report` says outright where it records one ("no provenance fallback — the config snapshot carries no variant field"). The block says *how* a run was configured and not *what* was asked of it, so a bare `.provenance.json` sidecar cannot be re-derived from. That is a defensible design — a patient variant in a file meant to be passed around is a different artifact — and every other document already says the narrower true thing ("re-derivable from config + seed", "reproducible from its inputs"). The one that stated the broad version was the numbered principle that *requires* it. It now says what else is needed and where the variant actually lives, and a derived guard fails on the broad claim while `Provenance` has no variant field.
- **"No outbound network call" has a second exception, and it is a different kind.** The entry above named consequence annotation. A **trained model** an operator has enabled is the other path off the machine: if its checkpoint is not already cached, the request fetches it. The two are worth keeping apart rather than merging into one warning — the first transmits the user's variant to a public server, the second downloads a pinned, hash-verified artifact and transmits nothing of theirs. Note which artifacts got this right unaided: the page's banner and the OpenAPI description claim only that *no sequence data* leaves the deployment, which stays true under both. It is the prose making the broader "no outbound network call" claim that needed the second exception. The guard now keys on both capabilities.
- **Five documents stated the no-egress guarantee without its exception; the page had it right all along.** `app.js` conditions its banner on `vep_enabled` with the reason written beside it — "That is the sentence a reader checks before pasting a patient variant, and enabling the VEP annotation makes it false" — and the OpenAPI description branches the same way. The README, `SPEC.md`, `docs/api/web.md`, `docs/deployment.md` and the serving module's own docstring (which lists it among "two invariants from the specification") all stated it flat. Consequence annotation sends the chromosome, position and both alleles to a public server; it is doubly opt-in — the operator enables it because their server makes the request, the client asks per request because the variant is theirs — and all five now say so where the claim is made. The guard is derived from the capability rather than the wording: while the API can be configured to annotate consequences, a paragraph making the claim must name the exception, and three of the five were found by the guard rather than by reading.
- **The README said the k-mer prefilter "auto-engages only when the seed is selective" and "stays because it is exact and free".** `SEED_PREFILTER_AUTO_ENGAGES = False`: it does not auto-engage at any budget, and the module comment that sets the flag ends with the sentence "What is removed is the assumption that it is free." Same defect as the FM-index entry above, on the sibling flag, in the same note. The prose now carries the code's own measurements — 1 Mb, one guide, no bulges, brute force/seeded: 48/139 to 58/157 with the crate, 60/226 to 81/282 without, and 0.79–1.65x for the `bisect` repair that was left open and then measured — and says what does keep the path: it is a proven superset by the pigeonhole bound and stays parity-tested. The derived guard is now keyed per flag, so each half inverts with its own.
- **The README still called the FM-index "the genome-scale search" after the engine stopped using it.** `FM_INDEX_AUTO_ENGAGES = False` carries the reason in the source — the threshold "turned the *default* configuration 2.7x slower at exactly the genome scale the tool exists for", and `scripts/native_speedup.py` "has been printing SLOWER for this pair" — while the README listed the kernel's speedup as "genome-scale" in a table whose neighbouring row is scrupulous about being a net cost, told a reader to build the crate "for the genome-scale path", and twice named it *the* search. The rows and the prose now say what the code decided: the path is exact, parity-pinned, opt-in (`use_fm_index=True` or `genome_index=`), a net cost at every size measured because the per-anchor work it avoids is now C-level, and worth having for a caller who wants a memory-mapped index for *memory* rather than time. The reason to build the crate is the kernels that *are* on the hot path. A derived guard now fails if any document presents the path as the default while the engine's auto-engage flag is off — and inverts with the flag.
- **The FM-index cache wrote its parts in place while its sibling store promised atomic writes.** `alleleforge.cache` states it as a property callers may rely on — "each value is written to a temp file and then renamed into place, so a crash or a concurrent writer can never leave a half-written entry a later read would trust (the cohort's parallel path relies on this)" — and nothing tested it. The other on-disk store, holding the artifact that is three orders of magnitude larger, used `write_bytes` / `write_text` directly. Two runs sharing a cache dir and starting together is enough: the second truncates `bwt.bin` while the first's `meta.json` is already there, and a third process reading between them fails the length check and is told its cache is corrupt. Fail-closed, and a corruption report for a race is still a bug. Every part is published temp-then-rename now, with `meta.json` last because `build` treats it as the marker of a finished directory — and the atomic-write property of *both* stores is checked.
- **The job store is bounded in bytes, not only in records.** `JobManager` evicted oldest-terminal-first past a thousand records, on the reasoning that "a long-lived server would otherwise grow `_jobs` without bound" — written when a record held a polling envelope. A finished **design** job keeps the ranked menu *and* the report built from it, measured at **1.25 MiB of JSON** for a 200-candidate menu on a 30 kb contig, so the count cap permitted well over a gigabyte of retained results — and the entry above routes every design the served page runs through this store. Both bounds now apply (1000 records, 256 MiB), whichever is reached first, never evicting an in-flight job. The size is measured once when the work finishes, by introspection, because the manager schedules opaque callables and must not learn what a design is. `create_app(jobs=JobManager(...))` lets an operator size it — a parameter that did not exist until the deployment guide was caught describing it.
- **The served page ran a single design five times to produce four downloads.** The single-variant panel rendered its report from `POST /api/design?format=html` and then served every download button from another `POST /api/design?format=…`, so a reader who looked at the report and saved the PDF, the JSON, the menu and the HTML paid for five variant resolutions, five enumerations and five off-target scans — the expensive part on a real genome. And no two saved files were guaranteed to be the same run: the PDF on a desk and the JSON beside it agreed by determinism rather than by identity, and differed at least in their timestamps. The cohort panel had already been moved onto the job route for this reason; the single-variant panel now submits once and renders the report and every download from that finished job, falling back to a fresh design — announced — only when the store has forgotten it. Verified in a browser: four download clicks, four `GET /api/jobs/<id>/result?format=…`, zero `POST /api/design`, one job id throughout.
- **The cohort TSV fallback left a progress message on screen after the file had arrived.** Driven in a browser — run a cohort, restart the server, click **Download TSV** — the download works and the status line still read "The server no longer holds that run — designing it again to build the table…". A progress message left standing after the work finished reads as work still running. It now ends with a line that also says the thing the ordinary path has no need to: these rows come from a *second* run of the same cohort, so the table is not the same document as the JSON downloaded from the first.
- **An unranked leaderboard entry keeps its measurements.** Listing a submission whose primary metric is undefined, rather than ranking it, was the right call — and the first rendering dropped it to a sentence, so the calibration error and out-of-distribution share it *did* measure vanished from the page. Qualifying an entry must not mean discarding what it established. Unranked entries now render as their own table — separate from the ranked one, because appending them underneath would be an ordering and the whole claim is that they cannot be ordered — carrying model, submitter, ECE, OOD share, split and the reason there is no rank. Found by opening the artifact rather than asserting on its substrings.
- **`SPEC_V2.md` said the native kernels were "not yet on a production hot path".** They are: the reference scan dispatches to the native per-anchor evaluator and bulged-alignment kernels from its innermost loop — twice per PAM-positive anchor, about a million times over 2 Mb — resolved at import so the availability check stays out of the loop, and pinned byte-identical to the Python path, so an unbuilt crate changes a scan's *speed* and not its results. Building the crate is still opt-in; being used once built is not. The claim was true when written, which is what makes it the dangerous kind — a round found the general form some time ago ("'not yet implemented' in docs is a claim with an expiry date and no alarm on it") and put an alarm on the web endpoints. This is the same alarm for the kernels, derived by reading the dispatchers out of the module, so a third one wired in tomorrow is covered without anyone remembering to add it.
- **The cohort table's note block now says whether an off-target search was run at all.** `aforge batch --no-offtarget` writes a per-patient table whose `worst_offtarget`, `best_specificity` and `offtarget_sources` cells are blank on every row. Each cell is honest — a search that did not happen must not report `0.0` and `1.000`, and it does not — and the file as a whole was not: a collaborator opening it sees empty safety columns and nothing telling them why. That is exactly what the `#` note block exists for, on its own stated grounds that "a row per patient with a bare `best_specificity` and no statement of which genome was searched is not interpretable". The mixed case gets its own sentence naming how many of how many, and a *failed* item is not counted as an unsearched one — it never got as far as a search.
- **A menu ranked with no off-target search said the safety term "uses the worst nominated site".** A candidate with no off-target report scores a full `1.0` on safety — the reassuring extreme for an axis nobody measured, chosen deliberately because penalising an unmeasured axis is a policy this project has no basis for, and flagged `offtarget-not-searched` on every candidate. That is the right decision about the number and it has a consequence for the *ordering* that nothing stated: with `--no-offtarget` every candidate takes the same maximum, so 30% of the ranking weight separates none of them and the order is decided by efficiency, cleanliness and simplicity alone. The rationale meanwhile described a computation that did not happen — in the same sentence that already qualified the lesser version of it ("no candidate here carries ancestry annotation, so there is no per-ancestry worst to take"). It now says which case this run is, including the mixed one, where it names how many of how many were not searched.
- **`chr1:15000:C>N` resolved, designed, and blamed the reference for an assembly gap that was not there.** The variant parser admits `ACGTN` in both alleles. In a **ref** that is correct — a VCF record at an assembly gap says `N`. In an **alt** it is not a base anyone can write: no oligo carries it, no editor installs it, no outcome distribution has it as a category. So the request went four layers down and came back as `prime: eligible but no actionable candidate enumerated — … the RT template spans an assembly gap (N) (200)`, on a contig of pure ACGT, sending the reader to look for a gap in their FASTA when the `N` was in their own input. Every other IUPAC code was already refused by the parser as an unrecognized variant; `N` in an alt is refused now too, naming what it is and where `N` *is* legitimate — and the enumerator's gap message is true again.
- **The off-by-one refusal printed two coordinate conventions under one set of digits.** `chrom:pos:ref>alt` is read as a 1-based VCF record and printed with a 0-based position. When the asserted ref sits one base *right*, the refusal spells that out — it is the "this tool does not accept its own printed variant" case. One base *left* got the terse branch: `reference mismatch at chr1:15000 … — the asserted ref is one base left; try chr1:15000:C>A`, which reads as "position 15000 is wrong; try position 15000". The header is 0-based and the remedy is a 1-based input, in the one message whose whole subject is a coordinate being off by one. Both directions now state the convention, and a test *runs* each suggestion and checks it resolves to the base the caller asserted — a remedy that does not resolve is worse than no remedy.
- **The note pointing at the withheld alleles named two routes, for four audiences.** `RANKED_MENU_SOURCE` is rendered into the HTML report, the PDF and both flat exports' note blocks, and said the full spectrum is written by `aforge design --json` and returned by `menu_to_json` — a terminal and a Python API. The served page displays that sentence to the audience the README describes as "users who will not touch a terminal"; an earlier entry gave them `POST /api/design?format=menu` and a **Download full menu** button and left the sentence pointing at the two routes it already had. It now names one route per surface, each pinned by a test to a format, an endpoint, a button with a handler, and an importable function.
- **Two of the six PDF text extractors in the test suite did not unescape `\\(` and `\\)`.** Every assertion about the rendered page reassembles its prose from the `(...) Tj` payloads, and the research-use disclaimer this project prints on every render contains "(e.g. GUIDE-seq / CHANGE-seq / amplicon sequencing)" — so those two were already mangling the sentence they exist to protect, and the shared regex stopped at an *escaped* closing parenthesis, splitting one run into two. There is now one extractor, in `tests/pdf_text.py`, with its own tests for both.
- **The docs told a reader to run `aforge bench gap cas9-efficiency`, which refuses.** Once an undefined metric stopped being reported as `0.0`, that command exits `2` — the reference baseline predicts one constant, so its rank correlation is undefined on both folds and there is no gap to subtract. Correct behaviour, wrong example, and invisible to the four existing docs guards, which check that a documented command *exists* and that its flags exist rather than that running it works. The benchmark examples now use tasks the baseline can be measured on, and say in prose what happens on the ones it cannot; the preprint no longer lists "baseline Spearman" among the numbers the fixtures produce; and the Python snippet says `primary_value` can be `None` rather than printing it into a reader's first contact. **Every `aforge bench …` invocation in the docs and the README is now executed**, in file order in one directory so a chain's later commands get the files its earlier ones wrote. A command documented as refusing is allowed, and must record its exit code and be explained in the prose beside it. The guard shipped covering `aforge bench …` only; it now runs **every** documented `aforge` invocation that needs no file the reader supplies — `resolve`, `data list`, `data show`, the whole `bench` group, fourteen commands across five documents. An invocation naming a path no earlier command in the same file wrote (a reference genome, a cohort VCF, a gnomAD release) is the reader's to provide and is recorded as such, checked in both directions so the rule can neither swallow the population nor cover a command that reaches a genome.
- **The calibration study printed a Python `None` in a column of numbers, and its ECE figure would have crashed on an absent ECE.** Both are consumers of a value that can now be genuinely undefined, written before the absence existed. The study is the artifact this project offers as its calibration evidence — a cell reading `None` says nothing a reader can act on and reads as a bug rather than as a statement about what was measured; it now prints `undefined` and carries the reason beneath the table, as the generalization table beside it already did. `task_ece_figure` called `float()` on the ECE, so the one chart whose subject is honest calibration would have raised on an honestly-absent calibration — and had it not raised, a bar at zero there reads as *perfectly calibrated*. It now drops the bar and names the task in its subtitle. Both are tested against a table with a hole punched in it, because the shipped fixtures happen to define every ECE today — which is exactly how a consumer comes to be written without the case.
- **The benchmark spec required the placeholder the code had stopped returning, and nothing compared them.** `openspec/specs/benchmark-harness/spec.md` still said the degenerate answer for `spearman`/`pearson`/`roc_auc`/`pr_auc` SHALL be `0.0`, and that metrics with a bounded worst value "SHALL fail toward it" — two rounds after the code stopped doing either. A shipped contract that contradicts the shipped code is worse than a missing one: the next reader finds an argument for putting the defect back. The CLI spec has been checked against the real CLI for hundreds of rounds; **no test in this repo referenced the benchmark spec at all**. It now carries one machine-readable line per metric — the degenerate answer each gives — and a test calls every one of them with an input that determines no value and holds the line to the result, in both directions, so neither the list nor the code can shrink quietly.
- **Top-1 accuracy over an empty fold is undefined, not zero — and the whole battery is now held to that.** KL was corrected for the empty-fold case on the argument that it "is unbounded above, so it has no pessimistic value to fall back to", while "a correlation or an AUROC of 0.0, an accuracy of 0.0" was offered as an acceptable pessimistic answer for the rest. That argument does not survive a ranked table: those values are ranks, not fillers. The correlations and AUCs were corrected in the previous entry and top-1 was the last row still averaging an empty sum to `0.0`, which on an accuracy reads as "got every one wrong". `test_an_empty_fold_measures_nothing.py` now checks the invariant through `evaluate_fold` for every task kind, so a metric added to any battery is covered the day it appears.
- **An undefined benchmark metric is reported as undefined, not as `0.0`.** `spearman`, `pearson`, `roc_auc` and `pr_auc` answered `0.0` for inputs that determine no value — a constant series, a single-class fold, a NaN. That is not a neutral placeholder on a ranked board; it is a score. The shipped CRISPR-Bench reference baseline predicts one constant (0.5721 on every example), so its Spearman is **undefined on every fold** — and the harness published `spearman: 0.0` as `primary_value`, ranked it first on the leaderboard under "spearman ↑", and subtracted two of them so `aforge bench gap` printed `gap=+0.0000 (positive = worse on the held-out context)` as a statement about generalization. On AUROC the placeholder is worse than neutral: `0.0` is the *worst possible* score, so a fold nothing could measure was published as a perfectly wrong model. The same result object had the right answer three lines away — ECE has been `None` when undefined since it was written, "kept distinct from a genuine 0.0 so an empty run is not scored as perfectly calibrated". The ranking metrics now use it too: `primary_value` may be `null` with a `primary_undefined_reason` naming what would have produced a number, the board lists such a row and never ranks it, `bench gap` refuses with the reason, `bench run` says so on stderr, and the committed generalization figure drops two bars that were drawn at height zero — which read as "no drop" — and names them. Result `schema_version` is now `5`.
- **The integrity sweep reads the cache namespaces off disk instead of naming them.** `aforge cache verify` asked `OffTargetCache` for its entries, so it checked one content-addressed namespace and walked straight past the **embeddings** cache sitting beside it — the store that had checksum sidecars first, and whose existence is the reason the off-target one was found to be missing them. Every namespace under the cache dir is now swept, including ones this command has never heard of. A namespace opened without verification writes no sidecar, and its absence there is reported as `unverifiable` rather than corruption: the read path of a verifying store treats the same absence as a failure, and a sweep cannot tell from disk which kind of store a directory belonged to.
- **A corrupted FM-index now fails with its own named error instead of `KeyError: 'T'`.** Tampering that keeps the length passes every cheap check, so the first thing to notice is the LF walk itself — and what it did was fail a dict lookup ten frames down in `_locate_row`, for a condition this module has a named error and a one-line remedy for. The alphabet of an indexed text is exactly the keys of `c_table`, so a BWT character the rank tables do not count cannot occur in an index built here; the walk now says so, names the index, and points at `aforge cache verify --deep`. A corrupted table can also close the LF walk into a cycle, which used to hang; that is bounded and named too.
- **The cross-run off-target cache now verifies its bytes on read — an altered entry is refused, not served.** The key protects against serving the answer to a *different* question; nothing protected against serving a *different answer* to this one. Content-addressing says the inputs match; it says nothing about whether the bytes on disk are still the bytes that were written. Measured on a two-site scan, editing the cached JSON's site list to `[]`: cold `2 sites, worst score 1.000`; warm `0 sites, worst score 0.000` — a perfect-match off-target became a clean guide, silently, on the opt-in flag whose whole promise is that it changes no result. A truncated file would have raised on parse; an edit that stays valid JSON, or a flipped bit inside a number, would not. The **embedding** cache in this same codebase has verified its bytes since it grew a checksum sidecar — the input to a score, while the safety finding itself was unguarded. The namespace is versioned to `offtarget/v2`, as the embedding cache does, so entries already on a user's disk go inert rather than failing every read closed on a sidecar they never had.
- **`aforge design` no longer exits 0 when a chemistry hit an unexpected error.** A vertical that raises an unexpected exception is recorded as a defect note and contributes no candidates rather than crashing the design — deliberate, and the rationale says so where a reader looks. Reporting *success* for it is not. `aforge batch` already draws this line for failed items; `design` did not, so a corrupted `--cache` entry (now refused rather than served) took a whole vertical out of a menu, wrote a zero-candidate report, and exited 0. The menu is still written — the run happened and its rationale explains it; only the exit code changes, to `4`.
- **The cohort panel's TSV download no longer dead-ends when the server has forgotten the run.** Serving the flat table from the finished job stopped the page re-designing a whole cohort to format a result it was already holding — but the job store is bounded and in-memory, so a result can be gone while the cohort is still on the page, and the button answered that with `Download failed: 404`. It now falls back to re-running, **behind the 404 and after saying so**: the point of the change was never to spend the run twice, and doing it silently would be the old behaviour wearing a new URL. The endpoint's own `404` says the same thing in a sentence a client can act on rather than "unknown job", since a caller here has usually just watched that job finish.
- **`aforge design --json` printed no ranked menu unless `--out` was also given.** Every truncated outcome table tells the reader where the withheld alleles are — *"the full spectrum is on the ranked menu … `aforge design --json` writes it"* — and `--json`'s own help says "Also print the ranked menu as JSON to stdout". It was guarded by `if as_json and out is not None`, so on the simplest form of the command that note names the menu was **silently not printed**: the reader got the report they already had, three alleles of four, with nothing saying the document they asked for had been withheld. The guard had a real reason — without `--out` the report goes to stdout too, and two JSON documents on one stream is what `test_a_json_stream_carries_only_json` exists to prevent — but dropping one silently is not the way out of it. Without `--out` the menu now *replaces* the report on stdout: the caller named the menu, the report there is the default they did not ask for, and the stream still carries one document. (Refusing was the first fix; twelve existing tests run that invocation and parse stdout, which is how the better resolution was found — and the one test that then failed read a report field from a variable it had named `menu`.) The allele withheld in the test fixture is an `indel` byproduct, which is the question the outcome table exists to answer. Found by rendering a report and following its own instruction.
- **The provenance a reader audits said what the bytes hash to, not what they are.** `doench-2016-cfd`'s row pairs `source_url` — CRISPOR's upstream `mismatch_score.pkl` — with `sha256`, the digest of the *vendored JSON conversion* that ships in the package. Fetch that URL and hash it and you get a different value, and the only conclusion a pin offers for a mismatch is tampering: the one conclusion it exists to make impossible. `DatasetVersion.bundled` now answers what `sha256` alone cannot — *what is this the hash of?* — following `caller_supplied`, added for the same kind of reason one row over. Three surfaces say it, because a machine-readable record a human cannot read is half a record: the provenance JSON carries the flag, the footer every render shares reads `(bundled; the hash is of the file that ships)`, and `aforge verify --cache-dir` reports `ok (bundled)` rather than a bare `ok` beside a URL it did not check. A test reads the upstream digest out of the shipped file's own `_provenance.sources` and asserts it still differs from the pinned one, so a future vendoring making them identical revisits the reasoning rather than leaving it standing; another checks the three origins do not print identically. Schemas regenerated, golden updated.
- **`fetchable` meant "the two fields a fetch needs are set", not "a fetch would work".** `dataset_status` computed it as `bool(sha256 and source_url)` — structural, not semantic — so `aforge data show doench-2016-cfd` printed `fetchable: True` for a row whose URL serves CRISPOR's upstream *pickle* while its digest pins the vendored *JSON conversion*. The shipped file records both hashes under `_provenance.sources`, so the project already knew they differ. A reader taking the flag at its word would fetch the URL, check the pinned digest, find a mismatch and reasonably read it as tampering — the audience `aforge verify`'s hash contract exists for. A bundled row has neither need nor path for a fetch since `resolve()` was fixed, so the flag now means what its name says, pinned against **behaviour**: for every registered dataset, `fetchable` must agree with whether `resolve()` actually reaches the downloader, measured with an injected one that records the attempt. A second test reads the upstream digest out of the shipped file and asserts it still differs from the pinned one. The change also corrected `test_the_table_says_which_rows_can_be_fetched`, which asserted the old formula verbatim — a fifth derivation of the answer `dataset_status` exists to single-source, and the only thing that disagreed once the definition was fixed.
- **`resolve()` could not produce the one dataset that ships inside the package.** `doench-2016-cfd` — the matrix behind every specificity number the tool prints — is the only registry row that is both `bundled` and pinned, and `resolve()` went straight to the cache without ever looking at the bundled copy. On a fresh offline install it raised `ConsentError … is not cached`, telling the reader to download something the wheel already contains; and after any fetch it raised `ChecksumError` **permanently**, because the row's `source_url` serves CRISPOR's upstream *pickle* while its `sha256` pins the vendored *JSON conversion* — bytes that can never agree. Found as real three-day-old state on a development machine: a `.pkl` sitting under the name `cfd_matrix.json`. The correct bytes were present throughout; the file in `site-packages` hashes to exactly the pinned digest. `aforge verify --cache-dir` had already been repaired for this at its own call site, with a comment reading *"a bundled dataset ships inside the installed package and is never in the cache"* — a fact about the data, fixed at a caller, leaving the accessor every other caller uses broken. `resolve()` now returns the bundled file after checksumming it against the same pinned digest; non-bundled rows still refuse an unconsented fetch, and a bundled file that fails its checksum is still refused.
- **Twelve more export columns could invent a value for a prediction that was never computed.** R430 found the ancestry pair; an AST pass over `_row` shows nineteen of thirty-seven columns are renamed or derived on the way into the table, and twelve are the prediction family. Each takes the same mutation with the **whole suite passing**: an absent prediction rendering `in_distribution: True`, `calibrated: True`, `efficiency_low: 0.0`, `efficiency_high: 1.0`, `p_intended_in_distribution: True` or `bystander_burden_calibrated: True` — 3,294 tests green each time. `in_distribution: True` for something never predicted is a claim about the evidence, not an odd-looking number: it says the model was asked and answered inside its training distribution. `_row`'s own comment states the property that was unguarded — the columns are blank for an absent prediction, *"the difference between 'no interval was computed' and 'the interval is zero-width'"*. The file now carries a prediction fixture pair and the same three-check shape, and its title generalises: *No field may show a value for something that was never computed.* Both column lists are written out rather than derived as "the columns that differ", because under the mutation each exists to catch, a column drops out of its own population and the assertion never runs on it.
- **An unmeasured worst-case off-target score could be exported as `0.0` with the whole suite green.** `test_an_unmeasured_axis_never_renders_as_a_number.py` opens with *"No off-target-derived field may show a value when nothing was searched"* and derives its population from `CandidateReport.model_fields` **by name** — `"offtarget" in field`. The flat exports call the two ancestry columns `worst_ancestry` and `worst_ancestry_score`: off-target-derived, and neither name contains the substring, so both sat outside every check in the file. Turning an unmeasured `worst_ancestry_score` into `0.0` — the most reassuring value a worst-case column can hold, in the two tables a pipeline filters on — left **3,291 tests passing**. The file now also checks the export columns, from a fixture pair differing only in whether a search ran (the searched half carrying ancestry frequencies, without which the column is `None` even when searched and would not be in the population). Three checks keep the list honest, the last being that no column telling the two fixtures apart may be missing from it. Found while pinning something else: the Parquet and TSV of one run now agree cell-for-cell (50 rows x 37 columns), with the null-versus-empty-string rule stated rather than assumed.
- **`make install` could not run `make docs`, which `make ci` requires.** R427's lesson was that the environment making your gate pass is part of the gate, so I diffed this machine's virtualenv against a clean documented install: beyond the Rust crate and release tooling it held the whole **mkdocs** stack. `make ci` is `lint type test docs examples reproduce` and `make docs` runs `mkdocs build --strict`, while `make install` did not install the `docs` extra — so a contributor following CONTRIBUTING gets `make: mkdocs: No such file or directory`. The same defect as R427, one gate member over, invisible for the same reason. `docs` joins the install, and the guard is generalised from imports to *tools*: every executable the `make ci` targets actually run is enumerated from the Makefile and must come from an installed extra or be recorded (`node`, which `make lint` uses to parse the served page's script, is a system runtime pip cannot supply). R427's own CI check is corrected too — it demanded every suite-running job install the whole gate set, which is wrong since CI splits the gate across jobs and the `pytest` job has no use for mkdocs; the property that matters, and that `test` and `rust` actually violated, is that a job running the suite must install whatever a test imports *at module scope*.
- **`pytest` could not collect the suite from the documented install.** One `import polars as pl` at module scope, in `test_the_parquet_schema_is_declared_not_guessed.py`, and `core` was in neither `make install` (`[dev,cli,web,genome-light]`) nor any CI job that runs tests — so in a clean venv built from the documented command, collection is interrupted and **not one test runs**. At module scope an import failure stops the whole run, which makes it a broken gate rather than one red test. The guard written for it found a second: the `rust` job installs `[dev,genome-light]` and, by a deliberate decision with eleven lines of comment explaining it, runs *the whole suite* — while 56 test files import `typer` at module scope and 17 import `fastapi`. It stayed invisible because this machine's dev virtualenv has `polars` and **not** `pyarrow` or `numpy`, the other two members of the same extra — the signature of a package installed by hand to get past an error. `CONTRIBUTING.md` already stated the property as the reason `make install` exists (*"the gate you are about to run cannot pass … the same extras set CI installs, kept in one place"*) and both halves were false; the guard now checks both, deriving what it needs from `cli.main._EXTRA_FOR_MODULE`, the module→extra table the CLI already maintains to turn an ImportError into an install line. Verified in a clean venv from the corrected command: 3,210 passed.
- **`pip install alleleforge` shipped an `aforge` command that could not start.** The base install is documented as the light core, and it installs the console script — declared unconditionally, while `typer` lives in the `cli` extra — so the first thing a user of the documented install saw was `ModuleNotFoundError: No module named 'typer'`. `main._missing_dependency` exists for exactly this and says so in its docstring ("for the imports that fail before any check runs"), and could not help: it lives inside the module that cannot load, so the one dependency the command is written in was the one its own remedy could not reach. The entry point is now a shim in `alleleforge.cli` that answers for `typer` by name and re-raises anything else, because turning every startup error into an install hint hides bugs behind an instruction the reader has already followed. Verified in a clean venv: core-only prints `pip install 'alleleforge[cli]'` and exits 69; with the extra, `0.1.0.dev0`. Found from `conda/meta.yaml`, whose `run:` list omits typer while its own `test:` block runs `aforge --version` — an artifact nobody has built, whose self-test could not pass; the recipe now requires typer, and a guard checks its `run:` covers the package's base dependencies.
- **A guard that reads the docs could have failed on the paragraph explaining it.** The check added a round earlier says in its docstring that it reads *"every fenced `pip install`"*; it read every line beginning with those words. The README's own paragraph cites the command it replaced — *"used to be spelled out here as `pip install -e \".[core,genome,variant,cli,ml,dev]\"`, which could not succeed"* — and misses tripping the guard only because of where that paragraph happens to wrap. One reflow and the guard would fail on the explanation of why it exists, with deleting the explanation as the cheapest fix. A citation of a broken command is the opposite of an instruction to run it: the population is now the fenced code blocks, which is what a reader executes. Also from the same sweep: `cas9-rs3` — the stack behind the one fully-wired real model — is installed by no CI job, so nothing would notice if it stopped resolving. It resolves (22 wheels, no source build) and is CI-free for a stated reason (CI is weight-free; those tests carry the `real_weights` marker), so it is now recorded with that reason rather than left as a harmless accident. Guarded in both directions.
- **The README's install section told a contributor to run a command that cannot succeed.** `pip install -e ".[core,genome,variant,cli,ml,dev]"` — the first command in the install section — fails with `Error: pg_config executable not found`, for the reason the Docker image did: `variant` is `hgvs`, `hgvs` requires `psycopg2`, and psycopg2 publishes Windows wheels only. Three facts show nobody had run it: **no CI job installs `variant`** (every one uses `genome-light`), the project's own development virtualenv has neither `hgvs` nor `psycopg2`, and `CONTRIBUTING.md` had already argued against a hand-written line — *"`make install` … is the same extras set CI installs, kept in one place"* — while the README carried one anyway. The README now points at `make install` and shows the extras it expands to; the extras table keeps `variant` with what it additionally costs (PostgreSQL client headers), because a capability removed from the record is a different mistake from one recorded with its price. Guarded: every fenced `pip install` in the README, CONTRIBUTING and the docs is refused if it names an extra needing a system library, and the README's from-source line is tied to the Makefile target so "kept in one place" is checkable rather than asserted.
- **The Docker image could not have been built.** It runs `pip install ".[core,variant,cli,web,genome-light]"` on `python:3.12-slim`, and `variant` is `hgvs>=1.5`, which requires `psycopg2` unconditionally — and psycopg2 publishes **Windows wheels only** (2.9.12: six `win_amd64` wheels and an sdist). So on Linux pip builds it from source, which needs `libpq-dev` and a compiler, and slim has neither; the line fails with `ERROR: Failed to build 'psycopg2'`. Nothing would have caught it: the docker job lives in `release.yml`, which says of itself *"inert until v0.1.0 is tagged"*, so the first person to meet it would have been whoever cut the first release — in a multi-arch QEMU build. `variant` was buying the image nothing: `hgvs` is the projector for `c.`/`p.` HGVS input, which this project already records the web API as unable to reach (`_NOT_IN_WEB["hgvs"]`). Verified against a venv built from the corrected extras — `/api/resolve`, `/api/design` and `/api/offtarget` answer 200 for coordinates, bare contigs and genomic `g.`, and a `c.` request still returns the refusal naming the missing library. The alternative, `libpq-dev` in the builder, would carry a Postgres client into an image that never speaks to Postgres. Guarded by name so it fails offline and on the commit that reintroduces it, with a second test that the reason still holds.
- **The Cas-OFFinder cross-check's anchor coordinate was only ever checked against its own arithmetic.** Everything the adapter reports hangs on one shift: Cas-OFFinder gives the leftmost coordinate of the whole protospacer+PAM match, AlleleForge records the protospacer start, and on the minus strand the PAM sits at the low-coordinate end — get it wrong and *every* minus-strand site is flagged as a two-way disagreement by the tool whose purpose is flagging disagreements. It was tested with a site built in the test at `start=1000` and the assertion that 997 comes out, which checks `1000 - 3 == 997`; it never saw a site the engine produced, so a bulged alignment (21 or 19 bases rather than 20) was outside it entirely. The binary is not installable here and real parity is not faked — but the property parity depends on is checkable from the reference: at the reported coordinate the window must be `len(protospacer) + 3` long with the PAM at the 3' end *as read on that site's strand*. The engine's own output now feeds the check, including a 21-base minus-strand bulged site, with premise tests that both strands and more than one protospacer length appear. The adapter is correct; three mutations of the shift each fail the new test.
- **The "Check a spacer" panel rendered a result and offered no way to keep it.** The guard for exactly this — *"the one rendering the page could not give you was the one it was showing you"* — already records the defect happening twice, and was silent for the third, because its population is *formats the API serves under `?format=`* and `/api/offtarget` serves one shape and takes no format parameter. The right population for the question it asks, and the wrong one for the question underneath it: can a reader take away what the page just showed them? The panel now offers **Download JSON**, serializing the response it is already holding rather than re-asking the endpoint — there is no second rendering to request, and re-POSTing would re-run a search that on a real genome is minutes and need not return the same thing. The guard gains a section asking the second question off the *panels*: every `<section id="panel-…">` must record a download surface, that surface must exist, and every button in it must have a handler. Verified in a browser — hidden until a search succeeds, hidden again while the next runs, absent after a refusal, and a 3,588-byte `application/json` blob carrying all thirteen response fields including the disclaimer and both ancestry tables.
- **The phone-width guard about tables could not see two of the page's tables.** `test_every_table_scrolls_inside_its_own_box` enumerated its subjects from the *stylesheet* — every rule matching `table…` — so the off-target panel's summary and ancestry tables, which carry no CSS rule of their own, were invisible to it. Its population was "tables the stylesheet styles"; its subject is "tables that can outgrow the viewport". Measured first: at 375x812 the two are 335px and 298px against a 375px viewport and `document.scrollWidth` is 375, so **nothing was broken** — an element a guard cannot see simply is not protected by it. `#ot-results` now scrolls, and the rule is load-bearing rather than decorative: forcing a fourteen-column table into it in a browser leaves `document.scrollWidth` at **375 with `overflow-x: auto` and 2,043 without it**, because overflow propagates and the whole document pans rather than the table. The guard now reads its population from the markup — every element the page assigns table HTML to via `innerHTML` — with the reverse check that an entry whose element no longer renders a table is stale; the stylesheet-based check stays, since the two populations overlap without either containing the other.
- **`--cell-context hek293t` was out of distribution, and reordered the menu.** The check was an exact, case-sensitive membership test against `PRIDICT_TRAINING_CONTEXTS = {"HEK293T", "K562"}`, so a user who typed the cell line in lower case — or pasted it with a stray space — got every candidate flagged `ood`. That flag is not cosmetic, and the project says so in its own words: `CAVEAT_FLAGS["ood"]` reads *"the efficiency prediction is out of distribution for this model — it is ranked on its **lower interval bound**, and the point estimate should not be trusted"*. So the case of a cell line name silently changed both an honesty flag and the order of the menu, with the only signal a three-letter flag that names no cell context — and `hek293t` produced byte-identical output to `NOT_A_CELL_LINE`, making a typo indistinguishable from a genuine out-of-distribution request. The comparison now folds case and strips surrounding whitespace, against a set derived from the public one so a context added there cannot be left out of the check. `HEK 293T` stays out of distribution on purpose: internal spacing is a different string, and guessing which cell line was meant is worse than flagging it. Found by fuzzing every string-typed CLI input; it is the only one of the family that neither refuses an unknown value nor normalizes a known one.
- **`aforge offtarget '>chr1'` scanned a pasted FASTA header and gave it a specificity score.** `--pam NZZ` is refused by name — `PAM` validates its pattern against the IUPAC alphabet — while the *spacer* argument of the same command went to `search()` as a bare `str` and was never checked. A pasted FASTA header was scanned as a five-base spacer and reported `specificity 0.026` over a 5,072-placement sub-threshold tail, at exit 0, described as "ambiguous at position(s) 1, 3, 4, 5" — `>` and `1` are not ambiguity codes, they are not bases; `_sanitize` folds everything outside `ACGTN` to `N`. `POST /api/offtarget` accepted the same string, as did a digit typed for a base, a space from a wrapped paste, a trailing hyphen and RNA, all at `specificity 1.000` and exit 0. Fixed in `_spacer_str`, the one function `search()` puts every caller through, rather than in the two shells — a check at a shell is one the next caller walks past — so the CLI now gives a usage error and the API a 422 carrying the same sentence, which names the offending characters and the three things that usually produce them. The IUPAC ambiguity codes stay accepted: they are what the "ambiguous at position(s)" disclosure exists for. Found by installing the package the documented way and typing a bad spacer.
- **The acceptance suite — the SPEC §16 definition of done — checked that the safety numbers existed, not that they meant anything.** Replacing `specificity_score()` with a constant `1.0` (every guide perfectly specific, the most consequential number the tool prints) left the whole acceptance suite green, as did zeroing `worst_score()`, `expected_burden()` and `ancestry_expected_burden()`; only an emptied `ancestry_stratification()` was caught. The assertions asked whether an axis was *populated*, and a constant populates it. Sharper still: on the reference-bias scenario the frequency-blind `ancestry_stratification()` reads **afr 1.000 / amr 1.000 / nfe 1.000** — a CFD score is a property of the sequence, not of who carries it — while `ancestry_expected_burden()` reads **afr 0.105 / amr 0.012 / nfe 0.001**. The test named `test_reference_bias_case_reproduced` asserted the first was non-empty. An earlier round added the second precisely because the first cannot express the finding, and the acceptance test was never updated. It now asserts values: specificity below 1.0 once a site is nominated, a positive worst score, the frequency-weighted burden strictly between zero and it, `afr > amr > nfe` with afr more than 100x nfe — and, out loud, that the frequency-blind figures are all equal, so a future reader is told to revisit the reasoning if that stops being true. All five mutations now fail.
- **Fourteen tests named `test_every_candidate_…` passed on a menu with no candidates.** Their whole body was `for c in <candidates>: assert …`, and an empty list runs the loop zero times and exits green — so each asserted the per-candidate contract only while something else happened to produce candidates. Not hypothetical: this project has shipped an empty menu (a large precise edit produced none until the nuclease+HDR route was added). Mutating all three design verticals to `return []` **broke 149 tests and left all fourteen of these green**, including the one called `test_completeness_property`. Each now binds the collection and asserts it is non-empty before looping, and all fourteen fail under that mutation. The grep that found them is now a guard, deliberately narrow — it looks only at loops over a computed candidate collection, since a loop over a fixed registry is exhaustive by construction — and its reader is checked in both directions so it cannot silently stop matching.
- **The reproducibility contract pinned a menu with nothing to rank and no off-target site.** `scripts/reproduce.py` is the R0 honesty contract — "reproducible from config + seed" — and says it keeps everything defining the result, "candidates, scores, intervals, outcomes, **off-targets**". Its canonical scenario was a 20-nt protospacer between two 20-nt poly-T pads: 63 bases, producing **one candidate, of one chemistry, over an off-target search that found nothing**. One candidate exercises no ranking, no Pareto front and no cross-chemistry caveat; an empty site table leaves every site-level number in a real report outside the contract. Not theoretical: two consecutive rounds changed the off-target scan and cited "reproduce matches golden" as evidence. Making the PAM scanner consume its match instead of looking ahead — which silently drops every overlapping anchor and reports a guide as safer than it is — **leaves the old scenario exiting 0 and the new one exiting 1**. The scenario now carries flanks that make prime editing eligible and a two-mismatch decoy of the protospacer with its own PAM, so the canonical menu ranks four candidates across two chemistries with five nominated off-target sites, a three-member Pareto front, and the cross-chemistry and unresolved-tie disclosures that no golden had ever covered. A new guard pins that coverage as a property, so a future `--update` cannot quietly shrink it back.
- **Eleven call sites built two validated models to reverse-complement a string.** `str(DNASequence(x).reverse_complement())` appeared eleven times across the enumerators, the genome index and the off-target scan: construct a frozen pydantic model, validate the alphabet, translate, construct a *second* model, validate the alphabet *again*, and throw both away to return the string it started from. The second validation was always redundant — `_COMPLEMENT` maps the IUPAC alphabet onto itself, which `test_every_validated_base_has_a_complement` already pinned — while the first is not, and dropping it is the trap documented beside `_COMPLEMENT_TABLE`: `str.translate` passes an unmapped character through unchanged where the model raises. There is now one `reverse_complement(str) -> str` that validates once and translates once, and the validation itself moved from a set difference to the same `translate` substitution `_sanitize` uses. **Per `design()` on a 20 kb reference, exactly: `DNASequence.__init__` 3,004 → 778, pydantic validations 4,989 → 2,763, Python calls 172,721 → 163,482.** Interleaved minimum over fifteen alternating runs: a 20 nt reverse complement 4.46 µs → 0.42 µs, a 2 Mb one 15.05 ms → 10.20 ms — the 2 Mb case being the off-target scan's whole-contig complement, which runs twice per `scan_sequence`. Call counts rather than wall clock because the machine was loaded; the ratios are exact and the timings would not have been.
- **The off-target scan ran a prefilter that cost more than the work it skipped.** `scripts/native_speedup.py` printed the pair — `high-stringency (mismatches=1): brute force 29.89ms, seeded 68.16ms (0.4x)` — and `scan_sequence` seeded anyway, the same shape as the FM-index auto-engage removed earlier: the number was in the script's output and the decision was in the prose. The prefilter's saving is the anchors it skips and its cost is its own `O(n)` pass; every round that measured it found the saving smaller (~2–4x when calibrated, then 0.94–1.12x), and the last of it went when the PAM test became one compiled regex scan, because the prefilter then pruned only a native `evaluate_anchor` call. **1 Mb, one guide, no bulges, three runs each, brute force / seeded in ms: crate built 48/139, 45/156, 39/167, 58/157; not built 60/226, 80/212, 69/292, 81/282 (mm = 0,1,2,3). `aforge offtarget` over 20 Mb at `--mismatches 1 --dna-bulges 0 --rna-bulges 0`: 5.89 / 6.50 / 5.90 s before, 3.42 / 3.18 / 2.83 s after, byte-identical JSON.** The one repair the previous comment left open — "attacking the prefix-sum construction" — was measured too: a `bisect` over the seed positions, with no `O(n)` pass at all, is still 0.79–1.65x (crate built) and 1.82–2.66x (not built). So the prefilter is opt-in rather than deleted: it is a *proven superset* by pigeonhole, and that exactness is why it stays reachable as `scan_sequence(seed=True)` and stays parity-tested. `SPEC_V2.md`'s ordering rule ("the seed must run *before* the PAM check to prune") is recorded as expired rather than quietly dropped — it described a per-anchor Python PAM test that no longer exists.
- **The off-target scan asked "is this a PAM?" four million times in Python, once per position per strand.** At the default budget the k-mer prefilter does not apply — `seed_length(20, 4 + 1 + 1)` falls below `MIN_SELECTIVE_K`, so `_seed_filter` returns `None` — and every anchor then paid for a three-character slice and a dict lookup before a single alignment was evaluated. "Does this window match an IUPAC pattern" is a regular question, so it is now one compiled lookahead scan the regex engine runs in C. **2 Mb scan (alternating, three runs each): 0.36 / 0.51 / 0.56 s before, 0.15 / 0.23 / 0.21 s after. `aforge offtarget` over 20 Mb: 6.70 / 5.65 / 5.37 s before, 2.84–3.64 s after, with byte-identical JSON.** The translation is exact in two places that would not have raised if they were wrong, and both are pinned: every pattern code becomes a character class of concrete bases (no `IUPAC_EXPAND` value contains `N`, which is what makes the old `"N" not in pam_seq` test unnecessary rather than forgotten), and the scan is a **lookahead**, because PAM windows overlap — `AGGG` holds an `NGG` match at 0 and another at 1, and a consuming match would silently drop the second and report a guide as safer than it is. The old per-anchor loop is kept verbatim in the test file as the oracle for a differential run over ten PAM patterns, five budgets and N-containing sequences.
- **`aforge verify` accepted a provenance block that named a model for the wrong chemistry.** The cross-check that catches an *emptied* `models` list only caught that. A checkpoint is tagged with the chemistry it scored and every candidate states its own, so deleting the two prime cards from a prime-only menu and leaving the unrelated base-editor one behind reported `1 model(s)` and `verified: provenance is complete and consistent` — a populated-looking block naming nothing against a single number in the file. `verify` now requires a model for each chemistry the menu ranks. It reads the grouping off the producer (`designer.model_chemistry_group`) rather than comparing the two labels, because the base vertical is one call covering ABE and CBE and stamps a single card tagged `base_abe`: real runs rank `base_cbe` candidates against exactly that card — sixteen in a 159-run sweep, none of which the new check refuses — and a checker that compared labels directly would reject genuine output. A test pins the correspondence, so retagging a vertical fails loudly instead of turning the check into a source of false refusals.
- **`aforge verify`'s tamper contract was defeated by deleting a row, not editing bytes.** The command's help says it "confirms the block names every model *and dataset* the result used". The model half is cross-checked against the result; the dataset half was taken on trust — so deleting the `doench-2016-cfd` row from `provenance.datasets` still reported `verified: provenance is complete and consistent` and exited zero, on a result whose every candidate names that matrix in `offtarget_matrix` as the thing that scored its off-target table. Worse under `--cache-dir`: the CFD matrix is the *only* artifact this project actually re-hashes (the three baseline models are unpinned), so deleting the row emptied the byte check too — it truthfully noted that nothing had been established and still exited zero. `verify` now reads the producer's own rule back off the result: a scoring matrix a candidate names, that the dataset registry knows, must appear in `datasets`. Matching on registry membership is what keeps the negative case working — a table that fell back even once is labeled `"published + approximation"`, and the length-relative approximation is code with no bytes to pin, which is why `_collect_datasets` deliberately does not record it. Both artifact shapes are covered, duck-typed as the model check already is.
- **A design spent 78% of its time re-parsing the same seventeen YAML files.** The comment above `default_registry` said the registry was "populated from the bundled cards on first use"; it was populated on *every* use. One `design()` calls it six times — through the efficiency, outcome and prime scorers, and again when the run collects its model checkpoints for provenance — so a single design read and parsed 102 model cards that ship inside the package and cannot change while the process runs. A profile put 0.651s of a 0.836s design inside `yaml.safe_load`. The cards are parsed once per process now. On a 300-variant cohort, same command and inputs, three runs each: **21.28 / 21.96 / 20.67 s of user CPU before, 6.91 / 6.81 / 7.10 s after**, with byte-identical output; a single design goes from ~279 ms to ~32 ms. `ModelCard` is frozen so the parsed cards are shared, and `default_registry()` still returns a *new* `ModelRegistry` around them — a caller that registers a card into the object it was handed cannot affect the next caller, which was previously an accident of the waste. `from_cards_dir(dir)` with an explicit directory stays uncached: it is the path a caller takes because their cards differ.
- **`pip install "alleleforge[cli]"` produced an `aforge` that could not print its own `--version`.** The documented CLI install does not include `pyfaidx` — the deployment guide lists genome access as a separate row to *add* — and `genome/reference.py` imported it at module scope. `cli.main` imports `design`, which reaches that module, so every command died with `ModuleNotFoundError: No module named 'pyfaidx'` before the argument parser saw the line: `--help`, `data list`, `bench list`, `resolve`, all of which touch no sequence. The package had met this once already and answered it at the package boundary — `genome/__init__` defers its `reference` re-exports, and its comment records `aforge bench run` failing exactly this way — but ten modules import the submodule *directly*, walking past the deferral, and each new one would have to remember. The dependency itself is now deferred to the moment a reference is opened, which no future caller can undo, and opening one without the extra names the install that provides it instead of raising a `ModuleNotFoundError` three frames down. Found by doing what the install table says and running the result.
- **The safe way to run the service was documented at a path that did not exist.** `docs/deployment.md` names `alleleforge.web.api.serve()` and explains that it *refuses* a non-loopback bind without an API token — the reason to prefer it over running `uvicorn` against the module-level `app`, which binds the socket itself and cannot consult that guard. `serve` lives in `alleleforge.web.api.app`, and the package exported only `create_app`, so a reader who followed the advice got an `AttributeError` and fell back to the unguarded line: the exact outcome the sentence exists to prevent. The function is re-exported at the path the guide names. Four documentation guards already read the docs — commands, flags, local links, and the symbols a ```python fence imports — and all four read a particular syntax; a dotted path in a *sentence* was visible to none of them. Every `alleleforge…` path the prose names outside a code fence is now resolved.
- **A token-protected deployment served a page that could not do anything.** `ALLELEFORGE_API_TOKEN` gates every `/api/*` call except health — which is right, and is what `docker-compose.yml` tells an operator to set before publishing the port beyond the host. The served page is not exempt and could not guess: it loaded, read health, listed the deployment's capabilities, and answered every action with `401 missing or invalid API token`. Accurate, and nothing a person in a browser can act on, because a browser cannot add a header by itself — so the one audience with no terminal to fall back to was the one locked out. `GET /api/health` now reports `auth_required` (never the token), the page reveals a field when it is set, and every call goes through one `apiFetch` wrapper so a call added later cannot skip the header. The token is held in `sessionStorage` — the browser tab, not the browser profile — because it is the operator's secret.
- **The HTTP shell was the surface still leaking pydantic's report.** `errors.reason` was introduced for exactly this and applied to the CLI, the cohort's per-item error column, the designer's skip note and the job queue; `web/api/app.py` — the one place a *client* reads the text — was not on the list. So `POST /api/offtarget` with `pam: "XYZ"` still answered with `"detail": "1 validation error for PAM / pattern / Value error, PAM has non-IUPAC characters: ['X', 'Z'] [type=value_error, input_value='XYZ', input_type=str] / For further information visit https://errors.pydantic.dev/..."` — an internal model name, a field, a framework's taxonomy and a link to a library the client never imported, wrapped around the one sentence it can show a user. Every refusal the handlers raise now renders as the sentence, including the startup `source_errors` a deployment reads from `/api/health`. FastAPI's own request-schema 422 keeps its structured body: that is a documented contract a generated client parses, not a leak. The guard that was supposed to prevent this listed four files and now also refuses `str(exc)`, not only `{exc}` — a list of surfaces is a scope, and a scope is a place to forget one.
- **The served page held one connection open for the whole cohort.** `runBatch()` was a single `fetch("/api/batch")`, and a browser — or any proxy in front of the server — closes an idle request long before a three-hundred-variant run finishes, so the cohort panel failed on exactly the cohorts it exists for, with a `TypeError` from `fetch` that says nothing about what happened. The page now submits to `/api/jobs/batch` and polls: the connection is never held, the status line carries the job's state instead of showing `Designing N variant(s)…` for minutes, and the poll has a deadline so a page whose server restarted (which drops in-flight job records, as the job manager documents) stops rather than saying "running" until the tab is closed.
- `POST /api/batch`'s OpenAPI description advertised `Parquet`, which it refuses with a 422. The description is what a client reads before writing the request; it now says JSON or TSV, which is what the endpoint and `docs/api/web.md` have always meant.
- **Parquet export crashed on an ordinary design.** `aforge design --format parquet` and `POST /api/design?format=parquet` — both documented as handing a pipeline the same table the TSV holds — died with a polars `ComputeError` on a 341-candidate menu. polars infers each dtype from the first 100 rows, and `bystander_burden` is null for every prime candidate and a float on the one base editor, which ranks last: the column was typed Null and then handed a float. The v14 change that gave bystander burden the interval its neighbours already had is what made the column mixed; the tests exercise reports smaller than the inference window, so nothing saw it. Inference was wrong even when it worked — a run with no population data leaves `worst_ancestry` null throughout and gave it a Null dtype, while the same tool with a gnomAD file writes a string column, two files no pipeline can union — and the empty frame was built from a separate expression, so a report with no candidates wrote every column as Null. `TSV_COLUMN_TYPES` now declares the types once, for the populated frame and the empty one, and is checked against real rows. `offtarget_expected_burden` also stopped carrying `""` as its absent value: the TSV renders `None` as the same empty cell, and a string sentinel cannot sit in a typed column beside the numbers it also holds.
- **A stale FASTA index was read through, and the wrong answer it gave was an unpadded empty sequence.** The `.fai` is not re-derived on open (`rebuild=False`, so a read-only reference mount works), so replacing or truncating the reference after indexing — writing a different assembly to the same path is the ordinary way — left pyfaidx warning about mtimes and then reading the old offsets. A `RuntimeWarning` reaches nobody in a library call, an HTTP deployment or the served page. Against a FASTA holding only `chr1`, with a two-contig index: `contigs` listed `chr2`, `contig_length('chr2')` returned 40, and fetching `chr2:0-20` returned the empty string with `padded=False` — "I read those twenty bases, and they are nothing" — which then flows into design and off-target scoring as measured data. Opening a reference now compares the FASTA's size against the offsets the index itself asserts and refuses when the file is smaller, naming `samtools faidx`. One `stat`, no false positives: a file shorter than the bytes its index requires cannot be the file it describes, whatever the mtimes say. A *longer* file is left alone — an appended contig does not move the ones already indexed.
- **A refusal was a dependency's error report, everywhere it could be one.** `pydantic.ValidationError` subclasses `ValueError`, so every boundary that catches `ValueError` and prints `str(exc)` printed pydantic's whole document: `aforge offtarget --pam XYZ` answered with `1 validation error for PAM / pattern / Value error, PAM has non-IUPAC characters: ['X', 'Z'] [type=value_error, input_value='XYZ', input_type=str] / For further information visit https://errors.pydantic.dev/...` — the sentence a person needs on the third line, under an internal model name, a field, a framework's taxonomy, and a link to a library they never imported. One call site had been patched by hand for one model, with a comment explaining why; the class stayed. `errors.reason(exc)` renders the sentence and leaves every other exception exactly as it was, and all four reporting surfaces go through it: the CLI's twenty error sites, the cohort's per-item `error` column, the designer's per-vertical skip note, and the job queue's `error` field.
- **`chr11:0:T>C` answered with a pydantic traceback quoting a number the caller never typed.** `chrom:pos:ref>alt` is read as a 1-based VCF record and stored 0-based, so a position of `0` reached the model as `-1` and the field validator replied `1 validation error for Variant / pos / Value error, pos -1 is negative [type=value_error, input_value=-1, input_type=int] / For further information visit https://errors.pydantic.dev/...` — an internal model name, a framework's formatting, a link to a library the caller never imported, and a coordinate they never wrote, sitting beside a dozen sibling refusals that are one curated sentence. `0` is also the specific mistake worth catching: it is what pasting a printed 0-based position for a contig's first base produces, and the refusal now says so. Both 1-based entry points route through it — the coordinate string and a VCF record — and a negative position is now refused as a position rather than as unparseable input. The model validator stays as the backstop for a caller who builds a `Variant` directly.
- **A position past the end of a chromosome was reported as a build mismatch.** `fetch_result` pads an over-run with `N` so a window near a telomere still comes back full length, and `_validate_ref` folded that padding into the mismatch branch — so `chr11:9999:A>T` against a 4,000-base contig printed `asserted ref 'A' but reference has 'N' (wrong build?)`. The reference does not have `N` there; it has nothing there, and the `N` is this tool's own invention. The message sent the reader to liftover for a variant no assembly conversion can rescue: the actual fault is a truncated or chromosome-only FASTA, or a coordinate in the wrong convention. The refusal now names the contig's length and the valid position range, and says what to check. The off-target engine already had this right from the other input — a region past a contig end reports how much of it was searchable and names "past a contig end" among the reasons; the resolver was the outlier.
- **"Why the other chemistries declined" did not say why.** Under that heading the menu rationale printed the routing rule's biological rationale — a description of what the chemistry is for, byte-identical on every run of the tool. Correcting `chr11:1999:T>A`, a reader was told that adenine base editing is "the cleanest fix when the required change is an A:T->G:C transition SNV": true, general, and leaving them to work out for themselves that their required change is A->T. The reader who most needs that line is the one who wanted a base editor and is now looking at a prime candidate. Each routing rule now also explains its refusal in terms of the variant in front of it — the change no editor installs, the variant class outside a chemistry's repertoire, the size against the RTT budget it exceeded, the break-free routes that made a double-strand break unnecessary — and that leads the line, with the policy sentence still behind it, because the two answer different questions.
- **The CLI reference's command table, and the guard behind it, could not see a subcommand.** Both checks enumerated top-level commands only, so `aforge bench compare` and `aforge data show` were absent from the table on the page a reader opens to learn what the tool does — while the guard whose whole subject is undocumented commands passed, because `bench` itself was listed. This is the same correction the table needed a round ago, one level down: the claim was written at a level the check did not visit. Both guards now walk the full command tree, and every subcommand has its own row.
- **`--help` described a release the reader never used.** `aforge lift` spent a paragraph explaining that the liftover "was implemented and tested but reachable only from Python" — a fact about a version nobody can install, and no help at all in deciding whether to run the command. `aforge bench compare` opened by saying the reproducibility digest "had no implementation: computed, stored, and read by nothing," which reads, to someone deciding whether to trust the comparison, as a description of the command in front of them. Both now say what they do. The motivation belongs in this file, where it already is. Separately, `--allow-ng`'s help rendered as `assumed.Consumed` — two adjacent string literals concatenated without the space between them, invisible in the source and shown to every user who asked. Both classes are now checked across every command and option the CLI exposes.
- **CONTRIBUTING's second command failed for every contributor who tried it.** It said "a conda environment is also provided" and gave `conda env create -f environment.yml`; there has never been an `environment.yml`. The repository ships `conda/meta.yaml`, a bioconda packaging recipe — how to publish the released package, not how to set up a checkout. The local-link guard could not see it, because the name is an argument inside a fenced command rather than a Markdown link; every config file a documented command names is now checked to exist, with an allowance for the one a reader is meant to write themselves. The setup step also said `pip install -e ".[dev]"`, which leaves out the FASTA reader and the web server, so the gate it tells you to run next could not pass; it points at `make install`, the extras set CI uses.
- **`ALLELEFORGE_REFERENCE` did nothing on the command line either** — the same mechanism as the seed, on the option that sets the build label stamped into provenance and decides which assembly a locus is reported against. `--reference` carried `hg38` as its default and that default reached every consumer directly, so the variable the library honours and the deployment guide lists changed nothing on any run. It now resolves flag, then environment and config, then the default; an explicit `--reference` still wins.
- **`ALLELEFORGE_SEED` did nothing on the command line.** The `--seed` option carried the default seed as its *default value*, and that default was handed to `Settings.load` as an override — and overrides outrank the environment, correctly, for a value the caller actually typed. A flag's default is not something the caller typed. So the variable listed in the deployment guide changed nothing on any `aforge design` or `aforge batch` run, every result stamped 20240501 into its provenance whatever the operator set, and the library honoured the variable all along. The documented precedence (defaults < config file < environment < explicit override) now holds on the CLI too, and `--seed` still wins when given.
- **A malformed setting arrived as a pydantic traceback naming a field nobody set.** `Settings` derives its variable names from `env_prefix`, so an operator sets `ALLELEFORGE_SEED` and the error reported `seed` — the one string a reader could search for, and the one string the message omitted. It matters most where it lands: the web app builds itself at module scope, so a mistyped variable is a container that will not start and this message is the entire diagnosis in the log. It now names the variable, the value and the reason, points at the settings table, and on the CLI exits 2 rather than 1, the code reserved for a defect in the tool itself. Still fatal by design: a seed or an interval level has no honest degraded mode, and substituting the default would stamp every result with a number the operator did not choose.
- **A typo in `ALLELEFORGE_TRAINED_MODELS` stopped the container from starting.** The setting was added earlier in this same release and validated by raising — from `create_app()`, which runs at module scope, so `uvicorn alleleforge.web.api.app:app` (the command in the deployment guide and the Dockerfile) exited with a traceback and the service never came up. That is the defect the reference loader thirty lines above it carries a paragraph about. A misspelling still must not leave a deployment silently baseline-only, so it is loud where every other misconfigured source already reports itself — `GET /api/health` under `source_errors`, plus a 422 by name on any request for a model it should have enabled. A bad value passed to `create_app(trained_models=…)` still raises: that is a programmer's mistake, not a deployment's.
- **The README told contributors to run a gate that is not the gate.** Its development section spelled out the tools by hand — `ruff` over three paths where CI runs four, the exact divergence `test_gate_mirrors_ci.py` was written about, on a third surface that test did not read — and told readers to `maturin develop`, which installs a build of the working tree into whichever virtualenv is active rather than the wheel CI installs. It points at `make ci` and `make native` now, and a check keeps it pointing rather than respelling. Two further `maturin develop` instructions, in CONTRIBUTING and the deployment guide, were found by the new check on its first run.
- **The served page panned sideways on a phone once the cohort table grew columns.** Measured at 375x812: `document.scrollWidth` 998 against a 375px viewport. Twelve columns of content that does not shrink (~980px) sat inside ancestors that all defaulted to `overflow-x: visible`, and overflow propagates — so the whole document moved, not just the table. It scrolls inside its own box now; the document measures 375 again. The existing guard was written for a non-wrapping flex row and its docstring asserted "the page has no other horizontal overflow at that width" — true when written, false once a table outgrew the viewport for a different reason. The rule it enforces is the general one now: an element that can outgrow the viewport must contain its own overflow, whether by wrapping or by scrolling.
- The "every artifact says what it is" check now derives its population from the code. The rule was enforced over a hand-written list, and that file's own docstring records what it cost: a fifth artifact (`aforge batch --json`, the document a lab passes around after a cohort run) was simply not on it, because "an enumeration is only as complete as whoever last extended it". Every function in `src/` that writes a file is now found by walking the AST, and each must say which artifact it produces and whether the rule reaches it — so a new writer fails until someone decides, instead of being invisible until someone notices.
- Half of `search()`'s numeric defaults had no documentation guard. The CFD and MIT thresholds and the mismatch budget were pinned across every document that quotes them; the DNA and RNA bulge budgets and the MAF floor — restated the same way in five documents, as the tool's operating envelope — were not. The check now *enumerates* the defaults rather than listing the ones somebody remembered, so a new default cannot be forgotten: each is either given the prose form it is written in, or recorded as one no document quotes.
- The benchmark's task table — name, kind, and the primary metric a model is *ranked on* — is written by hand in the README, the API reference and the preprint, and was compared to `alleleforge.benchmark.tasks` in none of them. All three agree today; the check keeps them there. A stale `Spearman` where the harness ranks on `KL` is not a documentation nit but a false statement about how models are compared, in the document written to be cited.
- The preprint's split-conformal recalibration table — a hand-copied set of computed numbers in the most citable artifact in the repository — is now compared against `calibration_study.conformal_demo()`, along with the sentence above it that the table exists to support. Correct today; the check is preventive, and mutation-verified accordingly, because a table that drifts is a nuisance while a table that stops supporting its own claim is a false scientific one.
- **The readiness assessment's verification numbers were stale, and its header said they were not.** The file exists so context is not lost across sessions and claims its numbers are "re-measured, not remembered"; it said 2,871 tests and 17 native parity tests when the real figures were 2,975 and 71. An earlier round re-measured them by hand and concluded the fix was to *derive* the claims rather than re-type them — then guarded the reachability table in the same document and left the numbers beside it unchecked. The current section now states only numbers a test derives from the repository (source files, notebooks, the coverage gate), and an absolute suite-wide test count is forbidden outright: it is wrong by the next commit, and "the suite passes" is the claim that matters. The dated sections below are untouched — freezing history is what they are for.
- **No CI job ran the full suite with the compiled crate installed.** The `rust` job built the wheel and then ran `pytest -m native`, so the shipped configuration — the one the docs recommend for real work, where the library takes its native branches everywhere — was exercised only where someone had remembered to add a marker, while every other job ran pure Python. That gap has bitten before: with the crate built, `FMIndex.build` dispatched to the extension and silently dropped `cache_dir`, `rebuild`, `occ_rate` and `sa_rate`, which no `native`-marked test covered. The job and `make native` now run the whole suite (it passes today: 2,973 tests with the extension loaded). The `rust` job is excused from `make ci` on the grounds that `make native` covers it — a claim about commands that nothing compared, on the one job the mirror test lets out of its main check; it is compared now.
- **The leaderboard grouped by a split *label* and never looked at the split's hash.** A comparison group is `(metric, split_version, synthetic)`, and `split_version` is a string a submitter writes — so two admissible, correctly signed submissions from different labs, both saying `v1` and scored on different bytes, were ranked against each other while the module's own docstring promises that ranks never cross a comparison group. `split_sha256` is on every result, precisely so a verifier can tell, and nothing consulted it. A group whose rows disagree now says so on both renders, and names the consequence: the order is unmeasured until the submitters agree on the split. Grouping still keys on the label, deliberately — re-partitioning silently by hash would produce two identically-captioned tables and hide the problem rather than show it.
- **`bystander_burden` was the one calibrated prediction in the flat table carrying no interval** — the fourth instance of this gap, and exactly the place the third one predicted: `efficiency` above it and `p_intended` below it both carry a value, an interval and two honesty flags, and the column between them carried a point estimate. It now carries the same four, `schema_version` is `14`, and a check accounts for every `CandidateReport` field: carried under its own name, recorded as flattened into named columns, or excused with a reason. It caught my own incomplete map on its first run (`calibrated`, efficiency's fourth flag).
- **The cohort TSV dropped `chemistries` in silence**, the same hand-written-renderer gap one layer below the browser table. `cohort_to_tsv` keeps an explicit column list, so a key added to the row and not to it never reaches the file — and a Python caller could see that a variant had three chemistries available while the artifact the run is read through showed only the recommended one. "Prime only" and "prime, base_abe and cas9_nuclease" send a reader to different next steps. The column is there now, and both directions are checked: every row key has a column, and no column outlives the key that fills it.
- **The browser's cohort table kept losing columns the other shells gained**, and a check now stops it. Twice in three rounds a fact was added to the cohort row, reached the CLI's TSV and `/api/batch`, and never reached the page — the audience with no terminal to fall back to, and the one whose table is hand-written rather than generated from the row. The resolved `variant` and the ClinVar classification are both columns now, and every key the row carries must be rendered or excused with a reason.
- **`best_bystander_burden` was a bare estimate beside an efficiency that carries its interval** — found by that check on its first run, and the third instance of the same gap. It is a calibrated `Prediction` like efficiency, and the cohort row kept the point estimate and dropped the envelope, so one column of a triage table followed the never-a-bare-float rule and its neighbour did not. The interval now travels with it on every surface, and the page shows the column at all for the first time.
- **Six documented command lines could not be pasted into a shell.** The variant syntax contains `>`, which every POSIX shell reads as output redirection, so `aforge design chr2:71:A>C --reference-fasta hg38.fa` creates a file named `C` and hands the tool `chr2:71:A` — the flagship example of the flagship command, unrunnable in the README, the CLI reference and the deployment guide. The existing guards asked whether an example names real flags and an input form the shell can *resolve*; both were true, and nobody asked whether the shell delivers the argument at all. Every documented command now quotes it, a check keeps them that way, and the refusal names the cause when the input has exactly the shape a shell leaves behind (`chrom:pos:ref` with no `>alt`) — and stays quiet for any other malformed input.
- **An accession or rsID the supplied release does not contain was a raw traceback**, on every shell — the likeliest thing to go wrong once `--clinvar`/`--dbsnp` exist. `ClinVarDB.get` and `DbSnpDB.locus` raise `KeyError` while their siblings in the resolver raise `ValueError`, so the shells' handling did not apply: the unguarded member of a family picked out by its exception *type*, not its logic. The refusal now names the record, the release's pin, and how many records it holds — `0 record(s)` says the file is the problem rather than the accession, which a header-only VCF from a truncated download reveals in no other way.
- The cohort resume check compares the reference *file*, not only its shape, closing the same gap one layer up: `_reference_snapshot` pins contig names and lengths by design (it is a shareable descriptor, so it can carry no local path and cannot hash a genome), which means two FASTAs of one shape share it. The resume decision is local to one machine, so it compares an opaque digest of the file's identity too, and the refusal names the innocent cause — a genome moved or re-copied reads as a different file even when its bytes are identical.
- **A warm off-target cache reported a guide as spotless in a genome it cuts.** The cache key identified a reference by build name and contig lengths — a *shape*, not an identity, since the build is a label the caller supplies and a soft-masked, patched or locally edited FASTA shares the shape of the one it came from. Measured with two references of one shape, the second carrying a perfect match for the guide: alone it reports 2 sites, worst 1.000, specificity 0.333; with the first genome's scan in the cache it reports 0 sites, specificity 1.000 — the most reassuring output the system can produce, from the wrong genome, on an opt-in flag whose whole promise is that it changes no result. The key now carries the FASTA's identity on this machine as well. Two byte-identical copies at different paths stop sharing entries, which costs a rescan; a safety cache has to fail in that direction. (The FM-index sibling was already keyed on a true content hash, which is what made this one the outlier.)
- **A cohort resume reused results computed under different inputs.** Resume is keyed on `item_id`, which identifies the *request*; re-running the same accessions against a second ClinVar release — one that places an item at a different locus — reported every item as "already done", exited 0, and wrote a summary with no rows, leaving an artifact designed against the release the user did not name with nothing in it saying so. The manifest header has recorded what the first run was since it was introduced, and nothing read it back. It is now compared, and a mismatch on version, seed, reference build or shape, intent, or the data sources handed to the run is refused with both remedies named (`--no-resume`, or a new manifest). The header also records those data sources up front, since a resume decision needs them before any item runs. A manifest with no header stays resumable.
- `aforge batch` reports `design_many`'s refusals — a mismatched resume, and a parallel run with no reference factory — as usage errors naming the remedy, instead of a traceback.
- **Three allowance entries excused capabilities the shells already offered.** The strong-form check — an excuse for something a surface now provides is a false record — existed for `design()` and had never been mirrored onto `search()` or `build_report()`. In the meantime `_SEARCH_NOT_IN_WEB` told a reader the off-target `scorer` was "not yet exposed; the CLI's `--scorer` has no web counterpart" while `OffTargetRequest` carried the field, and `_SEARCH_NOT_IN_CLI` said the CLI "has no session to hold" a cross-run cache two rounds after `aforge offtarget --cache` shipped. A weaker sibling check is worse than none: the list reads as maintained, and set subtraction can never see an entry that is both excused and offered.
- The reachability checks now bind the CLI's calls the way Python binds them, from the AST. Matching `name=` counted only keyword arguments, so `search(spacer, PAM(...), ...)` looked as though the CLI supplied neither — and both then sat in an allowance list with a reason invented for a gap that was never there.
- `specs/readiness-assessment.md` told a deployer to set `ALLELEFORGE_GNOMAD`; the variable is `ALLELEFORGE_GNOMAD_TSV`, so following it leaves a silently reference-only deployment. The env-var guard read README, SPEC and `docs/` — every surface except the two directories whose stated job is describing the software as it is now. It now reads `specs/`, `openspec/specs/` and `CONTRIBUTING.md`, and the reverse direction immediately found `ALLELEFORGE_LIVE_INTEGRATION` — how a contributor runs the live-service tests — documented nowhere. Both opt-in test markers are now a table in CONTRIBUTING.
- The readiness report says its criteria are narrower than the roadmap phases they are named after, and the README says the same from its side. `[MET ] R2` beside a README row reading "R2 … in progress" is not a contradiction, and nothing said so.
- The cohort summary TSV states the run's counts, so a resumed run's empty table says it is empty because everything was already designed rather than reading as a cohort that produced nothing.
- A parallel cohort reports its items in input order. `--max-workers 4` recorded them as they finished, so three consecutive runs of one cohort produced three different row orders and the summary table could not be diffed — a performance flag changing the artifact. The manifest stays completion-ordered; it is a progress log.
- A variant naming a contig the reference does not have is refused with a message naming it and listing what the reference has, instead of a traceback ending in `KeyError: "unknown contig 'chrZ'"`. Fixed in the resolver, so the CLI, the HTTP API and a Python caller all get it.
- The release checklist no longer promises that `twine check` already passes. It errors on a current toolchain (`'2.5' is not a valid metadata version`), which is the packaging tools disagreeing with each other rather than a bad distribution — but a checklist that says a step passes is how that becomes a surprise mid-release. The wheel itself was verified from its own contents.
- The release-readiness report no longer calls a stale native build "importable". It counted a parity module as evidence while every test in it skipped, which is the self-flattery the criterion's own comments record having fixed twice before.
- `make lint` passes again: `ruff format --check` had been failing on a trailing newline in one notebook cell, so the CI lint job was red.
- The served page's JavaScript is parsed. Seven tests read `app.js` as text and nothing had ever run it through a parser, so a missing brace would ship a dead form with every gate green; the suite now runs `node --check` and CI runs it explicitly.
- The suite checks that the committed docs figures are what `scripts/figures.py` produces. They are committed, that script is the only thing that writes them, and it ran in neither `make ci` nor CI — so a change behind a figure left the docs showing the old one with every gate green.
- The reproducibility golden is current again, and the test suite checks it. It had drifted three legitimate changes behind — a new field, a dataset reaching provenance, a reworded rationale — and because `scripts/reproduce.py` runs only as its own CI job, every local signal stayed green.
- A stale native extension is now reported instead of silently disabling the parity suite. The version handshake could not see it — the crate version is single-sourced and unchanged between builds — so an extension built before the off-target evaluation kernel existed reported the same version as one built after it, and the seventeen tests that prove native/Python parity skipped themselves saying the crate was not built.
- The rendered PDF carries a `/Title` and `/Producer`, so a forty-five-page report no longer opens untitled and is no longer filed by a reference manager as an untitled document. No creation date, so the same report still renders to the same bytes.
- The model zoo's lighter consent gate consults `artifact_download_permitted` like the other three, so an environment that opted in with `allow_network` is no longer permitted for a pinned-artifact model and refused for a loader-driven one. All four refusals now name both remedies — `consent=True` and `ALLELEFORGE_ALLOW_NETWORK=1` — and two refusals that meant "there is nowhere to fetch this from" no longer claim consent was the problem.
- The two guards that answer "is this reachable from the CLI?" now use one definition and agree. One counted only what the CLI passes to `design()` and so listed `effect` as unreachable on the day `--vep` shipped; both now count the resolver call site too. The README's absolute parity claim states how many exceptions there are and names the file holding them, and fails if a seventh appears.
- The cohort manifest header states what the run's output is, not only what the run was. A `--manifest --output-dir` run with no `--summary-tsv` left a directory of serialized menus and an index with nothing in it saying what any of it was — while the exemption excusing those menus named the manifest header as the thing that carried the context.
- `aforge batch --json` states what it is. The cohort summary TSV carried the research-use disclaimer, `/api/batch` carried it, every other JSON this CLI emits carried it, and the cohort JSON — the document a lab passes around after a run — did not.
- `aforge offtarget --json` emits the eight report fields it had drifted behind on, including which requested ancestries no loaded source can speak for and how many sites fell below the reporting threshold. The HTTP response had carried them all along, so the same script could see them through one shell and not the other. `aforge data list --json` also carries the `presence` sentence the API returns.
- `GET /api/data` and `GET /api/data/{name}` report whether a deployment can actually use each dataset. The listing had carried the licence permission alone, so an HTTP client was told AlleleForge may redistribute seven datasets the deployment does not have. All four registry surfaces now share one derivation.
- Thirty-three CLI tests decoded `CliRunner`'s interleaved stdout+stderr as JSON. They now decode `result.stdout`, which is the stream a pipeline reads — the assertion that was meant, and the one a message on stderr cannot break.
- `aforge bench compare` says when the results it is comparing came from synthetic stand-ins. It pronounced two of them “the same scientific result” without ever reading the flag, and its `--json` verdict now carries `synthetic_datasets` for a caller gating on `agree`.
- The served page no longer pans sideways on a phone: the download row is a flex row that never wrapped, so it ran 4px past a 375px viewport with three buttons and 128px with four.
- The served page no longer offers example inputs it always refuses (a ClinVar accession, an rsID and an HGVS string sat in the variant placeholder), and its banner stops promising that no sequence data leaves a deployment that has consequence annotation enabled.
- `aforge data show` answers whether a run can use the dataset right now, the question `aforge data list` already answered. It had printed the raw descriptor — `redistributable: True`, `sha256: None` — leaving the reader to know that the first is a licence permission and the second means the registry will not even fetch it.
- `aforge bench run` states that a number came from a synthetic stand-in in every output mode. The caveat had been printed only in the bare terminal summary, so the two readers who keep the number — `--out` and `--json` — were the two never told.

- **An ordering hazard reaches the table a pipeline filters on.** The oligo screen warns when an insert
  contains the assembly enzyme's own site (`internal-BsaI-site:pegrna-extension:+@27`) — the enzyme cuts
  the construct, a failure found after the DNA is paid for. It reached the HTML, the PDF and the JSON and
  not the TSV, which is what a pipeline reads before placing an order. Sequences stay out of that table by
  design; a short hazard string does not, and the table already carries `flags` as its per-row hazard
  channel. Empty when oligos were not requested, so "not screened" is never read as "screened and clean".
  TSV schema 9 → 10.

- **Every figure is checked to state where its numbers came from.** `SYNTHETIC_DATA_NOTE`'s docstring makes
  the argument — a figure is the artifact most likely to be seen alone, so a caveat living beside it in the
  report does not travel with it — and all four shipped figures do state their provenance, in three forms
  matched to their sources. Nothing enumerated the registry, so the failure mode was a *new* figure
  shipping without a data line. Now guarded, against the rendered SVG rather than the builder source.

- **`data list` no longer offers a fetch the registry will refuse.** The registry's second invariant is
  that no unverifiable artifact is fetched — a download requires a pinned `sha256` — and seven of the eight
  shipped descriptors carry none, so `resolve(..., consent=True)` raises `ChecksumError` for almost
  everything the table lists. The refusal is the guarantee working; the table was the part that had not
  been told, printing "supply or fetch it" uniformly. Rows now say which of the two a reader can actually
  do, derived per descriptor.

- **A documented endpoint is checked to exist.** The endpoint guard enforced "every route is listed" and
  not the reverse, so a renamed or removed endpoint would have kept its entry in both documents. Running
  the other direction found one discrepancy and a small one: both listed `GET /api/jobs/{id}` while the
  served path is `/api/jobs/{job_id}` — the endpoint exists, the placeholder was spelled two ways, and the
  documented spelling was the one that did *not* match the `job_id` field `POST /api/jobs/design` hands
  back. Aligned, and now checked in both directions.

- **The variables that enable the trained models are documented.** `ALLELEFORGE_LINDEL_REPO` and
  `ALLELEFORGE_BEDICT_REPO` are how the opt-in trained Cas9-outcome and base-edit-outcome models are
  pointed at their checkouts — named in the CLI's refusal when `--trained-*` is passed without them, and
  listed in no table a reader could consult. `XDG_CONFIG_HOME`, which decides where `config.toml` is looked
  up, was likewise unlisted. The env-var guard only checked *documented → read*; it now checks the reverse,
  because an undocumented setting is a capability nobody can turn on.

- **The two human renders are checked to carry the same fields.** The spec requires every field on "every
  human-readable surface (HTML and PDF alike), so the printable leave-behind is not missing a field the
  on-screen report shows", and the existing guard only asked whether a field reached *at least one*
  renderer — so a field rendered in HTML alone passed while violating the requirement. Parity held by hand;
  it is now checked, with the seam for a format-specific exception left empty and named, and the guard's
  own limits stated: it compares whole fields, not attributes reached through a local.

- **Every prediction's notes reach a reader, from one rule instead of two lists.** `_uncovered_notes`
  existed twice — once in the HTML render, once in the PDF — and both copies named `efficiency` and
  `bystander_burden` while neither named `p_intended_prediction`, so a note on the intended-allele
  probability would have reached the JSON and no human page. Latent, in duplicate. The rule is one shared
  function now and the prediction list is derived from the model, so a prediction field added later is
  covered the day it appears.

- **An untrained point estimate says so on the report.** A candidate read
  `Efficiency 0.60 [0.45, 0.75] @ 80% (nominal — coverage not measured)` — a parenthetical about the
  *band*, while the number itself came from an unfitted pseudo-random scaffold. The bundled model card
  carries that as its load-bearing sentence and `point_from_trained_model` records it per prediction; it
  reached no human surface, so the estimate was rendered in exactly the typography a trained model's would
  get. Both renders now mark it, naming the method, for efficiency and P(intended) alike — and leave a
  trained estimate unadorned.

- **A mixed-matrix report names the matrix behind its headline number.** The report carries no per-site
  rows by design — it summarises, and the lossless export has the sites — so on a mixed table its effective
  matrix reads `published + approximation`, telling a reader both scales were used and not which produced
  the worst-case score. That score is the number that drives the safety axis, the ancestry table and the
  triage decision. Every render now names the matrix that scored the worst site, and stays quiet when the
  table is homogeneous. TSV schema 8 → 9.

- **A bulged off-target no longer reads as a perfect match.** Three of the five rows in a real bulged scan
  printed `mm=0` while being 21-nt or 19-nt alignments through a gap; only the interval width gave that
  away, and no reader computes it. `mm=0` is the most reassuring thing a row can say. Non-zero bulge counts
  now appear beside the mismatch count — which is also what explains the fallback matrix beside them, since
  the published one is defined only for a 20-nt ungapped alignment — and an ungapped table is unchanged.

- **A mixed-matrix off-target table says which scale each row used.** The published CFD matrix is defined
  for a 20-nt ungapped alignment, so a bulged or off-length hit falls back to the length-relative
  approximation *per site* — one report, two scales, rows printed in score order. `effective_matrix()`
  named both but could not say which row was which, so a published `0.50` and an approximated `0.60` sat
  adjacent with nothing to tell them apart. The JSON has carried `score_matrix` per site all along; the
  human form now does too, and only when the report is genuinely mixed.

- **The cohort summary qualifies the column it is sorted by.** A cohort is triaged by sorting
  `best_efficiency`, and a real run puts `base_abe 0.6000` next to `prime 0.3657` — outputs of different,
  mutually uncalibrated models. The single-variant menu states this in its rationale (above); the surface
  *designed* for sorting had nothing, which is the wrong way round. The note is one shared constant rather
  than two wordings, sits in the `#` block so a comment-skipping reader still gets a clean table, and is
  omitted when every row's best candidate is the same chemistry.

- **A cross-chemistry menu says its efficiencies are not one scale.** A real menu orders `prime 0.366`
  against `base_abe 0.400`, and those come from different models — `pridict2-baseline` and
  `be-dict-baseline`, both named in the provenance, neither calibrated against the other. Projecting onto
  four shared objectives is what makes the ordering possible; it does not make the efficiency axis one
  measurement. The leaderboard already refuses to rank across metrics and says why; the design menu, which
  *does* rank across chemistries because a user needs one list, had no equivalent sentence. It does now,
  only when the menu actually spans chemistries.

- **The docs' two-task leaderboard is pinned to keep the tasks apart.** `docs/api/cli.md` documents scoring
  two tasks and rendering one board. A Spearman on a regression task and an AUROC on a classification task
  are not comparable, and the spec says a rank never crosses a comparison group — so a refactor that merged
  the groups would put `0.7500` above `0.0000` as though one model beat another, which is the most
  plausible way for that board to become actively misleading. The documented chain is now executed and the
  grouping asserted; collapsing the comparison group turns it red.

- **The README's benchmark walkthrough is executed by the suite.** Four commands presented as the way to
  use CRISPR-Bench — list, score, write a signed result, render a model-card-gated board — proofread by
  existing guards (real flags, real symbols) and run start to finish by none. A renamed subcommand, or a
  leaderboard that rejected the result `bench run` had just written, would have survived review of the
  most-read file in the repo. The commands are now parsed out of the README and run in sequence, with the
  final glob expanded against the files the earlier steps actually produced.

- **The build-mismatch remedy is pinned end to end.** `resolve` refuses a record whose native assembly
  disagrees with the requested build and names `aforge lift ... --chain ... --from ... --to ...`; `lift`
  documents that its output is "in the same locus form `design --region` accepts, so the result pipes
  straight back in". Two claims across three commands, run by nothing. Now tested: the flags in the refusal
  exist, a real chain file maps a locus, the printed locus is accepted verbatim by `--region`, and an
  unmappable locus prints `UNMAPPED` with a non-zero exit rather than being dropped — a silently shorter
  list is a smaller search, which reads as a cleaner guide.

- **An unmeasured off-target axis is pinned never to render as a number.** `0.0` in a worst-case column and
  `1.0` in a specificity column are the *reassuring* values, and this project has shipped that confusion
  once already (`worst_offtarget: 0.0` for a candidate with no report). The guard derives the field list
  from `CandidateReport` rather than listing today's seven columns, so an off-target field added later is
  covered the day it appears — and it checks the model, the TSV and the JSON, since a value can be
  suppressed on one surface and invented on another.

- **The safety axis is pinned monotone under adding an off-target.** This project shipped that bug twice —
  a patient off-target masked on the safety axis, and a benign ancestry-tagged site *raising* a candidate's
  safety by switching `worst_ancestry()` onto a stratified path that never saw the danger. Both fixes left
  behind a regression test for their own case and no property test, so the invariant they restored was
  guarded only against those two shapes. Now swept over every subset of a mixed pool (reference,
  ancestry-tagged, patient, and a population site whose attribution is unknown), plus the composite
  ranking. Verified by reintroducing the historical bug: safety rises 0.50 → 0.80 and the test fails.

- **A wider off-target search is pinned never to report a safer guide.** Raising the mismatch budget,
  lowering the reporting cut-off, or allowing bulges can only find more, so no result from a wider search
  may look better than the cheap one — the worst direction for that failure to run in, and a class this
  project has already shipped once (a benign ancestry-tagged site *raising* a candidate's safety score).
  Now tested, including the subtlety that makes the naive form of the property false: the engine keeps the
  best-scoring alignment per site, so a hit realigned through a bulge reports a different interval, and what
  must hold is coverage — every ungapped site overlapped by a bulged site scoring at least as high.

- **The documented scientific defaults are pinned to the code.** The off-target budgets and reporting
  thresholds (`CFD >= 0.20 or MIT >= 0.10`, `<= 4 mismatches`) and the pegRNA geometry (`PBS 8-17 nt`,
  `RTT 7-34 nt`) are restated fourteen times across the README's feature and parameter tables, its
  architecture diagram, the prime API page and the population concepts page — agreeing by hand and checked
  nowhere. A reader takes those numbers as the tool's operating envelope; they are what a scientific claim
  rests on. Every documented occurrence is now compared against `search()`'s signature and
  `PBS_RANGE`/`RTT_RANGE`.

- **The documented exit codes are pinned to the enum.** They are written out four times — `ExitCode`, the
  CLI spec, the `docs/api/cli.md` table and a README sentence — and only the spec copy was checked against
  the code. Exit codes are the part of a CLI that scripts branch on, so a fifth code or a renumbering would
  have left two documents telling pipeline authors the wrong thing with a green suite. All three copies are
  checked now, including against each other.

- **The job status contract names the states it emits.** `JobStatusResponse.state` was typed `str` and
  described as "queued | running | done | error" — and nothing emits `queued`; a job starts `pending`. A
  client polling until the state leaves the documented first value waits forever, and a bare string field
  put nothing in the OpenAPI schema for that prose to be checked against. It is the enum now, so the four
  values travel with the schema. The neighbouring `progress` field had been typed and documented for
  exactly this reason.

- **A failed design job reports what the synchronous call reports.** `POST /api/design` with an unparseable
  variant answers `422 {"detail": "unrecognized variant input: ..."}`; the identical request through
  `POST /api/jobs/design` recorded `HTTPException: 422: unrecognized variant input: ...` — the framework's
  exception class and an HTTP status glued to the front of the one sentence a caller can act on, in the
  field whose whole job is carrying that sentence. Exceptions without a `detail` keep their type name,
  which is a real clue when the message alone is opaque.

- **The browser UI says what the deployment can actually search.** Its status line reported one bit —
  `reference loaded` or not — while the Populations box invited ancestry labels whose usefulness depends
  entirely on operator configuration a browser user cannot see or supply. It now reports the loaded
  population source, haplotype panel and track names, and names a configured source that could not be read
  separately from one that was never configured. The comment in `app.js` asserting that no file-backed
  source can reach this deployment "over HTTP ... always" was the last place still claiming the old state.

- **The web API docs no longer call a working endpoint unimplemented.** The endpoint table said
  "`GET /api/bench` | CRISPR-Bench (`501` until Phase 14)"; Phase 14 shipped and the endpoint returns all
  five tasks with their kind, chemistry, dataset and metric battery. A reader following the docs would not
  call it — a capability made unreachable by prose rather than by code, which is the same outcome as not
  having built it. The health row and the deployment-configuration paragraph are current too, and a test
  now fails if any endpoint the docs describe as not-implemented actually works.

- **The README explains all three off-target summary numbers.** It described the worst case and the
  aggregate specificity, and said specificity "surfaces on every output surface that summarizes
  off-target" — then `expected_burden` was added to those same surfaces and the paragraph was not
  revisited. The one number that tells a rare-variant off-target from a universal one was undocumented in
  the place a reader goes to understand the summary. Now explained, including that it appears only when
  some site's presence is probabilistic, so its absence is not read as "no burden".

- **The README describes the web surface that ships.** It explained that the four file-backed inputs were
  "deliberately absent" from the web API because a client-supplied path would be a server-side file-read
  primitive, and that the surface "needs server-side configuration like the reference already has". The
  reasoning was right and the conclusion had moved on: three of the four are now configured exactly that
  way. `--patient-vcf` stays out for a different reason — a personal genotype is the caller's data, not the
  operator's — and a test now checks each half of the claim rather than trusting the paragraph.

- **Two live code paths that no test ran are now covered.** The PEP 562 lazy re-export in `alleleforge.genome`
  — the whole point of which is that `from alleleforge.genome import ReferenceGenome` keeps working without
  importing `pyfaidx` at package import — was exercised nowhere, so a typo in the deferred-name tuple would
  have surfaced at a user's first attribute access. And `population-offtarget`, the flag saying a
  candidate's off-targets exist only on population alleles, was emitted by a line the suite never reached.
  Both behave correctly; neither had anything watching them.

- **A misconfigured data source is distinguishable from an absent one.** Each optional source recorded why
  it failed to load, and only the reference's reason was ever read. So
  `ALLELEFORGE_GNOMAD_TSV=/data/typo.tsv` and configuring nothing at all both returned `gnomad_loaded:
  false` — an operator's broken mount indistinguishable from a deliberate choice, on the axis that decides
  whether any population site can be nominated. `GET /api/health` now reports `source_errors`.

- **The cohort/single-variant option parity is enforced, not just stated.** The spec has required since it
  shipped that "every option `aforge design` accepts SHALL be accepted by `aforge batch`" — established once
  and guarded by nothing, so every option added since had to be copied by hand and the failure mode was a
  flag silently missing from the surface where it matters most. Now a test, covering the web's
  `DesignRequest`/`BatchRequest` too, where this session watched the drift happen in real time.

- **A report no longer tells an API client to pass a CLI flag.** `search_description()` — a library method
  returned verbatim over HTTP and rendered into every report — advised "pass `--gnomad` or `--haplotypes`",
  flags that exist on one of the three shells and that an HTTP client or Python caller cannot pass at all.
  It names the capability now; the CLI keeps its own flag-specific warning.

- **`verify` names the sidecar when handed the artifact beside it.** `design --format html` prints "wrote
  report.html and report.html.provenance.json", so the obvious next command is `aforge verify report.html`
  — which answered with three stacked pydantic validation errors and `errors.pydantic.dev` links. The
  tool already knew the answer: `verify`'s own docstring says the sidecar is the only machine-readable
  provenance an html/pdf/tsv run leaves behind. The refusal now names that path, and the detailed validator
  output is kept for a malformed file with no sidecar beside it, where there is no next command to name.

- **`resolve` says whether a genome checked its answer.** Without a reference it performs neither
  left-alignment nor REF-allele validation, so `chr2:1006:T>A` where the genome has a `G` came back as a
  clean normalized SNV with exit 0 — while the same input with `--reference-fasta` is refused by name
  ("asserted ref 'T' but reference has 'G' (wrong build?)"). For a correct variant the two payloads were
  **byte-identical**: nothing in the artifact said whether the normalization had been checked at all, on the
  command whose whole job is telling a caller what their input means. Every form now carries
  `reference_checked` and, when one checked it, the genome's identity — `build` is a caller-supplied label
  that reads `hg38` whether or not any FASTA was opened.

- **`resolve` states the coordinate convention its loci are in.** It prints a normalized variant position
  and a working interval, and said nothing about 0-based half-open versus the 1-based inclusive form a
  genome browser shows — the off-by-one this project keeps a named constant for. The report footer, the
  cohort TSV header and both off-target surfaces all carry it; the command whose entire job is telling a
  caller what their input means did not. Added to the human render, the JSON payload and
  `POST /api/resolve`.

- **Each artifact's disclaimer describes that artifact.** Found by starting the API as `docs/deployment.md`
  documents it and reading the responses: `GET /api/health` — a liveness probe — returned "The candidates
  below are ranked ... Every off-target nomination is computational and must be experimentally validated",
  promising validation of nominations it does not make about candidates it does not have. The standalone
  off-target surfaces had the mirror-image problem. Three wordings now, nested so every artifact still
  carries the core research-use sentence: core alone for status, core plus validation for an off-target
  nomination, the full text for a ranked menu.

- **A reference-only cohort row still reads differently from an unsearched one.** Blanking empty
  collections in the cohort TSV (above) would have collapsed `offtarget_sources` `{}` — a search ran, no
  optional source was supplied — into the empty cell that means no search happened at all. It now renders
  `reference-only`, which is what the CLI already calls that state.
- **The cohort TSV is readable without a Python parser.** `_batch_tsv` passed every value through `str()`,
  so the file a pipeline reads carried `['pol3-terminator', 'gc-out-of-band:0.20']` in a tab-separated cell,
  `{}` for an empty mapping, and `0.44999999999999996` for a rounded interval bound. `report/export.py` —
  this project's *other* TSV — formats before it renders: four decimal places, `;`-joined flags. Now both
  do, with empty collections rendering as empty cells and a populated mapping as `gnomad=3;reference=1`.

- **A cohort row leads with what happened to that variant.** `_decline_reason` flattened every rationale
  bullet in report order, and routing rationales come first because the report reads top-down while a cohort
  row is scanned left to right. So a no-op input gave three definitions of what each chemistry is *for* and
  then, 700 characters in, the one sentence about the input: the reference and desired alleles are
  identical. Nothing is dropped — a cohort row is often all a reader sees for that variant — but the run
  notes lead. They became separable when the rationale gained its own heading for them.

- **A base-editor candidate can now say it is out of distribution.** `ood` is the sharpest label the
  honesty machinery has — the point estimate should not be trusted, and the candidate was ranked on its
  lower interval bound. `design/cas9.py` and `design/prime.py` both raise it; `design/base_editor.py`'s
  `_flags` was never handed the efficiency prediction, so no base-editor candidate could carry it whatever
  the predictor said. The ranker was never fooled — it reads `in_distribution` directly and was already
  demoting such a candidate — so one could be *ranked* as untrustworthy and *rendered* as ordinary.
  Reachable through the documented `base_outcome_predictor` override, where a trained model's OOD detector
  legitimately returns `False`.

- **A Pol III terminator in the spacer is flagged on every chemistry.** Four consecutive Ts end U6
  transcription, so the guide is never made at full length — categorically worse than the two caveats
  `design/spacer_quality.py` already shared. The check stayed behind in the prime vertical when the others
  moved, so the same constraint had three answers: prime refuses the protospacer, the Cas9 efficiency model
  docks 1.5 logits, base editing said nothing. The golden reproducibility fixture shipped the proof — its
  single `recommended` candidate is an ABE8e sgRNA on `TTTAAACGTTTTTTTTTTTT`, flagged for GC and a missing
  5' G, silent about twelve consecutive Ts, reproduced byte-exactly on every run. Now annotated by the
  shared module and classified as a hazard naming its consequence.

- **The menu rationale's headings are true of the lines under them.** Run outcomes and caveats were appended
  as bare `- ` bullets directly beneath "Why the other chemistries declined:", in that list's own format, so
  a reader met `- prime: 90 candidate(s)` as a reason prime declined — on a page where prime produced all 90
  candidates. Worse, the chemistry that declined for a *runtime* reason (no PAM in range) sat among those
  never eligible at all, though the two send a reader somewhere different. The notes now have their own
  heading.

- **A population off-target now says how common it is, to a person as well as a machine.** Running the real
  `aforge offtarget --gnomad` on the rs114518452-style reference-bias case printed
  `score=1.0 ... population chr2:32:T>G` — the same string whether the causal allele is in one genome in ten
  or one in a thousand. The JSON had carried `frequency` and the per-ancestry breakdown all along, and the
  HTML and PDF have shown the per-ancestry worst case since it existed, so the CLI user of the feature this
  project exists for had to re-run with `--json` to learn whether the site mattered. The row now ends
  `carried at 0.105 (afr 0.105, nfe 0.001)` and the summary carries the per-ancestry worst case. A
  reference-only scan prints neither.

- **The documented ensemble size and interval level are pinned to the code.** `N=5` and `80% interval` are
  restated in six and seven places — the README, the concepts page, the preprint, and the bundled
  `cas9-efficiency-ensemble` **model card** (both as prose and as `metrics.ensemble_size`). Nothing tied any
  of them to `DEFAULT_ENSEMBLE_SIZE` / `DEFAULT_INTERVAL_LEVEL`, so changing one constant would have quietly
  falsified a model card and a preprint with a green suite. A model card that describes an ensemble the code
  no longer runs is worse than no card, because it looks like disclosure.

- **The frequency-weighted off-target burden reaches a reader.** `expected_burden()` weights each site by
  the probability a genome carries it, so a 0.1%-MAF population hit and a universal reference hit of the same
  raw score — indistinguishable in the frequency-blind `worst_score` and `specificity` — are weighted a
  thousandfold apart. Population-aware nomination is the project's differentiator and the shipped spec says
  the burden appears "in the summary numbers"; it was on the model and on no surface. It now appears in the
  HTML, the PDF, the TSV (`offtarget_expected_burden`, schema 8), the JSON, `aforge offtarget`, and
  `POST /api/offtarget` — reported only when some site's presence is probabilistic, since with reference
  sites alone it merely restates the score sum. Every surface asks the same
  `OffTargetReport.is_frequency_weighted()` so they agree on when it is worth showing.
- **The documented TSV `schema_version` matched the code again.** `docs/api/cli.md` named version 6 while the
  exporter shipped 7 — the one field a consumer is told to branch on, wrong where they read it. Now pinned
  by a test.

- **`resolve` says why it recommends another build.** Both shells answered with a bare
  `"reference_recommendation": "T2T-CHM13v2"`, and the CLI's human render — what a person actually reads —
  did not mention it at all. `ReferenceRecommendation.reason`, which names the regions that triggered it,
  was consumed by nothing. The build name is an answer with the question removed; the cause is the part that
  matters, because a segmental duplication is where a read cannot be placed uniquely and so where an
  off-target search under-reports. Both surfaces now carry
  `reference_recommendation_reason`, and an ordinary locus still says nothing.

- **A design inside a segmental duplication now says so.** The resolver already flagged loci overlapping
  segdups, centromeres, and other hg38-difficult regions, built `ambiguous-region:<kind>` and
  `recommend-reference:<build>` flags for them, and recommended T2T — and
  `ReferenceRecommendation.apply_to`, its own docstring calling it "the wiring point into the Phase 1 result
  types", had no caller. A design at a flagged locus returned 70 candidates, an HTML page, a PDF and a JSON
  export, none mentioning it: the condition under which a read cannot be placed uniquely, which is when the
  off-target search under-reports. The designer now applies it, `ambiguous-region` is classified as a caveat
  with the consequence spelled out, and the flag-classification guard was rebuilt on the AST — its regexes
  had missed three emission idioms, and each miss was a flag rendered with no sentence behind it. Its
  "classified but nothing emits it" check now covers `CAVEAT_FLAGS` too, which is what `recommend-reference`
  had been failing silently.

- **Every shell spells the ranking objectives from the ranker.** `design.ranking.OBJECTIVES` names the four
  axes; the CLI held its own copy, and the web API held two more — a hardcoded `min_length=4`/`max_length=4`
  and a positional `e, c, s, p = weights_in` unpack. Four spellings of one fact, which agreed only about the
  objectives that exist. A fifth would have been unreachable from every shell at once, with the CLI refusing
  the very table naming it and the API rejecting the vector as too long. The shells derive from `OBJECTIVES`
  now, and a test pins the one pair that cannot derive — the tuple against `RankingWeights`'s fields.
- **The leaderboard no longer guesses which direction a metric ranks.** Two tables in the same package
  answered "does higher win?" by opposite defaults: `runner.HIGHER_IS_BETTER` raises on a metric it does not
  know, while `leaderboard.LOWER_IS_BETTER` was a hand-written denylist, so anything outside `{kl, ece}` was
  silently ranked descending. `primary_metric` is a free-form string on a submitted result, so a submission
  ranking on `rmse` put the worst model in first place and printed `rmse ↑` beside it. `LOWER_IS_BETTER` is
  now derived from the runner's table — one fact, one place — and a submission whose ranking metric has no
  declared direction is refused, naming the metrics that do.
- **`make ci` now reproduces CI's lint job, which was failing.** CI runs
  `ruff check|format --check src tests scripts examples`; the Makefile's `lint` target ran
  `src tests scripts`, so the local gate reported green over three paths while CI ran four. With the pinned
  `ruff==0.15.21`, `examples/03_batch_vcf.ipynb` fails `ruff format --check` — it reached `main` because
  nothing local could see it. The notebook is formatted (and still executes), the Makefile matches, and
  `test_gate_mirrors_ci.py` — which compared job *names* to target *names* — now compares the commands, with
  a reasoned escape list that is empty.

- **A cohort was silently smaller than the VCF it came from.** `iter_vcf` drops three kinds of row, all of
  them correctly — none names a designable substitution: a soft-filtered call (`FILTER` is not PASS, skipped
  by default), a row whose REF is symbolic, and a symbolic ALT (`<DEL>`, `<DUP>`, a breakend, the `*`
  spanning-deletion allele). A real VCF carries all three routinely. Six rows in a synthetic example yielded
  two design requests and the run reported success, with nothing anywhere connecting the two numbers. The
  batch summary now carries an `ingest:` line naming the count per reason — and stays silent when nothing was
  dropped, since a caveat that fires always is a caveat nobody reads. The counts are also in the `--json`
  payload. Deliberately counted as **drops** rather than rows: a multi-allelic row can lose one ALT and keep
  another, and "N of M rows yielded nothing" would be false for exactly the row a reader most needs to know
  about — the one that came through incomplete.

- **A parallel cohort over a FASTA with no `.fai` yet raced to build it, and failed items with the wrong
  error.** `design_many` documented the precondition — the FASTA "must already carry its `.fai` index, so the
  concurrent first-opens read it rather than racing to build it" — and both callers in this tree honored it.
  A caller who does not gets `KeyError: unknown contig 'chr2'` on some items, some of the time: the contig is
  there, the index was mid-write when a second thread read it. Measured at 2 failures in 20 runs on a
  four-item cohort. The remedy the docstring asked the caller for is one line, so `design_many` now does it —
  it opens the factory once before starting the pool — and the precondition is gone rather than documented. A
  documented precondition whose violation is a race is a bad trade: non-deterministic, parallel-only, and it
  reports the one thing that is not wrong.

- **`lift_interval`'s docstring described the algorithm it had been changed to stop using.** It said the method
  "lifts the first and last bases independently and rebuilds the span". The code lifts *every* base, and the
  comment three lines below it explains why: an endpoint-only check passes a **balanced** interior chain gap —
  a source deletion and a target insertion of the same size — because the endpoints still map and the span
  length is unchanged while the interior maps to nothing. The implementation was strengthened, the guarantee
  is tested, and the docstring went on describing the weaker version whose hole the change closed. Unusually
  for this project the doc *understated* the guarantee, so a reader auditing for that exact hazard would have
  concluded it was present.

- **A search that examined nothing exited 0.** Over a truncated reference — a contig header with no bases,
  which is what an interrupted download leaves — `aforge offtarget` prints `0 site(s), worst score 0.000,
  specificity 1.000` and, underneath, "NO SEQUENCE WAS SEARCHED … this is not a clean result, it is an empty
  one". The human reading the terminal is told plainly; a pipeline branching on `$?` saw a spotless guide.
  That is the same "not measured printed as clean" the warning exists to prevent, one surface over. It now
  exits `MISSING_DATA` **after** saying why — `aforge batch` already draws this distinction, where a run whose
  items failed completes without having succeeded. The `--json` payload had the matching gap: its `search`
  block carried the budgets and cut-offs but not the extent, so a machine consumer could not tell a
  genome-wide scan from a 140-base one, nor see the zero that makes every other number meaningless. It now
  carries `searched_bases`, `resolved_bases` and `maf_threshold`.

- **Two cohort workers writing the same output file shared one temp file.** `_atomic_write_text` named its
  temp file `<path>.<pid>.tmp` — unique per *process*, while the function runs inside `_design_one`, which runs
  in a worker thread. Two items with the same id resolve to the same output path and therefore the same temp
  path, and a variant repeated in a VCF is ordinary while `--max-workers` is on `aforge batch`. Both threads
  write one file and both rename it: the first `os.replace` moves the temp away and the second raises
  `FileNotFoundError`, which the cohort records as "unexpected FileNotFoundError (likely a defect)" against an
  item whose data was fine; other interleavings leave the two payloads mixed in the export the module calls
  lossless. The temp name is now unique per call. The atomicity itself was never wrong — temp file plus
  `os.replace` is right, and so is the encoding pin above it; the *name* was wrong.

- **A cohort re-run skipped the items that had failed, and reported a clean, empty run.** Resume skipped any
  item the manifest mentioned — including the ones recorded with `status: "error"`. A cohort of 10,000 that
  finished with 200 failures skipped all 10,000 on the next run, reporting `total=0, failed=0` and **exiting
  0** where the first run had exited non-zero. "Re-run until it passes" worked, by doing nothing, and the only
  way to retry the 200 was to delete the manifest and lose the 9,800. A failed item did no work worth
  preserving — resume exists to avoid recomputing *results* — and retrying is cheap, since these fail at
  resolution before any search. Resume now skips only what succeeded.

- **A manifest whose last line was truncated crashed the resume.** An append interrupted mid-write leaves
  exactly that, and `json.loads` raised `JSONDecodeError` from the one code path whose whole purpose is
  recovering from an interrupted run. (A sibling test tolerates *blank* lines, so malformed lines had been
  considered and the wrong case handled.) A truncated **final** line is now treated as the interrupted append
  it is, and its item runs again. A malformed line anywhere else is still an error, naming the line number:
  that means a corrupt or hand-edited manifest, where silently skipping would silently recompute or silently
  drop an item.

- **The README repeated the cell-context overclaim that had just been corrected everywhere else.** It said
  `--cell-context` "raises the out-of-distribution flag on **every** efficiency prediction" — true of the prime
  vertical and of nothing else. The same sentence had been fixed in the CLI help and in both web request
  models in the round before, and missed here, which is the argument for a check rather than more care. The
  README now says which vertical consumes it and what the other chemistries' in-distribution flag describes.

- **A cell context two of three chemistries never looked at, reported as in-distribution.** `cell_context` is
  consumed by the prime vertical alone — `design_cas9` and `design_base_editor` have no such parameter — so for
  those chemistries a supplied context is never examined. With a context no scorer recognizes:

      prime          -> ood flag, in_distribution=False
      cas9_nuclease  -> no flag,  in_distribution=True
      base_abe       -> no flag,  in_distribution=True

  Those two `True`s are truthful about what they measure — `context_in_distribution` checks the *guide*
  context, no ambiguous base and long enough for the head to read, and is never hardcoded — and that is what
  makes them misleading. A reader who asked for K562 sees `in_distribution: True` beside a nuclease candidate,
  in a column a pipeline filters on, and reads it as a statement about K562. The rationale now names the
  chemistries that could not consider the context, and says what their in-distribution flag does describe. The
  fix is a declaration rather than an invented OOD check: fabricating a cell-context distribution for scorers
  that have none would be worse than the silence. The CLI help and both web request models said the context
  "flags **every** efficiency prediction out-of-distribution"; they now say which chemistry consumes it.

- **A design run scoped to a gene panel scanned the whole genome anyway, for two of three chemistries.**
  `design()` takes `offtarget_regions`, documents it, records it in the provenance snapshot, and exposes it as
  `--region` / `--regions-bed` on both `aforge design` and `aforge batch`. All three verticals accept the
  parameter. Two of the three call sites did not pass it: the base editor did, **SpCas9 nuclease and prime
  editing did not**. So the restriction was inert for the two most-used chemistries, and the artifact said
  otherwise — the snapshot recorded the intended scope while the engine scanned every contig:

      offtarget_regions=[chr2:0-50]  ->  provenance: 50 bases, actually searched: 140

  Both directions of that are wrong. A scan wider than asked for is slower than asked for, on the axis where
  the `--region` help says scoping "is usually what makes a run practical" — so against a real hg38 a
  panel-scoped design run was a whole-genome one, which is the difference between practical and impossible.
  And the provenance asserted a restriction that was never applied, which is the claim a re-run is checked
  against. The bug was invisible to everything: the parameter existed end to end, every signature accepted it,
  the suite was green, and a region naming a contig the reference does not have — which `search()` refuses by
  name — was accepted without a word, because it never reached `search()`.

- **Three ancestries requested, an empty breakdown, and nothing in the report saying the request went
  unhonored.** `--populations` names the labels to stratify by; it supplies no alleles. Asked for three with no
  `--gnomad` and no `--haplotypes`, the scan is reference-only and the breakdown comes back empty — which, as
  the CLI's own warning puts it, "reads like 'no ancestry-specific risk found' rather than 'nothing was
  searched'." That warning went to the terminal. `unbacked_populations`, the field that carries the same fact
  into the HTML page, the PDF and the TSV, was switched off in exactly this case by a trailing `if backed else
  ()`, on the reasoning that the CLI warned separately. So the durable artifact said nothing and a library or
  web caller was told nothing at all. The two cases — no source, and a source lacking the label — differ in
  how a user fixes them, not in what the report has to say.

- **The population cut-off decided the verdict without appearing in it.** The MAF threshold decides which
  population alleles enter the scan at all, one step earlier than the reporting cut-offs the description
  already named. Against a source holding one 2% PAM-creating variant: `maf=0.001` gives 1 site at
  specificity 0.500, `maf=0.05` gives **0 sites at a clean 1.000** — and both descriptions were identical on
  that axis. The existing note for an inert source made it worse by naming the wrong cause, attributing to the
  locus ("contributing nothing *in this region*") what the caller's own threshold had done. The cut-off is now
  named whenever it applied, and the inert-source note names it too. A reference-only scan still says nothing
  about MAF, since a provenance line that is always present teaches a reader to skip provenance lines.

- **A panel scan and a genome-wide scan described themselves identically.** `search_description()` exists so
  that "a reader comparing two reports" can do so — the site count, the worst score and the specificity are
  all conditional on the settings it names. It named the mismatch and bulge budgets and the two reporting
  cut-offs, and not the *extent* searched, which is the setting that moves the numbers most. Scoping to a gene
  panel is the ordinary way a run is made practical; the `--region` help says so outright. Over a two-contig
  reference holding the same locus twice, restricting to one contig gave **1 site at specificity 0.468** where
  the whole reference gave **2 at 0.305** — and both printed the same provenance string, because
  `searched_bases` was mentioned only when the *resolved* fraction was degraded and both resolved fully. The
  smaller search, the one that finds fewer off-targets, read as the safer guide. The extent now leads the
  description. A report whose `searched_bases` is unset (the field has a default, so an older serialized
  report arrives at 0 with its sites attached) says its extent is unrecorded rather than claiming zero.

- **The README said human-readable reports were 1-based. They are 0-based half-open.** One row of the
  coordinate cheat-sheet lumped HGVS together with "human-readable reports" and labelled the pair 1-based.
  HGVS is; the reports are not, and say so in their own provenance block. A reader trusting the table would
  have read the new `locus` as 1-based inclusive and landed one base off — the single failure the whole
  surface exists to prevent. The row is split, and a test pins the table against the report's own note, which
  live in different files.

- **A `NaN` threshold silently changed which off-target sites were reported.** `--cfd-threshold -1`, `2` and
  `inf` are all refused with a usage error; `nan` was accepted, because Click's `min=0.0, max=1.0` is a pair
  of comparisons and every comparison against `NaN` is False. The value then reached a consumer that compared
  against it, where the same property decided the outcome by whichever way that consumer's test happened to be
  written. The site filter is a *skip* test, so a `NaN` threshold skipped nothing and reported every site —
  while the report printed `sites reported at CFD >= nan`, a cutoff it was not applying. The population filter
  is an *include* test, so `--maf nan` admitted no record at all: **every population off-target disappeared**
  and the report read as a clean bill of health on the population-safety axis, with no error and no warning.
  Non-finite `maf`, `cfd_threshold` and `mit_threshold` are now refused by name at both public entry points —
  `search()`, which every shell, web and cohort caller passes, and `enumerate_population_sites()`, where the
  mask occurred — before anything is scanned. This is R186's shape found in a live input rather than a latent
  one: the same expression property, this time reachable from the command line.

- **A declined chemistry gave no reason unless *every* chemistry declined.** The routing rationales were
  computed either way and shown only for an empty menu. `base_abe=no` is least actionable precisely for the
  reader who needed a base editor — someone avoiding a double-strand break, who sees a prime candidate and no
  statement of why the chemistry they wanted was unavailable. Declines are now always explained. Beside a
  real menu the first sentence only: the SpCas9 rationale runs to 540 characters, and a paragraph per
  declined chemistry in every report buries the candidates; where nothing is eligible that text is the whole
  content and is kept whole.

- **An edit that changes nothing reported "no candidate was examined".** Prime enumeration refuses three
  things before it examines any protospacer — a no-op edit, an edit longer than prime editing spans, a
  desired allele no RTT can carry — and all three fell through to the empty-tally placeholder. A user who
  typos `chr7:3004:A>A` was told nothing about the actual problem. Each now names itself; the earlier work
  had taught the enumeration *loop* to explain itself and left the early returns silent. (The
  "edit too large" wording also said "replaces more reference bases", which describes only half its branch —
  a 60-base insertion replaces one.)

- **The interactive report showed the oligos as a JSON dump; both surfaces now share one block.** A
  serialized object "contains" every field, which is how the HDR donor and the prepended-G note counted as
  rendered in the HTML while being absent from the sheet a lab orders from — and it is not what a reader
  scanning a report reads. The HTML now renders the same lines the printable sheet builds, so the two cannot
  drift again.

- **The printable order sheet omitted the HDR donor — half the reagent.** `oligos_for` pairs a precise Cas9
  candidate with its repair template, and its own test says why: *"returning only the guide would hand the
  bench the half that cannot edit."* The PDF then handed the bench exactly that half — no donor sequence, not
  even the word "donor" — while the candidate line above read "+ HDR donor 100 nt", so a reader knew one
  existed and could not order it from the page. The sheet now carries the donor's sequence, length, re-cut
  disposition, note and warnings. The field-coverage guard is extended to both oligo models, checked against
  the PDF's hand-formatted block specifically: the HTML dumps the whole record as JSON, so every field is
  trivially "present" there and nothing is learned.

- **The printable order sheet did not say that the cloned guide differs from the scored spacer.** U6
  transcription needs a 5' G, so the lentiGuide scheme prepends one when the spacer lacks it — the duplex a
  lab orders encodes a **21-nt** guide while every efficiency and off-target number on the page describes the
  20-nt spacer. The oligo record carries `g_added` and the HTML buries it in a JSON dump of that record; the
  PDF's formatted block, which is the sheet someone actually orders from, omitted it. It now names the added
  G, both lengths, and the spacer the scores belong to.

- **`chromatin_track` without `encode_tracks` ran to completion and recorded a provenance entry that was not
  true.** The track name selects a track from the supplied ENCODE tracks; supplying only the name produced a
  normal menu, wrote `chromatin_track: 'DNase'` into the provenance config snapshot as though the run were
  chromatin-aware, and then reported *"chromatin track 'DNase' was supplied but covers none of the candidate
  loci"* — asserting a supply that never happened and sending the reader to inspect the coverage of a file
  they do not have. The CLI refused the combination; the library, the cohort and the web API did not. Now
  refused in `design()`.

- **A region naming an unknown contig crashed the library with a bare `KeyError`.** The CLI checked this and
  said which contig, which the reference actually has, and that *"a dropped region searches less than you
  asked for"* — the library and the web API got `KeyError: "unknown contig 'chrNOPE'"` from deep inside the
  fetch. A panel built against another assembly or naming convention is the ordinary way this happens. The
  check moved into `search()`, and the CLI's early exit now calls it rather than keeping a second
  implementation of "is this contig known".

- **The MIT/bulge refusal was in the CLI, so the library still crashed mid-scan.** Two rounds ago the
  combination was refused at the shell — but `search()` is what the library, the cohort path and any future
  web caller go through, and they still hit `ValueError: … this one is 19 nt` from deep inside the scan,
  which reads as a complaint about the caller's spacer while the caller's spacer is fine. The guard moved into
  `search()`, where every caller passes; the CLI's duplicate is gone rather than left as a second
  implementation of the same rule.

- **A conformal interval claimed coverage its calibration set could not support.** Split conformal takes the
  `ceil((n+1)·level)`-th smallest normalized residual; when that rank exceeds `n` the implementation correctly
  falls back to the largest residual, but the guarantee that fallback carries is `n/(n+1)`, not the level
  requested. Three calibration points and a 0.95 target produced a prediction labelled
  `interval_level=0.95, calibrated=True` **with no notes** — while the coverage it actually guarantees is
  0.75, and a strict 0.95 needs 19 points. The code's comment knew; the artifact did not, in the module that
  implements this project's headline claim. Intervals are now labelled with the coverage they *earn* and
  carry a note naming the shortfall and the required size, and `min_calibration_size(level)` is public so a
  caller can size a set before fitting. That helper's obvious closed form
  (`ceil(level / (1 - level))`) is wrong in binary floating point at the project's own default of 0.80 —
  `4.000000000000001` rounds to 5 — so it is solved by the exact condition instead.

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

- **A rejected request was echoed back at its own size.** Every string field on the web models is bounded —
  `variant` at 8192, `spacer` at 512, `intent` and `cell_context` at 128 — and none of those bounds constrained
  the *response*. FastAPI's default validation error carries the offending `input` verbatim, so a 100 KB value
  sent to a field bounded at 128 characters came back as a 100 KB error, on every field:

      variant (bounded 8192)      HTTP 422  resp=100152B
      intent (bounded 128)        HTTP 422  resp=100149B
      cell_context (bounded 128)  HTTP 422  resp=100155B
      spacer (bounded 512)        HTTP 422  resp=100149B

  The bounds say what is *accepted*; the rejection is what carries the value, so a field-level fix does not
  help — bounding `intent` (the one string field that was unbounded) changed the response by 3 bytes. A
  validation-error handler now trims the echoed input, turning those 100 KB responses into ~360 bytes, while
  keeping `loc`, `msg` and `type` — what makes a 422 actionable — and echoing short values unchanged so a
  caller still sees their own typo. Being on the handler, it covers every field on every model, including ones
  not written yet.

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
