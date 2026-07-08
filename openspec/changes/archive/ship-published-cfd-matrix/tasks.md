# Tasks

## 1. Vendor and default the published matrix
- [x] 1.1 Add the Doench 2016 CFD mismatch matrix as a vendored data file with its
      citation and license recorded in the registry. *(Vendored at
      `offtarget/cfd_matrix.json` — the 240 mismatch weights + 16 PAM weights in the native
      Doench key form, with a `_provenance` block; the file was sourced from CRISPOR and
      **cross-verified byte-for-byte against CRISPRitz** (max abs diff 0.0), and the PAM
      weights match the previously-vetted published table. A pinned `doench-2016-cfd`
      `DatasetDescriptor` (citation + license + real sha256 of the shipped file) records it
      in the registry.)*
- [x] 1.2 Make it the default `mismatch_weights` source; keep the approximation available
      behind an explicit, labeled option. *(`CfdScorer()` now loads the published matrix by
      default via `published_cfd_mismatch_weights()` and labels its `matrix`
      `doench-2016-cfd`; the transparent seed-tolerance model is opt-in via
      `CfdScorer(approximate=True)`, labeled `doench-2016-seed-tolerance-approximation`.)*
- [x] 1.3 Test: default CFD reproduces published example scores within tolerance.
      *(`test_default_cfd_reproduces_published_example_scores` and
      `test_published_cfd_matrix_has_expected_anchor_values`; separately the conversion was
      fuzz-checked against the reference CFD calculator over 20k random pairs, max diff
      1.7e-18.)*

## 2. Clamp/validate scores at scoring time
- [x] 2.1 Validate/clamp each computed score into `[0, 1]` inside the scorer with a clear
      error/warning, before the `OffTargetSite` validator.
- [x] 2.2 Test: an injected out-of-range weight is caught at scoring time, not as a
      downstream abort.

## 3. Record matrix/scorer provenance
- [x] 3.1 Tag each score (or the report) with the scorer name and matrix identity.
- [x] 3.2 Surface the scorer + matrix in the off-target report render.
- [x] 3.3 Mark the Cas12a analog scorer's unvalidated status in output.

## 4. Reconcile
- [x] 4.1 Regenerate off-target and reproduce goldens; note the score change in CHANGELOG.
      *(Re-confirmed after defaulting the published matrix: the reproduce golden's only drift
      was the honest `score_matrix` label flipping to `doench-2016-cfd` — the acceptance
      scenario's single off-target is a perfect match, so no CFD *value* changed. Golden
      regenerated; CHANGELOG notes that real off-target runs with mismatched sites now return
      published-CFD numbers instead of the approximation.)*
- [x] 4.2 `make ci` green. *(ruff + mypy --strict clean, 1005 passed/5 skipped at 97.4%
      coverage, docs strict, reproduce matches the regenerated golden.)*
