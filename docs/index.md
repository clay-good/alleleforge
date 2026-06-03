# AlleleForge

**Variant in, corrective edit out.**

AlleleForge is a variant-driven, multi-modality, uncertainty-aware CRISPR guide and edit design
framework spanning SpCas9 nuclease, base editors, and prime editors, with population- and
haplotype-aware off-target nomination and a public benchmark (CRISPR-Bench).

!!! warning "Research tool — not medical advice"
    AlleleForge produces ranked, explicitly *uncertain* design hypotheses. Every off-target
    nomination is **computational** and **must be experimentally validated**. It is not a medical
    device and provides no medical advice. See [Scope & responsible use](scope.md).

## What it does

You supply a variant (ClinVar accession, dbSNP rsID, HGVS, VCF record, raw coordinates, or a raw
target sequence). AlleleForge returns a ranked, safety-annotated menu of candidate edits across
every applicable chemistry, each carrying:

- a **calibrated uncertainty interval** on efficiency (never a bare float);
- a **predicted edit outcome** distribution (indels / bystanders / byproducts);
- a **population- and haplotype-aware off-target report**, ancestry-stratified by default.

## Build status

AlleleForge is built in ordered phases against [the specification](https://github.com/clay-good/alleleforge/blob/main/SPEC.md).
The foundations land before any chemistry-specific or ML code.

| Phase | Component | Status |
|---|---|:---:|
| 0 | Repo bootstrap, CI, packaging, Rust toolchain | done |
| 1 | Core domain types & schemas (`types/`) | done |
| 2 | Genome access & indexing | next |
| 3–15 | Data registry → chemistries → designer → report → CLI → web → benchmark → release | planned |

## The uncertainty contract in one snippet

```python
from alleleforge.types import Prediction, UncertaintyMethod

p = Prediction(
    value=0.72,
    interval=(0.61, 0.83),           # calibrated 80% predictive interval
    method=UncertaintyMethod.ENSEMBLE,
    in_distribution=True,
    calibrated=True,
)
assert p.interval[0] <= p.value <= p.interval[1]   # always holds
```

See the [uncertainty contract](concepts/uncertainty.md) and [population-aware safety](concepts/population.md)
concept pages, and the [core types reference](api/types.md).
