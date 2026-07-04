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

## Impact

- Specs: `offtarget-scoring` (MODIFIED default matrix + score clamping; ADDED matrix
  provenance), `reporting` (ADDED scorer/matrix provenance surfaced in the report).
- Code: `offtarget/scoring.py`, the report builder/renderers, and a vendored matrix data
  file with its citation in the model/dataset registry.
- Tests: default CFD reproduces published example scores; an out-of-range weight is
  clamped/flagged at scoring time; the report names the matrix used. Off-target scores
  will change for existing runs — regenerate goldens and note the change in the CHANGELOG.
