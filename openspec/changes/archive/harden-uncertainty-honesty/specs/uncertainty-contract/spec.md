# uncertainty-contract (delta)

## MODIFIED Requirements

### Requirement: Honesty flags carry defined meaning

`method`, `calibrated`, and `in_distribution` SHALL each carry a defined, auditable
meaning, and the flags SHALL be tamper-resistant, not honor-system:

- `calibrated = True` SHALL be settable only by a fitted calibrator (the conformal or
  isotonic path). A `Prediction` constructed directly by a scorer SHALL default to
  `calibrated = False`; a direct attempt to assert `calibrated = True` SHALL not be
  honored.
- A prediction produced without a real trained backbone (e.g. on the weight-free stub
  embedder) SHALL report `calibrated = False` and a heuristic-appropriate `method`, so a
  heuristic result is distinguishable from a trained one without reading provenance.
- `in_distribution = False` SHALL NOT coexist with `calibrated = True`.

`method` remains one of `ensemble`, `evidential`, `quantile`, `conformal`, `heuristic`,
`agreement`, `none`, stored verbatim in provenance.

#### Scenario: Scorer cannot self-declare calibration
- **WHEN** a scorer constructs a `Prediction` asserting `calibrated = True` without a
  fitted calibrator
- **THEN** the result reports `calibrated = False`

#### Scenario: Stub-backbone result is honest
- **WHEN** the default ensemble scorer runs on the weight-free stub embedder
- **THEN** the returned prediction reports `calibrated = False`

#### Scenario: OOD cannot be calibrated
- **WHEN** a prediction has `in_distribution = False`
- **THEN** it also has `calibrated = False`

## ADDED Requirements

### Requirement: Out-of-distribution predictions widen, never narrow

When a prediction is flagged `in_distribution = False`, its interval SHALL be at least as
wide as the in-distribution interval it would otherwise have produced (widened, or its
`method` demoted), so an out-of-distribution input can never present a narrow, confident
interval even when model members happen to agree.

#### Scenario: Agreeing members on an OOD input
- **WHEN** ensemble members agree closely but the input is out of distribution
- **THEN** the returned interval is widened rather than narrow, and `calibrated = False`

### Requirement: Interval repair is recorded, not silent

When packaging a value and interval requires widening the interval to contain the point
estimate (a signal the underlying head is inconsistent), the system SHALL record a note
rather than silently repairing it, so a broken head is surfaced for audit.

#### Scenario: Point outside its own interval
- **WHEN** a scorer's point estimate falls outside its predicted interval
- **THEN** the interval is widened to contain it AND a note recording the repair is
  attached for audit
