# CRISPR-Bench

A standardized, calibration-first benchmark for CRISPR guide- and edit-design
models. CRISPR-Bench is AlleleForge's sister deliverable and a field-level
contribution in its own right: a common yardstick — versioned datasets, frozen
splits, fixed task contracts, and an honest leaderboard — that any model can be
measured against, whether or not it uses the rest of AlleleForge.

> This package ships **small synthetic fixtures** so the whole benchmark runs in
> CI with no downloads and no scientific-stack dependency. The real public
> corpora are fetched at runtime, with consent, through the same license-gated
> registry the rest of AlleleForge uses. The synthetic numbers are for plumbing,
> not for science.

## The five tasks

| Task | Kind | Source corpus | Primary metric | + required |
|---|---|---|---|---|
| `cas9-efficiency` | regression | Rule Set 3 validation, DeepHF/DeepSpCas9 | Spearman | Pearson, **ECE** |
| `cas9-outcome` | distribution | FORECasT, inDelphi, Lindel | KL ↓ | top-1, **ECE** |
| `be-outcome` | distribution | BE-Hive, BE-DICT | KL ↓ | top-1, **ECE** |
| `pe-efficiency` | regression | PRIDICT2 Library-Diverse | Spearman | Pearson, **ECE** |
| `offtarget-classification` | classification | GUIDE-seq / CHANGE-seq aggregates | AUROC | AUPRC, **ECE** |

Calibration (Expected Calibration Error) is required on **every** task. A model
that is accurate but overconfident is dangerous for edit design, so honesty is
ranked next to accuracy rather than buried in an appendix.

## Datasets, licenses, and citations

Each dataset declares its provenance up front (`BenchmarkDataset.dataset_version()`
returns the license, citation, source URL, and content hash). The upstream
corpora and their references:

| Dataset | Reference | License posture |
|---|---|---|
| `rs3-validation` | DeWeirdt & Doench, *Nat Commun* 2022 (Rule Set 3) | Open; redistribution varies |
| `forecast-outcomes` | Allen et al., *Nat Biotechnol* 2019 (FORECasT) | Open; redistribution varies |
| `be-hive-outcomes` | Arbab et al., *Cell* 2020 (BE-Hive) | Open; redistribution varies |
| `pridict2-library` | Mathis et al., *Nat Biotechnol* 2023 (PRIDICT2) | Open; redistribution varies |
| `guideseq-offtarget` | Tsai et al., *Nat Biotechnol* 2015 (GUIDE-seq) | Open; redistribution varies |

Because bulk redistribution terms differ per source, the fixtures committed here
are synthetic stand-ins (`synthetic: true`, `redistributable: false`); the loader
for real data goes through the consent-gated registry, exactly like the Phase 3
population datasets.

## Split philosophy: frozen, content-hashed, cross-context

A split is **immutable once published**. Each split file pins the membership of
its `train` / `val` / `test` folds and two hashes:

- a hash of the **dataset content** it was cut from — so a frozen split is
  invalidated the instant a label or input changes underneath it;
- a hash of the **split's own membership** — so the file cannot be silently
  edited.

`load_split()` recomputes and verifies **both** on read and raises
`SplitIntegrityError` on any mismatch. Changing the data — or the split — means
minting a new split *version* (e.g. `v2`); you never edit a published one.

The test folds are deliberately **cross-context**: a whole cell type / chromatin
context is held out into test, so the benchmark measures *generalization* rather
than memorization. Cross-cell-type generalization is a known weak spot for guide
models; making it the headline split keeps the benchmark honest about it.

## How to submit

1. Wrap your model as a `Scorer` (it must return a calibrated `Prediction`,
   never a bare float — see [the uncertainty contract](../../../docs/concepts/uncertainty.md)).
2. Run it through `run_benchmark(scorer, task, ...)`; each call returns a
   **signed, provenance-stamped** `BenchmarkResult`.
3. Package the results into a `Submission` with your **model card** (a name, a
   license, and a citation are mandatory) and add it to a `Leaderboard`. The
   board re-verifies every result signature and rejects any unsigned, edited, or
   uncarded entry.

```python
from datetime import UTC, datetime
from alleleforge.benchmark import (
    Leaderboard, ModelInfo, Submission, get_task, load_split, run_benchmark,
)

results = []
for name in ("cas9-efficiency", "pe-efficiency"):
    split, ds = load_split(name)
    results.append(run_benchmark(my_scorer, get_task(name), split=split, dataset=ds))

board = Leaderboard()
board.add(Submission(
    submitter="your-lab",
    model=ModelInfo(name="my-model", version="1.0", license="MIT", citation="…"),
    results=tuple(results),
    submitted_at=datetime.now(UTC),
))
print(board.render_markdown())
```

## Launch plan

- **Hosting:** a static leaderboard (`Leaderboard.render_html()`), HuggingFace
  Spaces / Polaris compatible, displaying each entry's accuracy metric,
  calibration (ECE), and split version.
- **External submissions:** accepted with a model card; results must verify their
  signatures. The split version is shown next to every score so cross-version
  comparisons are never silently mixed.
- **Lab outreach:** seed the board with the reference baseline and AlleleForge's
  own scorers, then invite the groups behind the source datasets to submit their
  models against the frozen cross-context splits.
