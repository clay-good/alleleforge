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

## 2. Allele-aware nuclease correction + re-cut-blocking donor — DONE

- [x] In `enumerate/cas9.py`, substitute the carried allele onto the fetched window for
  CORRECT/REVERT/INSTALL intents before enumerating protospacers/PAMs, mirroring
  `enumerate/base_editor.py` and `enumerate/prime.py`.
  (`carried_allele` + `_overlay_allele` applied in `_enumerate_pam`; `design/cas9.py`
  threads the same overlay into `guide_context` and `_cut_outcome` so on-target scoring
  reads the carried 20-mer too. Length-preserving substitution only — indels keep the
  reference frame, as the prime/base enumerators bail on non-single-position edits.)
- [x] In `hdr_donor` (`enumerate/cas9.py`), introduce a PAM-blocking silent mutation
  in the donor, or explicitly report that none is available, so the corrected allele is not
  a Cas9 substrate.
  (`hdr_donor` now takes the `guide` it must survive and returns an `HDRDonor` carrying the
  sequence, an optional `BlockingMutation`, a `recut_blocked` flag, and a note. It searches
  the PAM for a base in a homology arm whose change breaks the guide's PAM; if the
  correction itself already disrupts the PAM/seed no mutation is added; if no arm PAM base
  can block, `recut_blocked = False` with an explicit note.)
- [x] Test: a CORRECT intent whose alt allele destroys the reference PAM does not emit that
  guide; one whose alt creates a PAM does emit it; the donor records its blocking mutation.
  (`test_correct_intent_drops_guide_when_alt_destroys_pam`,
  `test_correct_intent_finds_guide_when_alt_creates_pam`,
  `test_hdr_donor_records_pam_blocking_mutation`,
  `test_hdr_donor_no_block_needed_when_edit_disrupts_pam`.)

## 3. Base-editor efficiency axis — DONE

- [x] In `design/base_editor.py`, set the ranking efficiency axis to target-base editing
  activity (P(target position edited), independent of bystanders); keep the clean fraction
  on the cleanliness axis.
  (`WindowOutcome.p_target_edited` = the marginal target-edit probability; the candidate's
  `efficiency` now reads it, while cleanliness stays `outcome.p_intended`.)
- [x] Verify the axis is populated consistently with the Cas9/prime activity axis.
  (Efficiency is now raw activity on every chemistry; cleanliness is the distinct clean
  fraction — the two ranking objectives no longer collapse to one number for base editors.)
- [x] Test: a high-activity/obligate-bystander base edit reports high efficiency and lower
  cleanliness, and is not double-penalized.
  (`test_target_activity_is_distinct_from_clean_fraction`.)

## 4. Composite-preserving truncation — DONE

- [x] In the vertical enumerators / `design/designer.py`, apply
  `max_candidates_per_chemistry` after projecting candidates onto the shared ranking
  objectives (or defer truncation to the global ranker).
  (Verticals now receive `max_candidates=None`; `rank_candidates` gained a
  `max_per_chemistry` cap applied **after** the composite sort. Off-target search already
  ran on every candidate before the old local slice, so no extra compute.)
- [x] Test: with a per-chemistry cap set, a candidate that tops the composite but is lower
  on a vertical's local proxy is still returned.
  (`test_cap_keeps_composite_best_not_local_proxy_best`, `test_cap_is_per_chemistry`.)

## 5. Regenerate goldens — DONE

- [x] Regenerate menu/ranking goldens affected by the axis and truncation changes.
  (No golden churn: the full suite — including the reproduce/golden tests — passes
  unchanged. The carried-allele substitution and scoring overlay only alter output when
  the variant sits inside a precise-intent guide's protospacer/PAM, which the golden
  fixtures do not exercise; the axis/truncation changes shipped in their own increments.)

## Status

All parts are **shipped**. Part 1 (PE3b seed direction), part 3 (base-editor activity
efficiency axis), and part 4 (composite-preserving truncation) landed earlier; part 2
(allele-aware nuclease correction against the carried allele + a re-cut-blocking HDR donor,
spanning `enumerate/cas9.py`, `design/cas9.py`, and the `HDRDonor`/`BlockingMutation`
types) and part 5 (golden verification) complete the change. Ready to archive.
