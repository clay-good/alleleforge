# Tasks — wire the ePRIDICT open-chromatin adjustment

1. **Expose `chromatin` on the Protocol** → verify: `PrimeEfficiencyScorer.score` declares
   `chromatin: tuple[EncodeTracks, GenomicInterval, str] | None = None`; mypy stays green with
   `PridictScorer` and the trained `_ModelZooAdapter` scorers.
2. **Thread tracks through `design_prime`** → verify: new `encode_tracks` / `chromatin_track`
   params; when both supplied, each pegRNA is scored with
   `chromatin=(encode_tracks, pegrna.placement, chromatin_track)`; when absent, the call is
   byte-identical to today (a regression test pins the no-tracks path unchanged).
3. **Preserve the honesty invariants** → verify: an OOD cell context stays OOD after a chromatin
   boost; an uncovered locus (signal 0) yields the unadjusted value; an unknown track name raises.
4. **Label the adjustment in the rationale** → verify: a chromatin-adjusted candidate's rationale
   records that the efficiency is chromatin-adjusted (and the raw signal), a non-adjusted one does not.
5. **Correct the docstrings** → verify: `design_prime` and the `prime_efficiency` module docstring
   describe the wired, opt-in behavior; no stale "unreachable" wording remains.
6. **Fold the spec delta into `specs/prime-editor-design/spec.md`, archive this folder, record in
   `changes/README.md`** → verify: full suite green, ruff+mypy clean, pushed to main.
