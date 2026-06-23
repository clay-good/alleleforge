# Distribution plan — getting AlleleForge into scientific hands

_Status as of 2026-06-23. Sequence matters: do NOT distribute widely until at least
one real model is wired + validated (see [`readiness-assessment.md`](readiness-assessment.md)).
Distribution amplifies whatever you ship._

## Sequencing principle

1. Build scientific substance first (model-integration).
2. Then Tier 1 (discovery infra) — low effort, high payoff.
3. Then Tier 2 (credibility / academic credit).
4. Then Tier 3 (community announcement) once Tiers 1–2 exist to point at.

PyPI is table stakes, **not** a growth channel — bench scientists install from conda.

## Tier 1 — discovery infrastructure (do regardless)

- **Bioconda** — *the* life-science distribution channel. A recipe yields
  `conda install -c bioconda alleleforge` + an automatic BioContainer (Docker/
  Singularity). Far more important than PyPI for bench scientists.
  - Action: write a `meta.yaml` recipe, submit PR to `bioconda/bioconda-recipes`.
  - Ref: https://pmc.ncbi.nlm.nih.gov/articles/PMC11070151/
- **bio.tools (ELIXIR registry)** — canonical discovery portal; gives a citable
  registry entry + RRID. Author a `biotoolsSchema` entry.
  - Refs: https://bio.tools/ ,
    https://biotools.readthedocs.io/en/latest/community_specific_guidelines.html
- **Zenodo DOI** — `.zenodo.json` already exists. Turn on the GitHub–Zenodo
  integration so every release gets a citable DOI. Minimum bar for citable software.
- **`awesome-CRISPR` list** — one PR to https://github.com/davidliwei/awesome-CRISPR
  puts it in the list researchers browse when surveying CRISPR tooling.

## Tier 2 — credibility / academic credit (after the science is real)

- **bioRxiv preprint** — draft already exists at `docs/paper/preprint.md`. Post once
  ≥1 model is wired + validated and the `[pending R1]` numbers are filled in. This is
  how the field announces tools and becomes citable.
- **JOSS (Journal of Open Source Software)** — peer-reviewed software paper, great for
  academic credit. **Hard gates:**
  1. Repo must be **public for 6+ months with active development across that period** —
     a freshly-public repo is rejected. **Start the clock now.**
  2. 2026 criteria emphasize **demonstrable research impact** (anti-AI-slop) — helps to
     have real users/citations first.
  3. JOSS won't review a wrapper-of-pretrained-models alone; the in-scope contribution
     is the **framework** (uncertainty contract, population-aware off-target, benchmark
     harness).
  - Refs: https://joss.readthedocs.io/en/latest/submitting.html ,
    https://joss.readthedocs.io/en/latest/review_criteria.html

## Tier 3 — community announcement (last)

- **Biostars** (https://www.biostars.org/), **r/bioinformatics**, **SEQanswers** —
  lead with the population-aware off-target engine (the part that works).
- **Bluesky / Mastodon bioinformatics communities**, lab mailing lists.

## Pre-flight before listing anywhere

- Cut a real `0.1.0` (currently `0.1.0.dev0` / Alpha) so the version signals "usable".
- Publish to PyPI (builds + `twine check` already pass) — table stakes.
- Ensure README honestly labels heuristic vs real scorers.

## Sources

- Bioconda (PMC): https://pmc.ncbi.nlm.nih.gov/articles/PMC11070151/
- bio.tools: https://bio.tools/ ; curation: https://biotools.readthedocs.io/en/latest/community_specific_guidelines.html
- JOSS submitting: https://joss.readthedocs.io/en/latest/submitting.html ; criteria: https://joss.readthedocs.io/en/latest/review_criteria.html
- awesome-CRISPR: https://github.com/davidliwei/awesome-CRISPR
- Biostars: https://www.biostars.org/
- CRISPR tools review (PMC): https://pmc.ncbi.nlm.nih.gov/articles/PMC10094584/
