# Tasks

- [x] Template the RTT at variable length (`edit_len` = the desired allele's length) so
      insertion, deletion, MNV, and delins enumerate alongside the SNV path.
- [x] Add `PRIME_MAX_TEMPLATED_EDIT`, derived from `RTT_RANGE` and
      `MIN_RTT_3PRIME_HOMOLOGY`, and fail closed above it (and above `PRIME_MAX_EDIT`) with
      an empty result rather than a truncated template.
- [x] Introduce `_Frame` so every placement and nick site is a reference footprint, and emit
      no placement where a protospacer has no reference locus.
- [x] Generalize PE3b seed classification to a seed-window comparison inside the shared
      prefix, so an indel is classified correctly and the spacer is templated from the right
      strand.
- [x] Widen `_prime_eligible` to the full small-edit repertoire under both budgets, checking
      the intent's *desired* allele; update the rule rationale.
- [x] Metamorphic verification: fetch every emitted pegRNA back and prove the RT product is a
      unique locus of the edited genome, that its PBS and protospacer read off the start
      genome at that same locus behind a real PAM, and that the template spans the edit with
      the minimum 3' homology — across six edit classes × both intents × both strands.
- [x] Pin the fail-closed edges (no-op edit, over-span, un-templatable allele) and the
      placement-footprint contract.
- [x] Replace the three tests that pinned the old SNV-only limitation.
- [x] Fold deltas into `openspec/specs/`, update README + CHANGELOG.
