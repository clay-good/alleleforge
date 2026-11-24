# R0 — pinning every shipped artifact

_Written 2026-11-24. R0 read "1/12 model cards with a source URL pin a checkpoint hash;
3/8 datasets pin one", blocked on "first deciding which file that is" for 16 of them.
This resolves that decision. The answer is not the one the blocker implied: for **6 of
the 11 unpinned model cards there is no single file to name**, and the reason is in this
repository's own loaders, not upstream. Two cards were also found citing dead URLs, and
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

### Recommendation

Add a `source_snapshot` pin — a repository plus an immutable revision — alongside the
existing single-file `source_url`/`checkpoint_sha256` pair:

- For the HF backbones: repo id + the 40-hex commit sha. `from_pretrained(repo,
  revision=sha)` already accepts exactly this, so the loader change is one keyword, and
  the pin becomes *stronger* than a blob hash because it covers the tokenizer and config
  the model is actually loaded with.
- For the checkout adapters: repository + commit sha, which is what
  `ALLELEFORGE_*_REPO` ought to be checked against. A content hash of
  `archive/<sha>.tar.gz` is **not** a safe substitute: GitHub's generated tarballs are
  not guaranteed byte-stable.

That change closes 6 of the 11 honestly. It is not in this round because it touches the
card schema, the consent gate's "pinned" predicate, the readiness report's definition of
pinned, and two loaders — and R0's wording ("pins a verified artifact hash") would need
to admit a revision pin as verification.

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
| 3 HF backbones | loader needs a snapshot | the `source_snapshot` pin above |
| `lindel`, `be-dict`, `pridict2` | loader needs a checkout | the `source_snapshot` pin above |
| `be-hive` | a web service, no artifact | upstream publishing a checkpoint |
| `deepprime`, `genet`, `indelphi`, `x-crisp` | repositories with no weight asset | a release **asset** rather than a source tag |
| 5 heuristic baselines | no artifact exists — they are code | nothing; correctly unpinnable |
| `dbsnp` | only a floating `latest_release/` path | a versioned URL from NCBI |
| `1000g`, `encode`, `gnomad`, `hgdp` | portals, not files | choosing per-release files, then fetch-and-hash |

The four dataset portals are the one group this repository could finish unilaterally:
each has per-release files behind the portal, so the work is choosing them and hashing.
That is its own change — the files are large enough that fetch-and-hash is a deliberate
operation.

## Status

R0 stays **open at 1/12 cards and 3/8 datasets** — unchanged by this round, deliberately.
What changed is that it is no longer blocked on an unmade decision: 6 cards need a schema
pin that is specified above, 5 need an upstream release, the datasets need file choices,
and two cards stopped lying about where they came from.
