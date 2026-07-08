# Align prime-editing routing with what enumeration can actually produce

## Why

Prime editing is described as the flagship value, but routing over-promises it. Routing
advertises prime for any non-knockout edit up to 44 bp (`design/routing.py:37, 71-76`),
yet `enumerate_prime` hard-returns `[]` for anything but a 1-bp-ref/1-bp-alt SNV
(`enumerate/prime.py:237`, with `edit_len` fixed to 1 at `prime.py:145`). Insertions,
deletions, and MNVs route to prime, enumerate nothing, and surface only as a generic
"eligible but no actionable candidate" note (`design/designer.py:281`). The headline
capability — arbitrary small edits by prime editing — is not actually delivered, and the
menu does not say so clearly.

Two adjacent gaps: enumeration applies no Pol-III constraints (no `TTTT`-terminator filter,
no 5'-G transcription-start requirement) that real pegRNA design needs; and the blanket
`except Exception` in `_run_chemistry` (`designer.py:277`) and `_design_one`
(`cohort.py:224`) makes a genuine bug indistinguishable from "no design," masking defects
behind graceful degradation.

## What Changes

- Make routing **consult a feasibility check** so it only advertises prime for edit classes
  enumeration can produce today (SNV), and state the reason when it declines — no more
  silent under-delivery. (If/when the variable-`edit_len` RTT path lands, widen the check.)
- Add **Pol-III constraints** (terminator, 5'-G start, spacer-GC) as inspectable rejection
  reasons rather than silent absence.
- **Distinguish a crash from "no design"**: re-raise or capture unexpected exception types
  as a typed failure so cohort error columns are actionable, instead of swallowing every
  exception into a note.

## Status (partial)

Task 1 has shipped: `_prime_eligible` now consults an SNV feasibility gate matching
what `enumerate_prime` can produce, so routing no longer advertises prime for
insertions, deletions, or MNVs it cannot template — and the prime routing rule's
rationale states the SNV-only limitation, so an ineligible decision carries the
specific reason instead of a generic "no candidate" note. Task 2 has also partly
shipped: `enumerate_prime` now filters a protospacer containing a `TTTT` Pol III
terminator (a pegRNA that cannot be transcribed from a U6 promoter is never
enumerated). Task 3 has also shipped: `_run_chemistry` and `_design_one` now catch
only *expected* design-failure exceptions (missing model, bad input, absent optional
dependency) as graceful "skipped"/error records, and tag any *unexpected* exception
type as a defect ("ERROR — unexpected …") so a genuine bug is no longer masked as
"no design". The 5'-G-start and GC-band caveats now surface as inspectable
candidate flags (`no-5prime-g`, `gc-out-of-band:<frac>`) rather than silent
absence. The only remaining item is a per-candidate rejection-reason channel
threaded out of enumeration (so a *dropped* candidate can state its reason), a
structural follow-up.

## Impact

- Specs: `prime-editor-design` (MODIFIED coverage honesty; ADDED Pol-III filters as
  inspectable reasons), `candidate-ranking` (MODIFIED graceful-degradation to separate a
  defect from an empty result).
- Code: `design/routing.py`, `enumerate/prime.py`, `design/designer.py`, `design/cohort.py`.
- Tests: an indel edit either enumerates a pegRNA or routes with an explicit "not yet
  supported" reason (not a generic note); a spacer with a `TTTT` terminator is rejected
  with a stated reason; an injected bug in a vertical surfaces as a typed failure, not a
  silent "no design."
