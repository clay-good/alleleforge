"""Shared fixtures for the data tests: paths to the synthetic dataset fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def clinvar_vcf() -> Path:
    """Return the path to the synthetic ClinVar VCF."""
    return FIXTURES / "clinvar.vcf"


@pytest.fixture
def gnomad_tsv() -> Path:
    """Return the path to the synthetic gnomAD sites TSV."""
    return FIXTURES / "gnomad.sites.tsv"


@pytest.fixture
def haplotypes_tsv() -> Path:
    """Return the path to the synthetic phased-haplotype TSV."""
    return FIXTURES / "haplotypes.tsv"


@pytest.fixture
def dbsnp_tsv() -> Path:
    """Return the path to the synthetic dbSNP TSV."""
    return FIXTURES / "dbsnp.tsv"


@pytest.fixture
def gencode_gtf() -> Path:
    """Return the path to the synthetic GENCODE GTF."""
    return FIXTURES / "gencode.gtf"


@pytest.fixture
def encode_bedgraph() -> Path:
    """Return the path to the synthetic ENCODE bedGraph."""
    return FIXTURES / "encode.bedgraph"
