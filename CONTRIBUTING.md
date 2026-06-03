# Contributing to AlleleForge

Thank you for your interest in AlleleForge. This document explains how to set up a development
environment, the quality gates every change must pass, and the conventions we follow.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md)
(Contributor Covenant 2.1).

## Project philosophy

AlleleForge is built phase by phase against [`SPEC.md`](SPEC.md), the authoritative build contract.
Before proposing a change, read the relevant phase. Two principles override personal preference:

- **Honest uncertainty.** No scorer returns a bare float; every numeric prediction carries a calibrated
  interval. Do not add code paths that emit point estimates without an uncertainty contract.
- **Population-aware by default.** Off-target analysis is ancestry-stratified; a single global number hides
  exactly the disparities we exist to surface.

## Development setup

```bash
git clone https://github.com/clay-good/alleleforge
cd alleleforge

# Python toolchain (3.11 or 3.12)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Optional native acceleration (Rust toolchain required)
cd rust && maturin develop --release && cd ..
```

A conda environment is also provided:

```bash
conda env create -f environment.yml
conda activate alleleforge
```

## Quality gates

Every change must pass the same gates CI enforces. Run them locally before opening a PR:

```bash
ruff check src tests            # lint, import order, public-API docstrings
ruff format --check src tests   # formatting
mypy src                        # strict type-check (no untyped defs)
pytest                          # tests + ≥85% coverage gate on the core
cd rust && cargo test           # native crate
```

A change is "done" only when its deliverables exist, `ruff` and `mypy --strict` pass on the new code, and
its tests are green.

### Testing conventions

- Tests live under `tests/`, mirroring `src/alleleforge/`.
- Use **pytest** and, for invariants, **Hypothesis** property tests (reverse-complement is an involution,
  coordinate conversions round-trip, normalization is idempotent, intervals contain their point estimate…).
- Never download a real genome or multi-GB dataset in CI — ship small synthetic fixtures under
  `tests/**/fixtures/` (the `.gitignore` explicitly allows them).
- Tests needing real model weights are marked `@pytest.mark.real_weights` and are skipped in CI.
- Tests needing the compiled extension are marked `@pytest.mark.native`.

## Commit &amp; PR conventions

- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`, `refactor:`…). Scope by module where useful, e.g. `feat(offtarget): …`.
- Keep changes surgical: touch only what the change requires; do not reformat or "improve" adjacent code.
- Every changed line should trace to the PR's stated purpose.
- Update [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]` for any user-visible change.
- New datasets, models, or scoring functions must carry a literature citation and a version in code.

## Reporting issues

Open a GitHub issue with a minimal reproduction. For anything touching off-target safety, include the
reference build, the populations queried, and the exact spacer/PAM — ancestry context matters.

## License of contributions

AlleleForge is licensed under the [MIT License](LICENSE) — all code, schemas, benchmark, and any first-party
model weights. By contributing you agree your contributions are licensed under MIT.
