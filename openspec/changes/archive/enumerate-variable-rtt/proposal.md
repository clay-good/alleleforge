# Enumerate the variable-length RTT: prime editing for every small edit class

## Why

Prime editing's whole claim is that it writes an **arbitrary** small edit. AlleleForge's
enumerator templated only a single-base substitution: `enumerate_prime` returned `[]` for
anything where `len(ref) != 1 or len(alt) != 1`, and routing declined prime for those classes
so the flagship would not silently under-deliver. The honest guardrail was correct; the gap
behind it was not. Most monogenic disease that prime editing is *designed* for is an indel —
the CFTR ΔF508 3 bp deletion is the textbook case — and AlleleForge could not design a pegRNA
for a single one of them.

## What Changes

- **Variable-length RT template.** The RTT is templated as *5' homology (nick → edit) + the
  desired allele + 3' homology*, so substitution, MNV, insertion, deletion, and delins all
  enumerate. A deleted span costs no template length; a written one costs a base each.
- **Two honest budgets, mirrored in routing.** `PRIME_MAX_EDIT` (44 bp) bounds the reference
  span an edit may replace; the new `PRIME_MAX_TEMPLATED_EDIT` (29 bp = `RTT_RANGE` ceiling
  minus the minimum 3' homology) bounds the allele the RTT must write. Routing checks the
  *intent-specific* desired allele against the second, so it never advertises an edit no RT
  template in range can carry.
- **Truthful placement across a length-changing edit.** Enumeration runs on the genome the
  target actually carries, whose coordinates drift from the reference past a length-changing
  edit. A new `_Frame` maps every emitted span back to the **reference footprint its bases
  come from** (wider for a deletion, narrower for an insertion), and reports no placement at
  all for a protospacer lying wholly inside carried bases the reference does not contain.
- **PE3b classification that survives an indel.** Seed disruption is now decided by comparing
  the ngRNA's seed window in the start and edited genomes rather than a single base, and is
  confined to the prefix the two genomes share — the precondition for templating a PE3b
  spacer from the edited strand at all.

## Impact

- `enumerate/prime.py`, `design/routing.py` (`PRIME_MAX_EDIT` moves next to the RTT budget it
  derives from and is re-exported).
- Specs: `prime-editor-design` (enumeration reach, coverage honesty, placement),
  `candidate-ranking` (routing reach).
- No change to the canonical reproducibility run (an SNV): the golden digest is unchanged.
