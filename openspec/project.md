# AlleleForge — Project Context

Context for anyone (human or agent) reading or writing OpenSpec specs in this repo.

## What this is

AlleleForge is a variant-driven, multi-modality, uncertainty-aware CRISPR guide &
edit design framework. You give it a sequence variant; it returns a ranked,
uncertainty-annotated set of candidate guide designs across SpCas9, base-editor, and
prime-editor chemistries, each with a population- and haplotype-aware off-target
profile.

**Research and educational use only.** It produces explicitly uncertain *predictions*.
It is not a medical device, contains no wet-lab protocols, and every off-target
nomination is computational and must be experimentally validated.

## The value proposition, honestly

The differentiated, trustworthy-today capability is **population/haplotype-aware
off-target nomination with honest uncertainty** — deterministic sequence matching plus
CFD/MIT scoring, no ML weights required. The efficiency/outcome predictors ship a
**weight-free heuristic baseline by default**; four real published models (Rule Set 3,
PRIDICT2.0, BE-DICT, Lindel) are wired as opt-in, license-gated, parity-verified paths.
Specs must preserve this honesty: never let a heuristic masquerade as a trained model.

## Tech stack

- **Language**: Python ≥ 3.11, `mypy --strict` clean, `ruff` (E,F,I,UP,B,D; google
  docstrings), line length 100.
- **Core deps** (deliberately light): `pydantic>=2.6`, `pydantic-settings`, `pyyaml`.
- **Optional extras**, pulled in per feature: `core` (polars/pyarrow/numpy), `genome`
  (pyfaidx/pysam/cyvcf2/mappy/pyliftover), `variant` (hgvs), `cli` (typer), `ml`
  (torch/transformers/lightning/sklearn), `cas9-rs3` (lightgbm/sglearn — the real
  Rule Set 3 path), `web` (fastapi/uvicorn), `docs` (mkdocs).
- **Performance**: optional Rust kernels via PyO3/maturin (`aforge_native`), each with a
  pure-Python fallback that must match it to the byte.
- **CLI**: `aforge` (Typer). **Web**: FastAPI. **Library is the source of truth**; CLI
  and web are thin shells with no business logic.
- **Tests**: pytest + hypothesis; coverage gate 85% (currently ~98%). Markers:
  `real_weights` (opt-in, downloads weights, skipped in CI), `native` (needs the
  compiled extension), `live_integration` (hits a live external service).

## Non-negotiable design principles (from SPEC.md §3)

1. **Variant-first.** The canonical journey starts from a variant, not a guide.
2. **Honest uncertainty.** No scorer returns a bare float. Every numeric prediction
   ships with a calibrated interval, a method tag, a calibrated flag, and an OOD flag.
3. **Population-aware by default.** Off-target search covers population variation and
   stratifies by ancestry; a minor allele can create a de novo PAM a reference-only
   scan misses.
4. **Wrap, don't rebuild.** Integrate the best existing tools behind one typed
   interface; add new ML only at genuine coverage gaps.
5. **Reproducible to the byte.** Pinned environments, versioned datasets, deterministic
   seeds, content-hashed checkpoints. Every top-level result embeds a `Provenance`
   block and must be re-derivable from it.
6. **Three audiences, one core.** Library is truth; CLI and web are thin shells.
7. **Typed and tested.** `mypy --strict`, `ruff`, property-based tests on core logic.
8. **Cite everything.** Every dataset, model, and scoring function carries a citation
   and a version, in code and in output provenance.

## Conventions specs must respect

- **CI stays weight-free.** Real trained models are opt-in behind the model-zoo gate and
  the `real_weights` marker; the library never hard-depends on a heavy/ML stack.
- **License/consent gate.** No non-redistributable artifact is bundled; the registry
  records each license and fetches at runtime with user consent + checksum verification.
- **Determinism.** Given the same inputs, seed, and versions, outputs are byte-stable.
- **Coordinates.** Be explicit about 0- vs 1-based and half-open conventions in every
  requirement that touches genomic position.
- **Before writing a local version of something the codebase already does, read the
  existing one.** This has now bitten three times, always the same way: a new, more
  central implementation re-broke a problem an older corner had already solved *and
  documented*.
  - `EditFrame` mapped a span's start and end boundaries with one function;
    `offtarget/_search.py`'s `_alt_coordinate_lift` had long since split its lift into
    `lo`/`hi` maps, with a docstring saying why. The single map mis-placed any span
    starting at a pure deletion.
  - `design_prime`'s in-run off-target cache keyed on the spacers alone;
    `offtarget/cache.py`'s `search_signature` already keyed on the on-target locus too,
    with a docstring warning that omitting it means one guide is "served the other's
    report, silently either counting the self-match or hiding a perfect-score site".
  - `_overlay_allele` was taught to handle a length-changing allele while
    `_cut_outcome`, one function over, kept the restriction it had just lost.

  The practical rule: when you add a coordinate map, a cache key, or an allele
  overlay, grep for the other ones first. The older implementation has usually already
  paid for the lesson, and its docstring is where the lesson is written down.

- **Adding a second reader to an `Iterable` parameter is an interface change.** The
  signature does not move, but `Iterable` is a promise the caller may keep with a
  generator, and every consumer after the first breaks it. R128: a coverage count added
  beside the existing enumeration silently consumed the caller's patient VCF, so the
  count reported the data was used while the personalization got an exhausted iterator.
  Materialize at the top of the function — and if a sibling argument already is, that is
  the convention telling you why.

- **A label about a scan costs per call; a scan costs per genome.** `search()` runs once
  per *candidate* (a prime menu has hundreds), so anything O(dataset) added inside it for
  reporting purposes is O(dataset x candidates) in production and invisible in tests,
  where every fixture is tiny. Two such regressions shipped before being measured (R126:
  23 s and 19% of a search). Before adding an explanation to a function, ask how often
  the function runs, and measure at the size of the real input.

- **When deleting an "unreachable" branch, ask whose invariant makes it unreachable.**
  A mutation run showing "no test can distinguish this" proves the branch is unreachable
  *given current behaviour*, which is only a guarantee when the behaviour is ours. In
  R125 the guarantee was `pyfaidx`'s `sequence_always_upper=True` — a dependency
  default — and deleting the defensive arm would have made a repeat-masked genome
  report as entirely unsearchable if that default ever changed. Defensive code is dead
  when the invariant is local, and load-bearing when it is someone else's.

- **Never chain `git commit --amend` behind `||` in a compound shell command.** A
  `git commit --amend ... || git add -A && git commit ...` fallback ran the *amend*,
  silently rewriting an already-pushed commit with the fallback's placeholder message
  (R117). Recovering needed `git reset --soft <pushed sha>` and a fresh commit; a
  force-push over shared history was the alternative and is not acceptable. Write the
  commit as one plain `git commit -F -`.

- **After restoring a mutated source file, clear `__pycache__`.** A restore whose
  mtime does not advance past the compiled bytecode leaves Python running the *mutant*
  while `inspect.getsource` shows the correct file — so the source reads right, the
  AST parses right, and the behaviour is still wrong. It cost a full CI cycle and a
  false hunt for a logic bug in R99. `find src -name __pycache__ -type d -exec rm -rf
  {} +` after every mutation loop.

- **Never `git checkout <file>` to undo a local mutation test.** It reverts the whole
  file to HEAD, taking every deliberate edit in the round with it. Copy the file aside
  (`cp f /tmp/f.bak`) before mutating and restore from the copy — which is what the
  source-code mutation checks already do; the prose ones drifted from that habit and
  cost a round's README edits. **This has now happened twice** (R96, R153): the second
  time it silently reverted a renderer edit made minutes earlier, and the only reason
  it was caught is that the full suite ran afterwards and one test that had just passed
  in isolation failed. `cp` before *every* mutation, without exception — and when a
  test passes alone and fails in the full run right after a mutation loop, suspect the
  restore before suspecting the test.

- **Never reconstruct a shared model field by field.** Adding a field to a pydantic
  model is only half the change: every place that rebuilds one by listing its fields
  silently resets whatever it forgot to that field's *default*, which is worse than
  leaving it blank — a report that says `cfd_threshold=0.20` asserts a scan that did
  not happen. Use `model_copy(update={...})`, naming only the fields that genuinely
  differ. `_merge_offtarget` lost three fields this way across three rounds before the
  mechanism itself was replaced. So: after adding a field to a model, grep for the
  model's other constructors; and when writing a merge, prefer copy-and-update. A test
  that iterates `Model.model_fields` instead of naming fields covers the fields that do
  not exist yet.

- **When two numbers are presented together, check they range over the same thing.**
  Each can be individually correct and documented while their juxtaposition is a lie,
  and no test of either one alone will catch it. R134: a cohort's `total` counted what
  the run processed and `skipped` counted the *manifest file*, so a two-item request
  reported `total: 0, skipped: 5`. R139: the benchmark's reproducibility digest covered
  `n_test` and not `n_out_of_distribution` — a denominator inside the integrity envelope
  and a numerator outside it — so a model that disclaimed nine predictions in ten
  compared as "the same scientific result" as one that stood behind all ten. The same
  question applies to a ratio's parts split across *any* boundary: signed/unsigned,
  scientific/volatile, shown/hidden.

- **An aggregate can be a claim even when it is not a number.** R135: the leaderboard
  labelled every row with its split version and marked synthetic corpora, and still
  ranked a 0.91 on the synthetic fixture as **#1** above a 0.42 on a real corpus. Every
  cell was honest; the rank column was the assertion, and annotating the rows does not
  retract it. When a fix is "we now show X", ask what the surrounding presentation still
  asserts on its own.

- **For an opt-in check, the audit question is "who opted in", not "is it correct".**
  A safety mechanism with a flag has two implementations — the code, and the set of call
  sites that pass the flag. R142: the disk cache's integrity gate (checksum sidecar,
  fail-closed read, careful publish ordering) is genuinely well built, and `verify=True`
  appeared only in its own tests, so none of it ever ran in the product. Enumerate the
  call sites. The related tell, which has now found something in several rounds: an
  exported helper for a boundary with **zero non-test callers** means the boundary is not
  being crossed (R136 `to_one_based`, R137 `Liftover`).

- **A guard in a convenience wrapper is not a guard on the documented path.** R143:
  `serve()` refuses a non-loopback bind without an API token, and both the deployment
  guide and the Dockerfile run `uvicorn …app:app`, which binds the module-level app and
  never calls it — while `create_app` did not read `ALLELEFORGE_API_TOKEN` either. An
  operator who published the port and set the variable got a fully open API. After
  writing a guard, run what the docs tell people to run.

- **A duplicated exception is a duplicated `except`.** R141: `ChecksumError` was defined
  in three modules and `ConsentError` in four, each exported under that name from its
  public package. `from alleleforge.genome import ChecksumError` then caught one third of
  the artifact-gate surface and the rest escaped as an unrelated-looking `RuntimeError` —
  a correct-looking handler that silently declines to run, with no symptom until it
  matters. For any exception name defined more than once, confirm the copies are
  genuinely different failures.

- **An audit that returns implausible results has two suspects, and one of them is the
  audit.** R138 built a check comparing documented `--flags` against the CLI, got obvious
  false positives, and recorded it as "inconclusive, not a clean bill" without finding
  the cause. Six rounds later the same question came up and the tool was still broken —
  a `TyperGroup` is not an `isinstance` of the `click.Group` visible here, so the walk
  found no subcommands (R144). A check abandoned as untrustworthy is a bug with an owner.
  Fix it or delete it; "inconclusive" makes the next person pay the same cost.

- **Audit the artifacts the audit produces.** Every round edits the changelog, the round
  log and the specs, and those edits get exactly the review that unreviewed work gets.
  R145: `[Unreleased]` had grown **77** change-type headings because each round prepended
  its own instead of merging. R146: the round log ran ascending for 134 rounds and then
  *descending* for eleven, because those rounds prepended their entries — and two cited
  round numbers had no entry at all. Both were invisible in any individual diff and
  obvious in one `grep`. Related: **"missing entry" and "skipped number" look identical
  from the gap.** A third apparent gap in that log was a skipped *number* whose work was
  logged under its neighbour; reconstructing an entry there would have been plausible,
  sourced from a real commit, and false. Check what the neighbours already say before
  writing anything into a hole.

## Existing planning docs (background, not OpenSpec)

`SPEC.md` (v1 build phases), `SPEC_V2.md` (R0–R6 roadmap), and `specs/*.md` (model-
integration and distribution planning) predate this OpenSpec directory. They are
historical/roadmap context. The authoritative capability contracts now live in
`openspec/specs/`; proposed changes live in `openspec/changes/`.
