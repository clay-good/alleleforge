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

- **Never `git checkout <file>` to undo a local mutation test.** It reverts the whole
  file to HEAD, taking every deliberate edit in the round with it. Copy the file aside
  (`cp f /tmp/f.bak`) before mutating and restore from the copy — which is what the
  source-code mutation checks already do; the prose ones drifted from that habit and
  cost a round's README edits.

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

## Existing planning docs (background, not OpenSpec)

`SPEC.md` (v1 build phases), `SPEC_V2.md` (R0–R6 roadmap), and `specs/*.md` (model-
integration and distribution planning) predate this OpenSpec directory. They are
historical/roadmap context. The authoritative capability contracts now live in
`openspec/specs/`; proposed changes live in `openspec/changes/`.
