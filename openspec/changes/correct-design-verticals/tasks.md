# Tasks

## 1. PE3b seed direction — DONE

- [x] In `enumerate/prime.py`, change the frame-minus seed-disruption test to measure from
  the PAM-proximal protospacer end (`edit_local - proto_lo < _SEED_LENGTH`), matching the
  Cas9 seed definition.
- [x] Confirm the frame-plus path (if any) measures from its own PAM-proximal end.
  (There is only one nicking-guide seed computation — the frame-minus `_select_nicking_guide`;
  the frame-plus path enumerates pegRNAs, not ngRNAs, so it has no seed test to correct.)
- [x] Test: an edit in the PAM-proximal seed is classified `pe3b` and preferred; a
  PAM-distal edit is not classified `pe3b`.
  (`test_pe3b_preferred_when_seed_disrupting` on a proto_lo=61 seed spanning edit 70, and
  `test_pam_distal_edit_is_not_labeled_pe3b` on the proto_lo=58 / 12-nt-distal case; three
  downstream fixtures that encoded the wrong direction were corrected to a real PE3b geometry.)

## 2. Allele-aware nuclease correction + re-cut-blocking donor

- [ ] In `enumerate/cas9.py`, substitute the carried allele onto the fetched window for
  CORRECT/REVERT/INSTALL intents before enumerating protospacers/PAMs, mirroring
  `enumerate/base_editor.py` and `enumerate/prime.py`.
- [ ] In `hdr_donor` (`design/cas9.py`), introduce a PAM- or seed-blocking silent mutation
  in the donor, or explicitly report that none is available, so the corrected allele is not
  a Cas9 substrate.
- [ ] Test: a CORRECT intent whose alt allele destroys the reference PAM does not emit that
  guide; one whose alt creates a PAM does emit it; the donor records its blocking mutation.

## 3. Base-editor efficiency axis

- [ ] In `design/base_editor.py`, set the ranking efficiency axis to target-base editing
  activity (P(target position edited), independent of bystanders); keep the clean fraction
  on the cleanliness axis.
- [ ] Verify the axis is populated consistently with the Cas9/prime activity axis.
- [ ] Test: a high-activity/obligate-bystander base edit reports high efficiency and lower
  cleanliness, and is not double-penalized.

## 4. Composite-preserving truncation

- [ ] In the vertical enumerators / `design/designer.py`, apply
  `max_candidates_per_chemistry` after projecting candidates onto the shared ranking
  objectives (or defer truncation to the global ranker).
- [ ] Test: with a per-chemistry cap set, a candidate that tops the composite but is lower
  on a vertical's local proxy is still returned.

## 5. Regenerate goldens

- [ ] Regenerate menu/ranking goldens affected by the axis and truncation changes.

## Status

Part 1 (PE3b seed direction) is **shipped**. Parts 2 (allele-aware nuclease correction +
re-cut-blocking donor), 3 (base-editor activity efficiency axis), and 4 (composite-preserving
per-chemistry truncation) remain open — each is a design-layer change with golden impact and
is deferred to its own focused increment.
