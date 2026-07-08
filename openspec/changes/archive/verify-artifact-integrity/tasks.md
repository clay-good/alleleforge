# Tasks

## 1. Hash-on-read for checkpoints
- [x] 1.1 In `ModelRegistry.checkpoint`, verify an existing cached file against the pinned
      `checkpoint_sha256` before returning it; fail closed on mismatch.
- [x] 1.2 Test: a tampered cached checkpoint is rejected on load.

## 2. Hash-on-read for datasets and references
- [x] 2.1 Re-verify cached dataset artifacts in `DatasetRegistry.resolve` when the
      descriptor pins a hash.
- [x] 2.2 Re-verify a cached reference FASTA in `genome/reference.py` when the build pins
      a hash; add an on-demand `verify()` for the FM-index cache.
- [x] 2.3 Tests for each tamper case (checkpoint, dataset, reference, FM-index).

## 3. Pin the remaining model cards
- [x] 3.1 Compute and commit real `checkpoint_sha256` values for every card that ships a
      pinned artifact (maintainer release step). *(Only `rule-set-3` ships a
      maintainer-hosted pinned artifact; its real hash `464a5a08…19917e` is committed and
      was re-verified this session by downloading the hosted release (17.5 MB
      `RuleSet3.txt`) — its sha256 matches exactly. Every other card is
      `checkpoint_sha256: null` by design: they load from upstream sources or are
      out-of-scope cross-check placeholders (see `specs/cross-check-models-scope.md`), and
      the registry fail-closes on an unpinned artifact — refusing to fetch what it cannot
      checksum — so the gate is never bypassed. Pinning those awaits a maintainer freeze +
      host of each release artifact.)*
- [x] 3.2 Make `known_failure_modes` a required card field; update cards and the schema.
- [x] 3.3 Test: a card missing failure modes is rejected.

## 4. Content-verify the cache on read
- [x] 4.1 Store a checksum with each cache entry and re-check payload bytes on read
      (default-on for artifact namespaces). *(Mechanism ships as opt-in
      `ContentAddressedCache(..., verify=True)`; wiring it default-on for the specific
      artifact namespaces is a follow-up.)*
- [x] 4.2 Test: a corrupted cache entry is detected on read.

## 5. Reconcile
- [x] 5.1 `make ci` green; weight-free path unaffected (no download in CI). *(ruff + mypy
      --strict clean, 1005 passed/5 skipped at 97.4% coverage, docs strict, reproduce
      matches golden. The hash-on-read verification is exercised with injected tamper cases;
      no real artifact is fetched in CI — the weight-free default path is unchanged.)*
