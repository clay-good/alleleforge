## MODIFIED Requirements

### Requirement: Population augmentation nominates created or strengthened sites

Population augmentation SHALL re-scan a window around each gnomAD variant on its
alternate allele and nominate hits the variant **creates or strengthens**, where
"strengthens" means the alt hit is more dangerous than any reference hit at the same
placement judged by the **specificity score** (CFD), not merely by a lower edit count —
so a variant that upgrades a weak PAM (e.g. `NAG`→`NGG`) or otherwise raises the score at
an unchanged edit count is reported. A nominated site overlaps the variant locus and is
annotated with the causal allele, carrying populations above the MAF threshold, and
per-ancestry frequency.

#### Scenario: De novo PAM from a minor allele
- **WHEN** the reference protospacer is followed by a non-PAM but a gnomAD variant
  creates a valid PAM
- **THEN** reference-only nomination returns zero sites and population-aware nomination
  returns one site annotated with the causal allele and its ancestry frequencies

#### Scenario: A variant upgrades a weak PAM without changing the edit count
- **WHEN** a minor allele changes a low-stringency PAM (`NAG`) into a canonical PAM
  (`NGG`) while the protospacer edit count is unchanged, raising the site's CFD above the
  reporting threshold
- **THEN** the strengthened site is nominated and attributed to the causal allele, rather
  than discarded because its edit count did not fall
