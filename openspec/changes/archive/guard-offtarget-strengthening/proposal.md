# Guard off-target strengthening and aggregate honesty

## Why

Population/haplotype-aware off-target nomination is AlleleForge's differentiator, and a
prior change (`bulletproof-offtarget-nomination`, archived) fixed its coordinate and
alignment correctness. Four gaps remain that let the differentiator *under-state* risk or
report an *optimistic* summary — the two failure modes a safety tool must never have:

1. **"Strengthened" is defined by edit count only.** Population and haplotype passes
   nominate an alt-allele hit only when `h.edits < prior` (`offtarget/population.py:105`,
   `offtarget/haplotype.py:153-155`), where `edits` counts protospacer mismatches/bulges
   and excludes the PAM. A minor allele that upgrades a weak `NAG` PAM to canonical `NGG`
   leaves the protospacer edit count unchanged, so the site is dropped — even though CFD
   jumps from **0.0715** (sub-threshold, invisible to the reference scan) to **0.2759** (a
   real, reportable off-target). This is a pure false-negative in exactly the de-novo
   scenario the population pass exists to catch.
2. **The genome-wide aggregate omits the off-target tail.** `specificity_score =
   1/(1 + Σ sᵢ)` (`types/offtarget.py:129-141`) sums only sites that already cleared the
   reporting threshold (`engine.py:307` filters before `report.sites`), so a guide with 5
   near-threshold off-targets and one with 500 can report the same specificity. The Hsu/
   CRISPOR aggregate it claims parity with sums over *all* candidate sites.
3. **CFD is applied to any spacer length under a "published" label.** `cfd_score` guards
   only `len(spacer) == len(protospacer)` (`offtarget/scoring.py:188-203`); the published
   matrix covers positions 1–20 only, so a mismatch at index ≥20 returns weight 0.0 and
   CFD collapses to 0 for a 21+-nt spacer, while a truncated guide is scored in the wrong
   register — yet the report still labels the matrix `doench-2016-cfd`. MIT honestly
   refuses off-length input (`scoring.py:224-225`); CFD silently fabricates one.
4. **The aggregates are frequency-blind.** `worst_score` and `specificity_score` read
   `s.score` only (`types/offtarget.py:125-141`); a 0.1%-MAF off-target weighs the same as
   a universal reference one, conflating the exact distinction the population pass makes.

## What Changes

- Nominate an alt-allele hit when it is created **or its specificity score exceeds** the
  best reference hit at the same placement — not only when its edit count is strictly
  lower — so a PAM upgrade (or any equal-edit CFD gain) is reported and attributed.
- Aggregate `specificity_score` over the **full set of nominated in-budget sites**, or
  explicitly document it as threshold-survivor-only and not CRISPOR-comparable.
- **Length-guard the published CFD scorer** to a 20-nt spacer (raise or record CFD as
  inapplicable), and reflect inapplicability in the recorded matrix identity.
- Expose a **frequency-aware aggregate** (expected off-target burden) alongside the
  frequency-blind worst-case, so rare and universal off-targets are distinguishable.

## Impact

- Specs: `offtarget-nomination` (MODIFIED strengthening definition), `offtarget-scoring`
  (ADDED full-set aggregate, CFD length guard, frequency-aware aggregate).
- Code: `offtarget/population.py`, `offtarget/haplotype.py`, `offtarget/scoring.py`,
  `offtarget/engine.py`, `types/offtarget.py`.
- Tests: a PAM-upgrade (`NAG`→`NGG`) variant nominates the strengthened site; specificity
  reflects sub-threshold tail; CFD raises/records on a 19- and 21-nt spacer; the
  frequency-aware aggregate separates a MAF-floor hit from a universal one. Some reported
  specificity numbers change — regenerate affected off-target goldens.
