<div align="center">

# AlleleForge

**Variant in. Ranked CRISPR designs out.**

Design and compare SpCas9, base-editing, and prime-editing strategies in one
uncertainty-aware, population-aware workflow.

[![CI](https://github.com/clay-good/alleleforge/actions/workflows/ci.yml/badge.svg)](https://github.com/clay-good/alleleforge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

> [!WARNING]
> AlleleForge is a research tool, not a medical device. Its designs and off-target
> nominations are computational hypotheses that require experimental validation.

## Why AlleleForge

CRISPR design often means moving a variant through separate tools for guide selection,
efficiency scoring, outcome prediction, and off-target analysis. AlleleForge puts that
work behind one interface.

Give it a variant and a reference genome. It determines which editing chemistries can
make the change, generates candidates, predicts their outcomes, evaluates off-targets,
and returns one ranked menu with the evidence needed to compare them.

- **Compare editing strategies together.** Evaluate SpCas9 nuclease, ABE/CBE base
  editors, and prime editors through the same pipeline.
- **See likely outcomes alongside guide scores.** Candidates include predicted intended
  edits, indels, bystanders, and other byproducts relevant to the chemistry.
- **Account for human variation.** Add population frequencies, phased haplotypes, or a
  patient VCF to find off-target sites absent from the reference genome. Runs without
  those inputs are clearly labeled reference-only.
- **Keep uncertainty visible.** Predictions carry intervals, distribution checks, and an
  explicit calibration status.
- **Reproduce and audit results.** Reports record the reference, models, datasets,
  settings, seed, licenses, and content hashes used to produce them.
- **Move from design to review.** Export JSON, TSV, Parquet, HTML, PDF, and
  cloning-ready oligos from the same core library.

AlleleForge is available as a Python library, the `aforge` CLI, a web API and browser
interface, and the CRISPR-Bench evaluation harness.

## Quick start

AlleleForge requires Python 3.11 or 3.12. The project is currently an active alpha, so
install it from source:

```bash
git clone https://github.com/clay-good/alleleforge.git
cd alleleforge
python3 -m venv .venv
source .venv/bin/activate
make install
```

Turn a genomic variant into a ranked HTML report:

```bash
aforge design 'chr11:5227002:A>T' \
  --reference-fasta hg38.fa \
  --intent correct \
  --format html \
  --out report.html
```

Add population-aware off-target analysis by supplying allele frequencies:

```bash
aforge design 'chr11:5227002:A>T' \
  --reference-fasta hg38.fa \
  --gnomad gnomad.sites.tsv.gz \
  --populations afr,eur,eas \
  --format html \
  --out report.html
```

The same pipeline is available in Python:

```python
from alleleforge.design import design
from alleleforge.genome import ReferenceGenome

with ReferenceGenome("hg38.fa", build="hg38") as reference:
    menu = design("chr11:5227002:A>T", reference=reference)

print(menu.model_dump_json(indent=2))
```

Run `aforge --help` for variant resolution, cohort design, standalone off-target
search, result verification, model and dataset inspection, caching, and benchmarking.

## What goes in and what comes out

| Input | Output |
|---|---|
| Genomic coordinates, VCF records, genomic HGVS, ClinVar accessions, dbSNP IDs, or raw target sequences | Ranked candidates across every applicable editing chemistry |
| A local reference FASTA | Guides, pegRNAs, donor designs, and cloning oligos |
| Optional gnomAD-style frequencies, haplotypes, and patient variants | Reference, population, haplotype, and patient-specific off-target findings |
| Optional trained models and chromatin tracks | Efficiency and outcome predictions with provenance and uncertainty |

ClinVar, dbSNP, coding/protein HGVS, trained models, and external annotations require
their documented optional dependencies or data sources. The default pipeline uses
transparent, weight-free baselines. Network downloads and VEP lookups require explicit
consent.

For commercial work, set `ALLELEFORGE_MODEL_USE=commercial`. The license gate refuses
trained models that do not permit the use you declare.

## Learn more

- [Documentation](docs/index.md)
- [Population-aware off-target analysis](docs/concepts/population.md)
- [Uncertainty contract](docs/concepts/uncertainty.md)
- [Python API](docs/api/designer.md)
- [CLI reference](docs/api/cli.md)
- [Data and provenance](docs/data.md)
- [Runnable notebooks](examples/)
- [Current v1.0 work](SPEC_V2.md)

## Development

```bash
make ci
```

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), and report security
issues through the private process in [SECURITY.md](SECURITY.md).

## Responsible use

AlleleForge produces research hypotheses, not clinical decisions. Computational
off-target analysis does not replace experimental validation such as GUIDE-seq,
CHANGE-seq, or targeted amplicon sequencing. Review model cards and dataset provenance
before acting on a result, especially when a prediction is uncalibrated or outside its
training distribution.

AlleleForge runs locally by default and has no telemetry. Optional external services
state what data they send and require separate consent.

## License and citation

AlleleForge is released under the [MIT License](LICENSE). Wrapped models and tools keep
their upstream licenses, which the model and data registries record and enforce.

If you use AlleleForge in research, cite it using [CITATION.cff](CITATION.cff).
