# The `aforge` CLI

Phase 12 wraps the library in a thin, reproducible, config-driven command-line
interface built with [Typer](https://typer.tiangolo.com/). It holds **no business
logic** — every command resolves its inputs, calls the same functions the Python
API exposes, and can emit machine-readable JSON. Runs are reproducible from the
echoed config plus the global seed, and a provenance sidecar is written next to
any file output.

Install the CLI extra:

```bash
pip install "alleleforge[cli]"
```

## Commands

| Command | Purpose |
|---|---|
| `aforge resolve` | Normalize any input form and show the variant + class (debugging aid). |
| `aforge design` | Variant → ranked, multi-chemistry menu rendered to JSON/TSV/HTML/PDF. |
| `aforge batch` | Cohort design over a VCF or variant list — streaming, resumable, failure-isolated. |
| `aforge offtarget` | Standalone population-aware off-target search for a spacer. |
| `aforge data list` / `show` | Inspect the dataset registry (versions, licenses, provenance). |
| `aforge bench list` / `run` | List and run [CRISPR-Bench](benchmark.md) tasks against frozen splits. |
| `aforge bench leaderboard` | Aggregate signed result JSONs into the model-card-gated leaderboard. |

Global options (before the subcommand): `--seed`, `--reference`, `--cache-dir`,
`--verbose/-v`, `--version/-V`. Every command takes `--json` for machine-readable
output.

## Exit codes

Distinct, meaningful exit codes make the CLI scriptable:

| Code | Meaning |
|---|---|
| `0` | success |
| `2` | usage / input error (bad flag, unparseable variant, bad intent) |
| `3` | missing data (reference FASTA or config file not found, unknown dataset or split) |
| `4` | an unavailable model or feature |

## Examples

```bash
# Normalize any input form (1-based in, 0-based canonical out)
aforge resolve chr2:100:A>G --json

# Variant → ranked menu, written as an interactive HTML report + provenance sidecar
aforge design chr2:71:A>C \
    --reference-fasta hg38.fa --intent install \
    --populations afr,eur,eas --format html --out report.html

# Restrict chemistries and tune ranking weights (efficiency,cleanliness,safety,simplicity)
aforge design VCV000012345 --reference-fasta hg38.fa \
    --chemistry prime --weights 0.5,0.2,0.2,0.1 --json

# A reproducible run from a config file (CLI flags override the file)
aforge --seed 20240501 design chr2:71:A>C --reference-fasta hg38.fa --config run.toml --format tsv

# Cohort design: a whole VCF (cyvcf2 fast path) or a one-variant-per-line list.
# Streaming + resumable (--manifest), durable per-sample menus (--output-dir),
# a per-item TSV summary, and a per-worker reference for the parallel path.
aforge batch cohort.vcf.gz --reference-fasta hg38.fa --intent correct \
    --manifest run.jsonl --output-dir menus/ --summary-tsv summary.tsv --max-workers 8

# Standalone population-aware off-target for a spacer
aforge offtarget GACGGAGGCTAAGCGTCGCAA --reference-fasta hg38.fa --pam NGG --json

# Inspect the dataset registry
aforge data list
aforge data show gnomad --json

# CRISPR-Bench: list the tasks, then score the reference baseline on a frozen split
aforge bench list
aforge bench run cas9-efficiency --out cas9.json
aforge bench run offtarget-classification --out offtarget.json

# Aggregate signed results into the model-card-gated leaderboard (Markdown or HTML).
# Every result must verify its signature and carry a complete model card.
aforge bench leaderboard cas9.json offtarget.json --format html --out board.html
```

!!! note "Reproducibility"
    `aforge --seed S design ...` records the seed and resolved config in the
    menu's provenance block. The same seed and config produce byte-identical
    output modulo the UTC timestamp — and a `<output>.provenance.json` sidecar is
    written alongside every file output so any result can be re-derived.
