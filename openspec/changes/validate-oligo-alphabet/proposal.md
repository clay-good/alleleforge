# Validate the alphabet in the wet-lab oligo path

## Why

The oligo module produces the exact annealed duplexes a bench scientist orders — a real
wet-lab deliverable where a wrong sequence wastes reagents and experiments. Its
`revcomp` uses `str.maketrans("ACGTN", "TGCAN")`, which **leaves any other character
unchanged** (`report/oligos.py:27, 30-32`). An RNA `U`, an IUPAC ambiguity code
(`R/Y/W/S/...`), or stray whitespace passes through untranslated, producing a wrong
antisense oligo — and because both strands are built from the same bad `revcomp`, the
round-trip reconstruction can still pass. There is no alphabet validation anywhere in the
module. This is the single highest-risk correctness issue in the codebase, and it is
cheap to fix.

Two lesser gaps compound it: the pegRNA `scaffold` is stored but never verified against a
known constant (`oligos.py:264, 176-202`), so a wrong/empty scaffold is invisible in the
deliverable; and the RTT/PBS split is validated against the same stored lengths it was
built from (`oligos.py:197-198`), so it cannot independently catch a mis-split boundary.

## What Changes

- Add **strict `ACGTN` alphabet validation** to `revcomp` (and at oligo construction):
  any character outside the DNA alphabet raises immediately with a clear message, so a
  mis-complemented oligo can never be emitted.
- **Verify the scaffold** against the expected constant for the chosen cloning scheme, so
  a wrong or empty scaffold is caught rather than silently shipped.
- Add an **independent RTT/PBS boundary check** (annotate component lengths in the output
  and assert reconstruction without relying solely on the stored fields).

## Impact

- Specs: `oligo-output` (MODIFIED round-trip to require alphabet validation; ADDED
  scaffold verification).
- Code: `report/oligos.py`.
- Tests: a spacer/RTT/PBS containing `U`, an IUPAC code, or whitespace raises at
  construction; a wrong scaffold is rejected; existing valid-DNA cases are unchanged.
