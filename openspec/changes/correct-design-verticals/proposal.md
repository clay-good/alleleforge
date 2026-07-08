# Correct design-vertical semantics

## Why

Four design-layer defects make a candidate mean something other than what its label and
ranking imply — each one silently misleads the researcher choosing an edit strategy:

1. **PE3b is measured from the wrong end of the seed.** For a frame-minus nicking guide
   the Cas9 seed is the PAM-proximal protospacer end (`proto_lo` side), so the edit is in
   the seed iff `edit_local - proto_lo < SEED_LENGTH`. The enumerator instead tests
   `proto_hi - edit_local <= SEED_LENGTH` (`enumerate/prime.py:108-111`) — the PAM-*distal*
   half. Genuine PE3b guides are demoted to plain PE3, and PAM-distal edits are falsely
   promoted to PE3b (the loop breaks on the first `seed_disrupting`, `prime.py:119-121`)
   and flagged `pe3b` (`design/prime.py:77`). PE3b's whole benefit — nicking only the
   edited strand to cut indel byproducts — is advertised where it does not hold.
2. **Nuclease + HDR correction is built on the reference, not the patient's allele.**
   `enumerate_cas9` fetches and enumerates guides on the raw reference
   (`enumerate/cas9.py:142-151`) with no allele substitution, while the base-editor and
   prime enumerators *do* substitute the carried allele (`enumerate/base_editor.py:234`,
   `enumerate/prime.py:257`). For a CORRECT/REVERT intent the patient carries the alt
   allele, so a PAM the alt destroys is still emitted, a PAM the alt creates is missed, and
   scoring runs on a 20-mer the patient does not have. Separately, `hdr_donor`
   (`cas9.py:251-282`) inserts no PAM/seed-blocking mutation, so a guide that still matches
   the corrected sequence re-cuts the HDR product — the classic HDR failure mode.
3. **Base-editor efficiency is a duplicate of cleanliness.** `design/base_editor.py:131`
   sets `efficiency = outcome.p_intended_exact` (target edited AND no bystander), and the
   ranker's cleanliness term reads the same clean-allele probability
   (`design/ranking.py:101`). So a base-editor candidate puts 0.65 of the composite weight
   (0.35 efficiency + 0.30 cleanliness) on one identical number, double-charging bystanders
   and understating activity — while Cas9 and prime put *raw activity* on the efficiency
   axis. Base editors are not compared like-with-like against the other chemistries.
4. **Per-chemistry caps truncate on a local proxy.** Each vertical applies
   `max_candidates_per_chemistry` on its own local sort (prime by efficiency,
   `design/prime.py:195`; Cas9 by efficiency-then-off-target, `cas9.py:187`; base by
   `p_intended_exact`, `base_editor.py:145`) *before* the global 4-objective ranker runs
   (`designer.py:240`). A candidate that would top the composite (modestly lower efficiency
   but far safer or cleaner) is pruned before the composite is computed.

## What Changes

- Measure PE3b seed disruption from the **PAM-proximal** protospacer end, so a guide is
  labeled `pe3b` only when the edit truly falls in its seed.
- For CORRECT/REVERT/INSTALL intents, enumerate Cas9 guides against the **allele the
  target genome carries** (matching the base/prime verticals), and have `hdr_donor`
  introduce — or explicitly report the absence of — a **PAM/seed-blocking mutation** so
  the corrected allele is not a re-cut substrate.
- Populate the base-editor **efficiency axis with target-base editing activity**
  (P(target position edited), bystander-independent), reserving the clean fraction for the
  cleanliness axis, so the two objectives measure distinct quantities as they do for Cas9
  and prime.
- Apply per-chemistry truncation **after projecting onto the shared ranking objectives**
  (or defer it to the global ranker), so a cap never removes a candidate that would rank
  above a retained one under the composite.

## Impact

- Specs: `prime-editor-design` (MODIFIED PE3b preference), `cas9-design` (ADDED
  allele-aware correction + re-cut-blocking donor), `base-editor-design` (ADDED activity
  efficiency axis), `candidate-ranking` (ADDED composite-preserving truncation).
- Code: `enumerate/prime.py`, `enumerate/cas9.py`, `design/cas9.py`, `design/base_editor.py`,
  `design/prime.py`, `design/designer.py`, `design/ranking.py`.
- Tests: a PAM-proximal-seed edit is classified PE3b and a PAM-distal one is not; a CORRECT
  intent whose alt allele destroys/creates a PAM enumerates the patient-correct guide set;
  an HDR donor reports its re-cut-blocking mutation; a high-activity/high-bystander base
  edit reports high efficiency and lower cleanliness; a capped run still returns the
  composite-optimal candidate. Rankings shift — regenerate affected menu goldens.
