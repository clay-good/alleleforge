# R0 — pinning every shipped artifact

_Written 2026-11-24. R0 read "1/12 model cards with a source URL pin a checkpoint hash;
3/8 datasets pin one", blocked on "first deciding which file that is" for 16 of them.
This resolves that decision. The answer is not the one the blocker implied: for **6 of
the 11 unpinned model cards there is no single file to name**, and the reason is in this
repository's own loaders, not upstream. A `source_snapshot` revision pin now covers all
six. Two cards were also found citing dead URLs, and
one misattributing its authorship._

## The decision, resolved

`checkpoint_sha256` and `source_url` describe **one file** that `ensure_checkpoint`
downloads and hash-verifies. The question "which file?" only has an answer when the
consumer loads one file. For six cards it does not:

| cards | what the loader consumes | why one hash cannot pin it |
| --- | --- | --- |
| `caduceus`, `evo2`, `nucleotide-transformer-v2-500m` | `from_pretrained(target)` | needs a repo id or a **snapshot directory** (config + tokenizer + weights), not a blob |
| `lindel`, `be-dict`, `pridict2` | a whole checkout via `ALLELEFORGE_*_REPO` | reads several files **plus importable Python** |

For the three Hugging Face backbones this was tested, not reasoned about. HF *does*
publish an immutable `resolve/<commit-sha>/<file>` URL and the SHA256 of each blob at
that revision — `caduceus`'s `model.safetensors` (30,937,760 bytes) was downloaded here
and rehashed to exactly HF's published digest, so the artifacts are real and hashable.
Pinning them still broke the product: `backbone.py` does

```python
target = self.resolve_weights() or self.model_id
model = auto_model.from_pretrained(target)
```

so a pinned card makes `target` a single cached `.ckpt` and hands `from_pretrained` a
file where it needs a snapshot. `tests/scoring/test_backbone_consent.py` asserts
`resolve_weights() is None` with the comment "no pinned artifact -> load by model id
after the gate", and it caught the regression. **The pin would have moved R0 from 1/12 to
4/12 while breaking the real-weights load path for anyone with the `ml` extra** — a
criterion satisfied by a number and broken in fact.

So the blocker was misstated in both directions. It is not "upstream has published
nothing hashable" (HF has). It is **"the card schema pins one file and six of these
loaders consume a set of files."** That is a schema question, and it is answerable here.

### Implemented: the `source_snapshot` pin

A `source_snapshot` field now pins a repository plus an immutable 40-hex revision,
alongside the existing single-file `source_url`/`checkpoint_sha256` pair. The three
Hugging Face backbones use it, and `backbone.py` passes the revision through to
`from_pretrained(target, revision=sha)`.

Why this is the right shape, and in one respect **stronger** than a blob hash: it covers
the tokenizer and config the model is actually loaded with, not just the weights file.
Two runs naming the same revision load the same model.

What it is *not*, and why R0's count does not move: it is not "a verified artifact hash".
The per-blob digests are checked by the hub client against the metadata upstream
published for that revision — this project does not recompute them. R0 asks for a hash
this project verified, so `scripts/release_readiness.py` reports snapshot pins as their
own evidence line, with that caveat, and leaves the criterion at 1/12. **Folding them in
would have moved the number without meeting the criterion, which is how a release gate
becomes a formality** — and is the mistake this round already made once with blob hashes.

Three things the schema refuses, each because accepting it would make the field look like
a pin while leaving the bytes free to move: a branch or tag, a short sha, and a card
carrying *both* pin kinds (`resolve_weights()` takes the single-file path whenever
`checkpoint_sha256` is set and never consults the snapshot, so the revision would be
silently ignored).

**Done for the checkout adapters too.** `lindel`, `be-dict` and `pridict2` now pin a
revision, and `check_checkout_revision` compares it against the directory
`ALLELEFORGE_*_REPO` points at. It **warns rather than refuses**, in three distinct
cases: on the pinned revision it is silent; on another revision it names both, because
scoring against upstream's latest is legitimate work; and when the revision cannot be
read — an unpacked tarball is a supported way to supply these — it says so, since "cannot
tell" is a different statement from "wrong". What must not happen is a run quietly using
something other than the pin while its provenance names the pin.

The revision is read from git's own plumbing rather than by shelling out: `git` need not
be installed, and a subprocess per prediction is a cost on a scoring path. A content hash
of `archive/<sha>.tar.gz` remains unsafe: GitHub's generated tarballs are not guaranteed
byte-stable.

Provenance of the three revisions, so they are auditable rather than plausible:

| card | repo | revision | how obtained |
| --- | --- | --- | --- |
| `caduceus` | `kuleshov-group/caduceus-ps_seqlen-131k_d_model-256_n_layer-16` | `d89eeb85…` | HF model API; blob also downloaded and rehashed to upstream's digest |
| `nucleotide-transformer-v2-500m` | `InstaDeepAI/nucleotide-transformer-v2-500m-multi-species` | `06615c16…` | HF model API |
| `evo2` | `arcinstitute/evo2_7b` | `bda0089f…` | HF model API |
| `lindel` | `shendurelab/Lindel` | `fdcad580…` | GitHub API, `master` head 2026-03-07 |
| `be-dict` | `uzh-dqbm-cmi/crispr` | `9d7f8bb2…` | GitHub API, `master` head 2026-10-30 |
| `pridict2` | `uzh-dqbm-cmi/PRIDICT2` | `c133c35e…` | GitHub API, `main` head 2026-02-02 |

## Two defects found by resolving the URLs rather than reading them

Neither was a pinning question.

- **`x-crisp` cited work that does not exist.** The card said "Zhang et al., 2023". There
  is one X-CRISP — Seale C & Gonçalves JP, *Bioinformatics Advances* 2025
  (doi:10.1101/2025.02.06.636858) — and its repository had moved. A model card that
  misattributes the work it wraps is a provenance defect, not a typo, and these are the
  fields the project asks researchers to trust. Corrected.
- **Two source URLs returned 404** — `Liam-Chen/PRIDICT2` and `AhmedjBaqer/X-CRISP`. A
  card citing an address that does not resolve is worse than one merely unpinned, because
  the claim looks checkable and is not. Repointed to `uzh-dqbm-cmi/PRIDICT2` and
  `joanagoncalveslab/XCRISP`, each cross-checked against the card's own citation.

**Left for a human:** upstream X-CRISP is GPL-3.0; the card says `research-only`. That
field drives the license gate, so the difference is not cosmetic — but `research-only` is
the stricter reading, the weights' own terms are not stated upstream, and loosening a
gate on an inference is the unsafe direction. Unchanged, flagged.

## What is enforced now

`tests/model_zoo/test_a_pinned_hash_requires_an_immutable_url.py`: **a hash beside a
mutable address is not a pin.** A digest next to a branch or a landing page fails the
moment upstream pushes, and the consent gate then refuses a model that used to load,
reporting "hash mismatch" when the truth is "upstream moved". Also guards that the two
dead owners cannot return, that digests are full lower-case SHA256, and that the set of
pinned cards is a deliberate edit rather than a side effect.

## The rest, and what each needs

| artifact | why unpinned | what would unblock it |
| --- | --- | --- |
| 3 HF backbones | loader needs a snapshot | **done** — `source_snapshot`, reported separately from R0 |
| `lindel`, `be-dict`, `pridict2` | loader needs a checkout | **done** — `source_snapshot` + `check_checkout_revision` |
| `be-hive` | a web service, no artifact | upstream publishing a checkpoint |
| `deepprime`, `genet`, `indelphi`, `x-crisp` | repositories with no weight asset | a release **asset** rather than a source tag |
| 5 heuristic baselines | no artifact exists — they are code | nothing; correctly unpinnable |
| `dbsnp` | **address fixed** — `/snp/archive/b156/`; `sha256` needs a 26 GB fetch | a deliberate fetch-and-hash (upstream publishes md5 only) |
| `1000g`, `encode`, `gnomad`, `hgdp` | portals, not files | choosing per-release files, then fetch-and-hash |

The four dataset portals are the one group this repository could finish unilaterally:
each has per-release files behind the portal, so the work is choosing them and hashing.
That is its own change — the files are large enough that fetch-and-hash is a deliberate
operation.

## The dbsnp defect, which was not a pinning problem

`dbsnp` declared `version="b156"` and cached as `dbsnp.b156.tsv.gz` while its
`source_url` pointed at `/snp/latest_release/`. Upstream had published b157, so the
address served 29,552,227,779 bytes where the descriptor meant 26,611,209,012. **A run
would have fetched one build of dbSNP and recorded it as another** — a false provenance
claim in a field whose only job is to say which data a result came from. The floating
address had already drifted a build ahead of the version beside it.

Repointed at `/snp/archive/b156/`, which cannot move and matches the declared version.
Upgrading to b157 is a separate, deliberate decision — new version, new cached filename —
and not something an address fix should do silently. A `sha256` still needs a 26 GB
fetch-and-hash (NCBI publishes md5 only: `a1082ca70e15eb63301dfc33b19d0ae7`), but it is
now a hash that stays true rather than one the next release invalidates.

Guarded two ways, both offline: no descriptor may name a moving address, and the three
descriptors whose upstream versions its paths must contain their version in it — which is
what would have caught this with no network at all.

## Deferred: the CFD matrix's citation

`doench-2016-cfd`'s `source_url` is a `master` URL, which the moving-target rule flags,
and it is exempt. It is not a fetch target: it is a *key* into the `sources` map inside
the shipped `cfd_matrix.json`, which records each upstream the matrix was cross-verified
against with that upstream's digest. Two existing tests hold the descriptor and that
record to the same key.

Pinning it to the commit that last touched the file was tried and reverted. The key would
have to change inside `cfd_matrix.json` too, which changes that file's digest, which is
the hash this registry pins — so making a citation immutable means re-cutting the matrix's
authentication trail. The content is verified identical at `master` and at that commit
(6,965 bytes, sha256 `c58e9c1a85f0…`), so nothing is wrong today; the exposure is that
the citation could later name bytes nobody checked. Worth doing deliberately, not in
passing.

## Status

R0 stays **open at 1/12 cards and 3/8 datasets** — unchanged, deliberately, because a
revision pin is not the hash the criterion asks for. What changed: all six cards whose loader
consumes a set of files are now reproducibly pinned and checked, five need an upstream
release, the datasets need file choices, and two cards stopped misstating where they came
from.
