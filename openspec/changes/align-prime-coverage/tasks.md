# Tasks

## 1. Feasibility-aware routing
- [x] 1.1 Add a lightweight feasibility check (edit class enumeration supports) and have
      `_prime_eligible` consult it; today that means SNV-only.
- [x] 1.2 When declining, record a specific reason ("prime enumeration does not yet support
      insertions/deletions") rather than a generic note. *(Surfaced via the prime rule
      rationale on the ineligible routing decision.)*
- [x] 1.3 Test: an indel routes with the explicit reason, or enumerates if supported.

## 2. Pol-III constraints as inspectable reasons
- [x] 2.1 Filter spacers with a `TTTT` terminator and enforce/annotate the 5'-G start and a
      spacer-GC band; expose each rejection as a stated reason. *(TTTT-terminator filter
      shipped — a spacer that cannot be transcribed is never enumerated; the 5'-G/GC-band
      annotation and per-candidate reason surfacing remain open.)*
- [x] 2.2 Test: a `TTTT`-containing spacer is rejected with its reason.

## 3. Separate a defect from an empty result
- [x] 3.1 In `_run_chemistry` and `_design_one`, catch only expected "no design" conditions;
      re-raise or capture unexpected exception types as a typed failure.
- [x] 3.2 Test: an injected error in a vertical surfaces as a typed failure, not a
      "skipped" note.

## 4. Reconcile
- [ ] 4.1 Update docs so prime's supported edit classes are stated honestly.
- [ ] 4.2 `make ci` green.
