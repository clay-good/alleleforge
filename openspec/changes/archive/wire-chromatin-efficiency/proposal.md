# Wire the ePRIDICT open-chromatin adjustment into the prime-editing design path

## Why

The prime-efficiency scorer implements an **ePRIDICT-style open-chromatin adjustment**:
`PridictScorer.score(pegrna, *, chromatin=(tracks, interval, track))` scales the efficiency
by the local ENCODE signal (`prime_efficiency.py:107-110`, open chromatin edits better). But
the adjustment is **unreachable through the design pipeline**: `design_prime` calls
`scorer.score(pegrna, cell_context=…)` with no `chromatin` argument (`design/prime.py:192`),
and the `PrimeEfficiencyScorer` Protocol does not even expose the parameter
(`design/prime.py:42`). So a real `af design` / `design_prime` run always produces the pure
pegRNA-geometry baseline, and the advertised chromatin-aware capability is dead code outside
a direct scorer call. No spec covers it — chromatin/ePRIDICT is absent from every spec file.

This is a capability the code already has, blocked only by a small integration seam. Wiring it
turns a documented-but-inert feature into a usable, honestly-labeled one — without touching the
scoring math (which Round 26 verified clean).

## What Changes

- **Expose `chromatin` on the `PrimeEfficiencyScorer` Protocol** so a conforming scorer can
  accept the ENCODE-tracks adjustment (`PridictScorer` already does; the trained adapters take
  `**kwargs`).
- **Thread ENCODE tracks through `design_prime`**: add optional `encode_tracks: EncodeTracks`
  and `chromatin_track: str`. When both are supplied, build
  `chromatin=(encode_tracks, pegrna.placement, chromatin_track)` per pegRNA and pass it to the
  scorer, so the efficiency reflects the edit locus's chromatin accessibility.
- **Keep it opt-in and honest**: absent tracks → the default is exactly the current geometry
  baseline (no behavior change for existing callers). The adjustment only **scales the point
  estimate**; it never flips the out-of-distribution flag, never fabricates calibration, and an
  uncovered locus (signal 0) is a **no-op**, never a penalty for missing data. A requested track
  name that the `EncodeTracks` object does not carry **fails closed** (raises), rather than
  silently applying no adjustment and misleading the caller into thinking chromatin was used.
- **Label it in the candidate rationale** when a chromatin adjustment was applied, so the
  researcher can see the efficiency was chromatin-adjusted rather than pure geometry.
- **Correct the docstrings** (`design_prime`, and the already-corrected `prime_efficiency`
  module docstring) to state the wired, opt-in behavior accurately.

## Impact

- Affected specs: `prime-editor-design` (a new requirement + scenarios for the opt-in,
  honesty-preserving chromatin adjustment).
- Affected code: `scoring/prime_efficiency.py` (unchanged math; the score method already
  accepts `chromatin`), `design/prime.py` (Protocol + `design_prime` params + wiring + rationale).
- Backward compatible: every existing caller that does not pass `encode_tracks` gets identical
  output. No new required argument, no dependency change (`EncodeTracks` is already in-tree).
