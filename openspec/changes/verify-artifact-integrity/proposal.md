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

## Status (partial)

The **hash-on-read** core has shipped (tasks 1 and 2): a cached checkpoint
(`ModelRegistry.checkpoint`), dataset (`DatasetRegistry.resolve`), and reference
FASTA (`ReferenceGenome.from_build`) are now re-verified against their pinned hash
on **every** load, not only on download — a tampered or truncated cache entry
fails closed. Tamper-on-read tests cover all three. When a card/descriptor pins no
hash, the artifact is served as before (there is nothing to verify against).

Still open: pinning real `checkpoint_sha256` values for the remaining cards (a
maintainer release step that requires downloading and hashing the actual
artifacts — must be done authoritatively, not guessed); making
`known_failure_modes` a required card field (task 3.2/3.3); the FM-index
`verify()` and content-verifying the content-addressed cache on read (task 4).

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
