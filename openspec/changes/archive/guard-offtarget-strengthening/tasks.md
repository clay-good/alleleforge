# Tasks

## 1. Score-based strengthening

- [x] In `offtarget/population.py` and `offtarget/haplotype.py`, replace the
  `h.edits < prior` create/strengthen gate with "created, or specificity score strictly
  greater than the best reference hit at the same placement," comparing on the scored
  value (CFD) rather than edit count.
- [x] Keep the causal-allele / ancestry attribution on the newly-retained sites.
- [x] Test: a variant that flips `NAG`→`NGG` with the protospacer untouched nominates the
  strengthened site with its ancestry annotation; a reference-only scan returns nothing.

## 2. Full-set genome-wide aggregate

- [x] In `types/offtarget.py`, aggregate `specificity_score` over all nominated in-budget
  sites (carry the sub-threshold tail into the sum), or document it as threshold-only and
  rename/annotate it so it is not read as the CRISPOR/Hsu aggregate.
- [x] Ensure the engine retains (or can supply) the sub-threshold sites the aggregate needs.
- [x] Test: two guides with identical top hits but different sub-threshold tails get
  different specificity scores.

## 3. CFD length guard

- [x] In `offtarget/scoring.py::cfd_score`, require a 20-nt spacer/protospacer; on any other
  length, raise (or return CFD as inapplicable) rather than scoring in the wrong register.
- [x] Reflect an inapplicable-CFD outcome in the recorded matrix identity / report so a
  non-20-nt score is never labeled `doench-2016-cfd`.
- [x] Test: a 19-nt and a 21-nt spacer are rejected/marked inapplicable, not silently zeroed.

## 4. Frequency-aware aggregate

- [x] Add a frequency-weighted expected-burden aggregate to the off-target report,
  weighting each non-reference site by its carrying-population frequency, alongside the
  existing frequency-blind worst-case.
- [x] Surface it in the report so a reader can distinguish a MAF-floor from a universal hit.
- [x] Test: a MAF-0.001 off-target and a universal one produce different expected burdens.

## 5. Regenerate goldens

- [x] Regenerate any off-target goldens whose specificity numbers shift.
