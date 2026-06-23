# Release & distribution runbook

The executable checklist for shipping AlleleForge to the scientific community. The
*why* and channel rationale live in [`specs/distribution-plan.md`](specs/distribution-plan.md);
this is the *how*, in order. Preconditions below are now met (two real models are
wired + validated: trained Rule Set 3 and PRIDICT2.0).

## 0. Pre-flight (once per release)

- [ ] Bump the version in [`src/alleleforge/_version.py`](src/alleleforge/_version.py)
      from `0.1.0.dev0` to the release version (e.g. `0.1.0`). The Rust crate's
      `version()` is asserted equal in the test suite.
- [ ] `make ci` green (lint, type, test, docs, reproduce). Native: `make native`.
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

- [ ] `python -m build` then `twine upload dist/*` (already passes `twine check`).

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
