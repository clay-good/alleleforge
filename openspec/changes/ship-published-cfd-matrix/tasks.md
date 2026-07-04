# Tasks

## 1. Vendor and default the published matrix
- [ ] 1.1 Add the Doench 2016 CFD mismatch matrix as a vendored data file with its
      citation and license recorded in the registry.
- [ ] 1.2 Make it the default `mismatch_weights` source; keep the approximation available
      behind an explicit, labeled option.
- [ ] 1.3 Test: default CFD reproduces published example scores within tolerance.

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
- [x] 4.2 `make ci` green.
