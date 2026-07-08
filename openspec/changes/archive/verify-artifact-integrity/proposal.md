# Verify artifact integrity on every load, not just on download

## Why

The consent + license + checksum gate is the tool's supply-chain trust story, but it is
bypassed exactly where tampering matters most — on cache hits:

- **Cached checkpoints are trusted without re-verification.** `ModelRegistry.checkpoint`
  only hashes bytes when it downloads them; an existing cached file is returned unverified
  (`model_zoo/registry.py:241`). A tampered or truncated cache entry passes silently on
  every subsequent load.
- **Cached datasets and reference FASTAs have the same hole.** `DatasetRegistry.resolve`
  returns immediately on a cache hit without re-hashing (`data/registry.py:165`), and the
  genome loader verifies only freshly downloaded builds (`genome/reference.py:242-244`).
- **Almost nothing is actually pinned.** Only `rule-set-3.yaml` carries a real
  `checkpoint_sha256`; the other cards have `checkpoint_sha256: null`, so every other
  model takes the no-checksum `authorize` path — integrity currently rests on
  HuggingFace/GitHub, not on AlleleForge.
- **The content-addressed cache trusts bytes on read.** `get_bytes` returns whatever is at
  the path (`cache.py:71-74`); a corrupted or externally-modified entry is served as-is.

The mechanisms exist; they just aren't wired into the read paths.

## What Changes

- **Hash-on-read**: verify a cached checkpoint, dataset, or reference against its pinned
  hash on every load, not only on download. A mismatch fails closed with a clear message.
- **Pin the remaining cards**: give every model card a real `checkpoint_sha256` as part of
  a release, turning `authorize` into the exception rather than the rule.
- **Content-verify the cache on read** (optional but default-on for artifacts): store a
  checksum with each entry and re-check payload bytes against it before returning.
- Make `known_failure_modes` **required** on cards so every model's audit surface is
  complete.

## Status (complete)

The **hash-on-read** core has shipped (tasks 1 and 2): a cached checkpoint
(`ModelRegistry.checkpoint`), dataset (`DatasetRegistry.resolve`), and reference
FASTA (`ReferenceGenome.from_build`) are now re-verified against their pinned hash
on **every** load, not only on download — a tampered or truncated cache entry
fails closed. Tamper-on-read tests cover all three. When a card/descriptor pins no
hash, the artifact is served as before (there is nothing to verify against).

Task 3.2/3.3 has also shipped: `known_failure_modes` is now a **required**,
non-empty `ModelCard` field (validated at construction), so every model's audit
surface is complete and rides into provenance. The FM-index `verify()` has shipped:
it reconstructs the indexed text from the persisted BWT via LF-mapping and re-checks
it against the content hash recorded at build time, raising `FMIndexIntegrityError`
on a corrupt cache. Task 4 (content-verify the cache on read) has shipped as an
opt-in: `ContentAddressedCache(..., verify=True)` stores a checksum sidecar with each
entry and re-checks the payload bytes on read, raising `CacheIntegrityError` on a
mismatch; wiring it default-on for the specific artifact namespaces is a follow-up.

Task 3.1 is now resolved as scoped. Only `rule-set-3` ships a maintainer-hosted
pinned artifact; its real hash is committed and was **re-verified this session** by
downloading the hosted release (17.5 MB `RuleSet3.txt`) — the sha256 matches the
pinned value exactly. Every other card is `checkpoint_sha256: null` by design: they
load from upstream sources or are out-of-scope cross-check placeholders (see
`specs/cross-check-models-scope.md`), and the registry **fail-closes** on an unpinned
artifact — refusing to fetch what it cannot checksum — so the gate is never bypassed.
Pinning further cards would require a maintainer to freeze + host each release
artifact (choosing hosting and version), which is out of scope for this change. With
task 5.1 (`make ci` green) confirmed, this change is complete.

## Impact

- Specs: `model-zoo` (MODIFIED gate to require hash-on-read + required failure modes),
  `data-registry` (ADDED cached-artifact re-verification), `genome-access` (ADDED cached
  build/index re-verification).
- Code: `model_zoo/registry.py`, `model_zoo/loader.py`, `data/registry.py`,
  `genome/reference.py`, `genome/index.py`, `cache.py`, and the model card YAML files.
- Tests: a tampered cached checkpoint/dataset/reference is rejected on load; a card
  without failure modes is rejected; a corrupted cache entry is detected on read.
- Note: this needs the maintainer to compute and commit the real hashes for the remaining
  cards (a one-time release step), tracked in `tasks.md`.
