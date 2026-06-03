"""Shared fixtures for the genome tests.

The bundled FASTA is copied into a temporary directory before it is opened, so
pyfaidx writes its ``.fai`` index next to the *copy* rather than polluting the
checked-in fixtures.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_fasta(tmp_path: Path) -> Path:
    """Return a writable copy of the tiny synthetic FASTA."""
    dest = tmp_path / "tiny.fasta"
    shutil.copy(FIXTURES / "tiny.fasta", dest)
    return dest


@pytest.fixture
def forward_chain() -> Path:
    """Return the path to the chr1 -> chrA (+200) chain file."""
    return FIXTURES / "forward.chain"


@pytest.fixture
def reverse_chain() -> Path:
    """Return the path to the chrA -> chr1 (-200) chain file."""
    return FIXTURES / "reverse.chain"
