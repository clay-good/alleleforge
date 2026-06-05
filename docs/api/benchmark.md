# CRISPR-Bench reference

`alleleforge.benchmark` (Phase 14) is AlleleForge's sister deliverable: a
standardized, field-level benchmark for guide-design models. It pins **versioned
datasets**, **frozen content-hashed splits**, a fixed **five-task contract**, a
metric battery with **calibration (ECE) required on every task**, a runner that
turns any [`Scorer`](scoring.md) into a *signed* result, and a model-card-gated
leaderboard.

Everything here is pure-Python and dependency-light so it runs in the same CI as
the core library. The datasets shipped in the repository are **small synthetic
fixtures**; the real public corpora (Rule Set 3, FORECasT, BE-Hive, PRIDICT2,
GUIDE-seq) are fetched at runtime through the consent-gated registry.

!!! note "Why calibration is a first-class metric"
    A model that is accurate but overconfident is dangerous for edit design. Every
    task reports `ece` alongside its accuracy metric, computed in a
    kind-appropriate way (interval coverage for regression, binned reliability for
    classification, predicted-mode reliability for distributions). See
    [The uncertainty contract](../concepts/uncertainty.md).

## The five tasks

| Task | Kind | Label | Primary metric |
|---|---|---|---|
| `cas9-efficiency` | regression | cleavage efficiency `[0, 1]` | Spearman |
| `cas9-outcome` | distribution | indel outcome frequencies | KL divergence (↓) |
| `be-outcome` | distribution | base-edit outcome frequencies | KL divergence (↓) |
| `pe-efficiency` | regression | pegRNA efficiency `[0, 1]` | Spearman |
| `offtarget-classification` | classification | 0/1 bona-fide off-target | AUROC |

## Running the benchmark

```python
from alleleforge.benchmark import build_baseline, load_split, run_benchmark, get_task

task = get_task("cas9-efficiency")
split, dataset = load_split("cas9-efficiency")        # frozen, hash-verified on read
scorer = build_baseline(task, split, dataset)         # or any Scorer of your own
result = run_benchmark(scorer, task, split=split, dataset=dataset)
print(result.primary_metric, result.primary_value, result.metrics["ece"])
assert result.verify_signature()                       # content-addressed result
```

From the CLI:

```bash
aforge bench list                       # the five tasks, datasets, and metrics
aforge bench run cas9-efficiency        # score the reference baseline
aforge bench run pe-efficiency --out result.json --json
```

## Tasks & examples

::: alleleforge.benchmark.tasks

## Datasets

::: alleleforge.benchmark.datasets

## Frozen splits

::: alleleforge.benchmark.splits

## Metrics

::: alleleforge.benchmark.metrics

## Runner

::: alleleforge.benchmark.runner

## Reference baseline

::: alleleforge.benchmark.baseline

## Leaderboard

::: alleleforge.benchmark.leaderboard
