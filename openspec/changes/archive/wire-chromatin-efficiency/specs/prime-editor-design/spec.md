# prime-editor-design (delta)

## ADDED Requirements

### Requirement: Chromatin-aware efficiency is opt-in and honesty-preserving

`design_prime` SHALL support an optional **open-chromatin (ePRIDICT-style) efficiency
adjustment** driven by ENCODE tracks. When the caller supplies both an `EncodeTracks` source
and a track name, the design path SHALL score each pegRNA with the chromatin context of its
own edit locus (the pegRNA placement interval), so a variant in open chromatin is predicted
to edit more efficiently than one in closed chromatin. The `PrimeEfficiencyScorer` protocol
SHALL expose the `chromatin` parameter so the adjustment is reachable through the design path,
not only by calling a scorer directly.

The adjustment SHALL be opt-in and SHALL NOT weaken any honesty guarantee:

- When no tracks are supplied, the efficiency SHALL be the pure pegRNA-geometry baseline —
  byte-identical to the pre-wiring default, so no existing caller's output changes.
- The adjustment SHALL only scale the efficiency **point estimate**; it SHALL NOT flip the
  `in_distribution` flag or assert calibration the scorer has not earned. An out-of-distribution
  cell context SHALL remain out-of-distribution after a chromatin adjustment.
- A locus with **no track coverage** (signal 0) SHALL be a no-op (the unadjusted value), never a
  penalty for missing data.
- A requested track name that the `EncodeTracks` object does not carry SHALL **fail closed**
  (raise), rather than silently applying no adjustment and misleading the caller into believing
  the efficiency was chromatin-adjusted.
- A candidate whose efficiency was chromatin-adjusted SHALL record that fact in its rationale, so
  the researcher can distinguish a chromatin-adjusted efficiency from a pure-geometry one.

#### Scenario: Opt-in — no tracks leaves the baseline unchanged
- **WHEN** `design_prime` is called without `encode_tracks`
- **THEN** every candidate's efficiency is the pure pegRNA-geometry baseline, identical to the
  output before chromatin wiring existed

#### Scenario: Open chromatin raises the predicted efficiency
- **WHEN** `design_prime` is called with an `EncodeTracks` source and a track name, and the
  pegRNA's edit locus has positive accessibility signal
- **THEN** the candidate's efficiency point estimate is higher than the pure-geometry baseline,
  and its rationale records that the efficiency was chromatin-adjusted

#### Scenario: Chromatin adjustment does not launder an OOD prediction
- **WHEN** the cell context is out-of-distribution and a chromatin adjustment is applied
- **THEN** the efficiency prediction remains flagged `in_distribution = False`

#### Scenario: Uncovered locus is a no-op
- **WHEN** the requested track has no coverage over the pegRNA's edit locus
- **THEN** the efficiency equals the unadjusted geometry baseline (no penalty for missing signal)

#### Scenario: Unknown track fails closed
- **WHEN** the requested track name is not present in the supplied `EncodeTracks`
- **THEN** the design raises rather than silently returning an unadjusted efficiency labeled as
  chromatin-aware
