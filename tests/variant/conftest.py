"""Fixtures for the variant-resolver tests.

A tiny synthetic ``chr2`` reference is written to a temp FASTA so the resolver's
left-alignment and reference-validation run against a real
:class:`ReferenceGenome` (Phase 2) without any genome-scale file. The data DBs
reuse the Phase 3 synthetic fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.clinvar import ClinVarDB
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.genome.reference import ReferenceGenome

#: chr2 landmarks (0-based):
#:   pos 5  = 'A'                  (SNV / coordinate tests)
#:   pos 12 = 'T'                  (insertion anchor)
#:   pos 13 = 'C', 14-16 = 'AAA'   (homopolymer for indel left-alignment)
CHR2_SEQ = "TTTTTACGTACGTCAAAGTTGGCCAATTGG"

_DATA_FIXTURES = Path(__file__).parents[1] / "data" / "fixtures"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    """Return an open :class:`ReferenceGenome` over the synthetic chr2."""
    fasta = tmp_path / "tiny.fa"
    fasta.write_text(f">chr2\n{CHR2_SEQ}\n")
    return ReferenceGenome(fasta, build="hg38")


@pytest.fixture
def clinvar_db() -> ClinVarDB:
    """Return the ClinVar DB parsed from the Phase 3 fixture."""
    return ClinVarDB.from_vcf(_DATA_FIXTURES / "clinvar.vcf")


@pytest.fixture
def dbsnp_db() -> DbSnpDB:
    """Return the dbSNP DB parsed from the Phase 3 fixture."""
    return DbSnpDB.from_tsv(_DATA_FIXTURES / "dbsnp.tsv")
