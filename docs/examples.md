# Examples & tutorials

Three runnable notebooks walk the AlleleForge journey end to end. Each is
**self-contained** — it builds a small synthetic locus and runs against the
weight-free stub models — so they execute in CI on every push and are reproducible
without downloading a genome or model weights. Swap the synthetic inputs for a real
hg38 reference, a gnomAD database, and trained weights through the model zoo, and
the call shapes are identical.

| Notebook | What it shows |
|---|---|
| [`01_clinvar_to_design.ipynb`](https://github.com/clay-good/alleleforge/blob/main/examples/01_clinvar_to_design.ipynb) | The canonical journey: a variant → ranked **prime-editing** design, demonstrating all four axes (variant input, calibrated ML efficiency with an honest OOD flag, intended-vs-byproduct outcome, population-aware off-target). |
| [`02_population_offtarget.ipynb`](https://github.com/clay-good/alleleforge/blob/main/examples/02_population_offtarget.ipynb) | The **reference-bias** case (`rs114518452`, Cancellieri & Pinello, *Nat Genet* 2023): a reference-only scan is blind to a population allele that creates a de-novo PAM; the population-aware engine nominates it and reports it **ancestry-stratified**. |
| [`03_batch_vcf.ipynb`](https://github.com/clay-good/alleleforge/blob/main/examples/03_batch_vcf.ipynb) | **Cohort-scale** design: resolve a batch of variants, design each across every eligible chemistry, and reduce the per-variant menus to one auditable summary table with provenance. |

## Running the notebooks

```bash
pip install -e ".[dev,cli]" "pyfaidx>=0.8" "pyliftover>=0.4"
pytest --nbmake examples/ --no-cov          # execute all three, as CI does
# or open them interactively
jupyter lab examples/
```

## The shortest possible path

The notebooks expand on what is, at its core, a single call:

```python
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent

reference = ReferenceGenome("hg38.fa", build="hg38")
menu = design("VCV000012345", reference=reference, intent=EditIntent.CORRECT,
              populations=["afr", "eur", "eas"])

best = menu.best
print(best.chemistry.value, best.efficiency.value, best.efficiency.interval)
```

`design()` resolves the variant, routes it to every eligible chemistry, enumerates
and scores candidates with calibrated uncertainty, runs population-aware
off-target, ranks the result, and attaches full provenance — the same core the CLI
and web service call.
