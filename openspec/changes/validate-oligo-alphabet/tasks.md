# Tasks

## 1. Strict alphabet validation
- [ ] 1.1 Make `revcomp` raise on any character outside `ACGTN` (clear message naming the
      offending character).
- [ ] 1.2 Validate the DNA alphabet of every input sequence at oligo construction.
- [ ] 1.3 Tests: `U`, an IUPAC ambiguity code, and whitespace each raise; valid DNA is
      unchanged.

## 2. Verify the scaffold
- [ ] 2.1 Check the stored scaffold against the expected constant for the cloning scheme.
- [ ] 2.2 Test: a wrong/empty scaffold is rejected.

## 3. Independent RTT/PBS boundary check
- [ ] 3.1 Annotate component lengths in the oligo output and assert the RTT/PBS split
      reconstructs independently of the stored slice length.
- [ ] 3.2 Test: a deliberately mis-split extension is detected.

## 4. Reconcile
- [ ] 4.1 `make ci` green; oligo goldens unchanged for valid inputs.
