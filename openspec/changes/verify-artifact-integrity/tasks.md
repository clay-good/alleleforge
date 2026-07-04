# Tasks

## 1. Hash-on-read for checkpoints
- [x] 1.1 In `ModelRegistry.checkpoint`, verify an existing cached file against the pinned
      `checkpoint_sha256` before returning it; fail closed on mismatch.
- [x] 1.2 Test: a tampered cached checkpoint is rejected on load.

## 2. Hash-on-read for datasets and references
- [x] 2.1 Re-verify cached dataset artifacts in `DatasetRegistry.resolve` when the
      descriptor pins a hash.
- [x] 2.2 Re-verify a cached reference FASTA in `genome/reference.py` when the build pins
      a hash; add an on-demand `verify()` for the FM-index cache. *(FASTA re-verify done;
      FM-index `verify()` still open.)*
- [x] 2.3 Tests for each tamper case. *(checkpoint, dataset, reference done.)*

## 3. Pin the remaining model cards
- [ ] 3.1 Compute and commit real `checkpoint_sha256` values for every card that ships a
      pinned artifact (maintainer release step).
- [x] 3.2 Make `known_failure_modes` a required card field; update cards and the schema.
- [x] 3.3 Test: a card missing failure modes is rejected.

## 4. Content-verify the cache on read
- [x] 4.1 Store a checksum with each cache entry and re-check payload bytes on read
      (default-on for artifact namespaces). *(Mechanism ships as opt-in
      `ContentAddressedCache(..., verify=True)`; wiring it default-on for the specific
      artifact namespaces is a follow-up.)*
- [x] 4.2 Test: a corrupted cache entry is detected on read.

## 5. Reconcile
- [ ] 5.1 `make ci` green; weight-free path unaffected (no download in CI).
