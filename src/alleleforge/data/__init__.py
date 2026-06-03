"""Data registry & population datasets (Phase 3).

License-aware, versioned, consent-gated access to the datasets AlleleForge's
population-aware analysis depends on: ClinVar (:mod:`.clinvar`), gnomAD
(:mod:`.gnomad`), 1000 Genomes (:mod:`.thousand_genomes`) and HGDP (:mod:`.hgdp`)
phased haplotypes (:mod:`.haplotypes`), dbSNP (:mod:`.dbsnp`), and GENCODE/ENCODE
annotations (:mod:`.annotations`). The :mod:`.registry` is the single choke point
for acquisition: it never vendors a non-redistributable source and never fetches
an artifact it cannot checksum-verify.

Every parser reads small plain-text fixtures with no heavy dependency, so the
test suite runs without ``pysam``/``cyvcf2`` and never opens a real release.
"""

from __future__ import annotations

from alleleforge.data.annotations import EncodeTracks, Gene, GeneModels
from alleleforge.data.clinvar import (
    ClinicalSignificance,
    ClinVarDB,
    ClinVarRecord,
    accession_from_variation_id,
)
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.data.gnomad import GNOMAD_POPULATIONS, GnomadDB, PopulationFrequency
from alleleforge.data.haplotypes import Haplotype, HaplotypePanel
from alleleforge.data.hgdp import HGDP
from alleleforge.data.registry import (
    DEFAULT_REGISTRY,
    ChecksumError,
    ConsentError,
    DatasetDescriptor,
    DatasetRegistry,
)
from alleleforge.data.thousand_genomes import ThousandGenomes

__all__ = [
    "DEFAULT_REGISTRY",
    "GNOMAD_POPULATIONS",
    "HGDP",
    "ChecksumError",
    "ClinVarDB",
    "ClinVarRecord",
    "ClinicalSignificance",
    "ConsentError",
    "DatasetDescriptor",
    "DatasetRegistry",
    "DbSnpDB",
    "EncodeTracks",
    "Gene",
    "GeneModels",
    "GnomadDB",
    "Haplotype",
    "HaplotypePanel",
    "PopulationFrequency",
    "ThousandGenomes",
    "accession_from_variation_id",
]
