# Release & distribution runbook

The executable checklist for shipping AlleleForge to the scientific community. The
*why* and channel rationale live in [`specs/distribution-plan.md`](specs/distribution-plan.md);
this is the *how*, in order. Preconditions below are now met (two real models are
wired + validated: trained Rule Set 3 and PRIDICT2.0).

## 0. Pre-flight (once per release)

- [ ] Bump the version in [`src/alleleforge/_version.py`](src/alleleforge/_version.py)
      from `0.1.0.dev0` to the release version (e.g. `0.1.0`), **and the matching
      `version:` in [`CITATION.cff`](CITATION.cff)** — a stale one makes every citation
      of the software name a version that was never released. The Rust crate's
      `version()` and `CITATION.cff`'s are both asserted equal in the test suite, so
      `make ci` fails if either is missed.
- [ ] `make ci` green (lint, type, test, docs, examples, reproduce, distribution,
      and the isolated wheel SBOM). Native: `make native`. Container: `make image`;
      ordinary CI also builds both published architectures without pushing them,
      then boots the loadable amd64 image and requires `/api/health` to answer.
- [ ] `python scripts/release_readiness.py` — the v1.0 criteria from `SPEC_V2.md` (R6),
      measured rather than recalled. It exits non-zero while any is open; for a `0.x`
      release that is expected, and the point is to read *which* are open and confirm
      each is still blocked outside the repository rather than forgotten.
- [ ] CHANGELOG updated.
- [ ] README claims are honest (heuristic vs trained scorers; see the prime/cas9
      sections). Confirm no overclaim of "wraps PRIDICT2/BE-Hive" beyond what's wired.

## 1. Host the trained Rule Set 3 booster (unblocks `--trained-efficiency`) — ✅ DONE

The `rule-set-3` card pins a `checkpoint_sha256` and a `source_url` release asset.

- [x] `RuleSet3.txt` produced via [`scripts/export_rs3_booster.py`](scripts/export_rs3_booster.py);
      sha256 confirmed == the card's `checkpoint_sha256` (`464a5a08…917e`).
- [x] Uploaded as the [`rs3-booster-v1`](https://github.com/clay-good/alleleforge/releases/tag/rs3-booster-v1)
      release asset (matches the card's `source_url`). Verified end to end: the
      model-zoo gate downloads it, the checksum verifies, and the scorer reproduces
      upstream `rs3` exactly. `pip install "alleleforge[cas9-rs3]"` +
      `aforge design --trained-efficiency` now works for any user.
- [ ] (Re-run only if the model is ever re-derived and the hash changes.)

## 2. Tag + GitHub release (→ Zenodo DOI)

- [ ] Enable the GitHub–Zenodo integration for the repo (one-time). `.zenodo.json`
      is already present.
- [ ] `git tag vX.Y.Z && git push origin vX.Y.Z`; publish a GitHub Release. Zenodo
      mints a DOI automatically. Add the DOI badge to the README.

## 3. PyPI (table stakes)

- [ ] `python scripts/check_distribution.py --outdir dist` then `twine upload dist/*`.
      - The wheel builds and is sound: verified 2026-09-07 that it carries `py.typed`,
        17 model cards, the benchmark splits, the served frontend and the CFD matrix,
        and that the package imports and resolves all of them from the wheel's own
        contents rather than the source tree.
      - The audit builds the wheel from the sdist, runs `twine check` over both, and
        compares every non-Python runtime resource in `src/alleleforge` with the wheel.
        It passed on 2026-09-28 with build 1.6.1, Hatchling 1.32.4 and twine 7.0.0.
        Twine 6.2.0 rejects current Metadata-Version 2.5 artifacts, so the release
        toolchain requires twine 7 or newer and both CI and the tag workflow run the
        same audit before publication.
      - `make sbom` installs that validated wheel into a temporary environment with
        no installer or build tools, emits a reproducible CycloneDX document, and
        checks the root name/version and dependency graph. The release job downloads
        and inventories the same `dist` artifact that the PyPI job publishes. Both
        PyPI and GHCR publication wait for that audit; OIDC, package-write, and
        release-write authority are scoped only to the job that uses each one.
      - Every external action in CI and release is pinned to a full commit SHA. The
        adjacent version comment lets Dependabot propose reviewed SHA updates without
        returning the workflow to a mutable tag.
      - Both Docker stages pin `python:3.12-slim` to one multi-architecture manifest
        digest. Dependabot's Docker ecosystem proposes explicit digest updates. The
        runtime server runs as fixed unprivileged UID/GID `10001:10001`, and its
        built-in health check calls the public `/api/health` liveness contract. The
        default Compose service uses a read-only root filesystem, drops every Linux
        capability, enables `no-new-privileges`, and leaves only `/tmp` and `/cache`
        writable.

## 4. Bioconda (the channel bench scientists use)

- [ ] Take the real sdist sha256 from the PyPI release; fill it into
      [`conda/meta.yaml`](conda/meta.yaml) (`source.sha256`) and set the version.
- [ ] Open a PR adding the recipe to
      [bioconda/bioconda-recipes](https://github.com/bioconda/bioconda-recipes)
      (`recipes/alleleforge/meta.yaml`). On merge: `conda install -c bioconda alleleforge`
      + an automatic BioContainer.

## 5. Discovery registries

- [ ] **bio.tools** — create an entry (biotoolsSchema) at https://bio.tools (gives an
      RRID). Fields mirror `.zenodo.json` + the README.
- [ ] **awesome-CRISPR** — open a PR adding AlleleForge to
      https://github.com/davidliwei/awesome-CRISPR (lead with the population/
      haplotype-aware off-target engine — the most differentiated, fully-real feature).

## 6. Credibility (after 1–5 exist to point at)

- [ ] **bioRxiv preprint** — finalize [`docs/paper/preprint.md`](docs/paper/preprint.md);
      fill any remaining `[pending R1]` numbers with real ones where models are wired.
- [ ] **JOSS** — submit once the repo has been public 6+ months with steady activity
      (start that clock now); frame the contribution as the *framework* (uncertainty
      contract, population-aware off-target, benchmark harness), not a model wrapper.

## 7. Announce (last)

- [ ] Biostars, r/bioinformatics, SEQanswers, Bluesky/Mastodon bioinformatics. Lead
      with what is unambiguously real today.
