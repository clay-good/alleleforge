# Contributing to AlleleForge

Thank you for your interest in AlleleForge. This document explains how to set up a development
environment, the quality gates every change must pass, and the conventions we follow.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md)
(Contributor Covenant 2.1).

## Project philosophy

AlleleForge is built phase by phase against [`SPEC.md`](SPEC.md), the authoritative build contract.
Before proposing a change, read the relevant phase. Two principles override personal preference:

- **Honest uncertainty.** No scorer returns a bare float; every numeric prediction carries an interval,
  the method behind it, and a `calibrated` flag saying whether that interval was fitted against held-out
  coverage. The weight-free defaults are heuristics and report `calibrated=False`; asserting otherwise is
  the one thing this project treats as worse than a wide interval. Do not add code paths that emit
  point estimates without an uncertainty contract.
- **Population-aware by default — as behaviour, not as a shipped dataset.** Off-target analysis is
  ancestry-stratified; a single global number hides exactly the disparities we exist to surface. Given a
  population source the scan uses it without being asked again; nothing of gnomAD ships, so without
  `--gnomad` (or a haplotype panel, or a patient VCF) a scan is **reference-only** and must say so. An
  empty ancestry breakdown means *not measured*, never *clean*.

## Development setup

```bash
git clone https://github.com/clay-good/alleleforge
cd alleleforge

# Python toolchain (3.11 or 3.12)
python -m venv .venv && source .venv/bin/activate
make install   # editable install with the dev, cli, web and genome-light extras

# Optional native acceleration (Rust toolchain required)
make native    # builds the wheel, installs it, runs the suite against it
```

`make install` rather than a hand-written `pip install -e ".[dev]"`: `dev` alone leaves
out the FASTA reader, the web server and the tabular stack, so the gate you are about to
run cannot pass. It is the same extras set CI installs, kept in one place — and that is
now checked rather than asserted: `core` was missing from both for a long time, and
`pytest` could not *collect* the suite without it, so no test ran at all
([`test_the_gate_can_run_from_the_documented_install.py`](tests/test_the_gate_can_run_from_the_documented_install.py)).
The `dev` extra currently constrains NumPy below 2.5 because mypy checks the supported
Python 3.11 type contract and NumPy 2.5's stubs require Python 3.12 syntax. Runtime extras
remain open to newer NumPy; this is a development-tool compatibility bound only.

There is no conda *environment* file. `conda/meta.yaml` is a bioconda-style packaging
recipe — it describes how to publish the released package, not how to set up a checkout —
and this section used to point at an `environment.yml` that has never existed.

## Quality gates

Every change must pass the same gates CI enforces. Run them locally before opening a PR:

```bash
ruff check src tests            # lint, import order, public-API docstrings
ruff format --check src tests   # formatting
mypy src                        # strict type-check (no untyped defs)
pytest                          # tests + ≥85% coverage gate on the core
make distribution              # sdist/wheel metadata and packaged-resource audit
make sbom                      # exact-wheel runtime-closure SBOM audit
make image                     # build + import-smoke the deployment image, when Docker is available
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
- Two markers are **opt-in**: the root `conftest.py` skips them unless their variable is set, so a
  clean checkout never downloads weights or calls an external service by accident.

  | Marker | Run them with | What they reach |
  |---|---|---|
  | `@pytest.mark.real_weights` | `ALLELEFORGE_REAL_WEIGHTS=1` | real model weights (a gated download) |
  | `@pytest.mark.live_integration` | `ALLELEFORGE_LIVE_INTEGRATION=1` | a live external service (VEP / UTA / Cas-OFFinder) |

- Tests needing the compiled extension are marked `@pytest.mark.native`. It is **not** opt-in here — the
  root conftest must not skip it, or the job that runs it becomes a no-op.
- That job (`make native`) builds the crate and runs the **whole** suite against it, not only the marked
  tests. With the crate installed the library takes its native branches everywhere, and that is the
  configuration the docs recommend for real work, while every other job runs the pure-Python one.

### Mutation testing

A green suite says the tests pass, not that they would notice a change. `scripts/mutate.py`
answers the second question: it edits one thing in a source file, runs a chosen slice of the
suite, restores the file, and records whether anything failed. A *survivor* — a mutation no
test objected to — is a claim nothing is checking.

```bash
python scripts/mutate.py --target src/alleleforge/x.py --tests "tests/x" --mode conj
python scripts/mutate.py --target src/alleleforge/x.py --tests x --mode conj --only 0   # list sites
python scripts/mutate.py --target src/alleleforge/x.py --tests tests --mode conj --index 3,7
```

Each `--mode` asks a different question — `ops` and `const` whether a computation or a
threshold is pinned, `conj` whether a condition's other arm is tested, `side` whether
anything observes that a statement ran at all, `raise` whether anything observes that a
refusal *fires*, `isinst` which side of a type guard a fixture supplies, `pair` whether
the two ends of a span are interchangeable, and `dflt` whether a boolean default in a
signature is a posture anyone has checked. The script's own docstring says what each
finds and why.

All eight modes have now been run repo-wide and each is exhausted, so a new one needs a
new hypothesis rather than a longer list. `raise`'s first sweep reported 370/370 killed
and that number was an artifact — the driver quoted a shell glob, pytest exited 4 without
running anything, and the harness scored every non-zero exit as a kill. R689 has the full
account and added the two controls that make that lie untellable: the chosen list is run
unmutated, and so is an unmutated `ast.unparse` rewrite. The real 46-module sweep (R691)
then found eleven untested refusals.

**Both controls earn their cost, and the second one earns it twice.** Three modules
failed the no-op control, each because a test reads the module's own source text, so
`ast.unparse` reformatting kills every mutant and the module scores a meaningless 100%.
Narrowing the list past the offending test did not reveal clean modules — it revealed four
real defects the false score had been hiding, including the sharpest finding of the round.
**An unmeasurable module and a perfect one are indistinguishable in the log.** When a run
reports `UNMEASURABLE`, narrowing the list and re-running is not bookkeeping; it is where
the findings were.

Three things to know before trusting a result, each of which has produced a confidently
wrong answer here:

- **Run your chosen test list green first.** A failing test makes the run exit non-zero
  whatever the mutation did, so every mutant reports "killed".
- **A module's own test directory is a filter, not evidence.** Survivors against it are
  routinely 50–100% phantom; re-run each against the whole suite before reading it as a
  gap. Confirm with `--index`.
- **Check what is actually installed before calling a survivor untested.** The venv
  lives in the *main* checkout, not in a worktree, so a probe that falls back to the
  system interpreter reports the opposite of the truth. In R691 one such mistake
  misclassified ten survivors; `polars`, `requests`, `typer` and `aforge_native` are
  present here and `numpy` and `torch` are not, which is what decides whether an optional
  dependency's refusal is reachable at all.
- **An exit-code assertion can be satisfied by the framework refusing to run the
  command.** `ExitCode.USAGE` is 2, which is also Typer's own usage-error code, so a
  malformed `runner.invoke` — a flag that does not exist, a positional passed as an
  option — produces exit 2 and a passing test that exercised nothing. Assert on the
  message as well as the code, or the CLI's commonest refusal is the one where this is
  invisible.
- **A survivor is one of three things**: reachable and untested (write the test),
  unobservable (prove it by running both branches over an exhaustive space, and record
  it), or unexecutable here (an optional dependency, a network path). Only the first is
  work, and conflating them produces a backlog nobody can close.

Never commit while a sweep may be live, and check `git diff --stat src/` afterwards: the
harness restores the file it mutated, but a killed process can leave it rewritten.
`tests/test_the_mutation_harness_applies_what_it_reports.py` guards the harness's own
index mapping — the property every conclusion above rests on.

### The documentation site

`docs/assets/css/palette.css` is the only stylesheet this project authors, and everything
in it is an accessibility override of the `mkdocs-material` theme, not styling: a WCAG AA
contrast fix and an 11px floor for inline code. Both are measured, and
`tests/test_the_docs_site_text_clears_a_legibility_floor.py` pins them.

Two things to know before changing it:

- **`mkdocs build --strict` does not measure the rendered page.** It checks links and
  references. Every accessibility defect found on this site so far was only visible by
  loading the built pages and reading computed styles in a browser; no gate does that, so
  the guards pin the *inputs* the fix reasons about instead.
- **A failure of the theme-bound half may mean the override is now redundant.** The theme
  is depended on as `>=9.5` and may raise its own sizes. The test says so when it fails:
  remove the override rather than keep it as decoration. That half skips wherever the
  `docs` extra is not installed, which is every job but `gate`.

Relative units compound, so check a size in the smallest container that can hold it — a
`.85em` that is comfortable in prose is 10.88px inside a table the theme has already
reduced.

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

## Security reports

Do not open a public issue for a vulnerability. See [`SECURITY.md`](SECURITY.md) —
reports go through a private advisory, which is visible only to the maintainers.
