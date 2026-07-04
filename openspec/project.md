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

## Existing planning docs (background, not OpenSpec)

`SPEC.md` (v1 build phases), `SPEC_V2.md` (R0–R6 roadmap), and `specs/*.md` (model-
integration and distribution planning) predate this OpenSpec directory. They are
historical/roadmap context. The authoritative capability contracts now live in
`openspec/specs/`; proposed changes live in `openspec/changes/`.
