# Ship the published CFD matrix as the default

## Why

CFD is the primary off-target specificity score and the number bench scientists compare
against CRISPOR. Today the shipped default per-position mismatch weights are a
**transparent monotonic seed-tolerance approximation**, not the published Doench 2016
CFD matrix (`offtarget/scoring.py:83-101, 13-16`). The exact 400-value matrix is
injectable but off by default. So out-of-the-box CFD scores — and the 0.20 threshold
applied to them — are **not** the CFD numbers a reviewer expects, and nothing in the
output says which matrix produced a score. This is the single largest scientific-trust
gap in the part of the tool the project most wants people to trust.

Two related sharp edges: an injected weight `> 1.0` yields a score `> 1.0` that the
`OffTargetSite` validator then rejects with an abort (`scoring.py:141-147`,
`types/offtarget.py:80-81`) rather than being clamped/validated at scoring time; and the
Cas12a scorer is an explicitly-unvalidated analog (`scoring.py:186-215`).

## What Changes

- Vendor the **published Doench 2016 CFD mismatch matrix** (it is redistributable) and
  make it the default per-position weight source; keep the approximation available and
  clearly labeled for offline/deterministic-fallback use.
- Record **which matrix produced each score** and surface the scorer + matrix provenance
  in the off-target report, so a consumer can see whether they are reading published-CFD
  or approximation numbers.
- **Clamp/validate scores into `[0, 1]` inside the scorer** so a stray weight is caught
  at scoring time with a clear message, not as a downstream validation abort.
- Mark the Cas12a scorer's analog status in output so it is not mistaken for a validated
  risk signal.

## Status (partial)

Task 2 (clamp/validate scores at scoring time) has shipped: `cfd_score` /
`cas12a_cfd_score` now reject an out-of-range mismatch/PAM weight with a clear
scoring-time error naming the offending weight, instead of letting a stray value
produce a `> 1.0` score that aborts later in the `OffTargetSite` validator.

Task 3 (matrix/scorer provenance) has also shipped: `CfdScorer`/`Cas12aCfdScorer`
now expose a `matrix` identity, `OffTargetReport` records `scorer`/`score_matrix`,
the engine populates them, and the `aforge offtarget` output surfaces them — so a
consumer can see the scores came from the transparent approximation
(`doench-2016-seed-tolerance-approximation`), and the Cas12a analog carries an
explicit `unvalidated` label. Off-target and reproduce goldens were regenerated.

Task 1 (default the published matrix) has now **shipped**. The authentic Doench 2016
CFD matrix — distributed only as a binary pickle upstream — was sourced from CRISPOR
and **cross-verified byte-for-byte against a second independent tool, CRISPRitz**
(all 240 mismatch weights identical, max abs diff 0.0; the 16 PAM weights match the
previously-vetted published table), then vendored as `offtarget/cfd_matrix.json` with
a full `_provenance` block and a pinned `doench-2016-cfd` registry descriptor.
`CfdScorer()` now defaults to it (labeled `doench-2016-cfd`), with the transparent
approximation kept behind `CfdScorer(approximate=True)`. The conversion into the
scorer's key form was proven exact against the reference CFD calculator over 20k
random pairs (max diff 1.7e-18). Nothing was fabricated or approximated-then-labeled
"published" — the values are the authentic published matrix, independently
corroborated.

## Impact

- Specs: `offtarget-scoring` (MODIFIED default matrix + score clamping; ADDED matrix
  provenance), `reporting` (ADDED scorer/matrix provenance surfaced in the report).
- Code: `offtarget/scoring.py`, the report builder/renderers, and a vendored matrix data
  file with its citation in the model/dataset registry.
- Tests: default CFD reproduces published example scores; an out-of-range weight is
  clamped/flagged at scoring time; the report names the matrix used. Off-target scores
  will change for existing runs — regenerate goldens and note the change in the CHANGELOG.
