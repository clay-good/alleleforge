"""Two CLI refusals offered a Python keyword argument as the remedy.

    $ aforge offtarget ACGT… --scorer mit
    error: the MIT score is undefined for bulged alignments; set dna_bulges=0 and
    rna_bulges=0, or use the CFD scorer

    $ aforge resolve VCV000012345
    error: resolving a ClinVar accession requires a clinvar= database

Neither `dna_bulges=` nor `clinvar=` is something a command line can be given. The first
is worse than it looks: the default bulge budget is non-zero, so that refusal is what a
caller meets the *first* time they pick one of the three advertised scorers, and the
check was deliberately moved out of the CLI into the engine so that every caller would
reach it — which is right, and makes a Python-only spelling reach further.

This project's standing rule is that a refusal names the remedy. A remedy belonging to a
different surface is half of one. Messages raised in the library may name Python spellings
*as well*, and the two here now name both.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

#: A `keyword=value` fragment: the shape of a Python argument offered as prose.
_PYTHON_KEYWORD = re.compile(r"(?<![\w-])[a-z_]{3,}=(?!=)\S")


def _unquoted(message: str) -> str:
    """Return ``message`` with backticked spans removed.

    A refusal may quote a Python spelling *as code* beside the command-line one — that is
    the fix, not the defect. Stripping the spans first states that rule directly; a
    lookbehind only excluded the first keyword inside a span like
    `` `dna_bulges=0, rna_bulges=0` ``.
    """
    return re.sub(r"`[^`]*`", " ", message)


#: CLI invocations that fail, with the flag a caller would use to act on each. Every one
#: is a refusal reachable from a command line with defaults or a single documented flag.
_FAILING: list[tuple[str, list[str], str]] = [
    ("mit-with-bulges", ["offtarget", "ACCTGAAGACTTACGCATAC", "--scorer", "mit"], "--dna-bulges"),
    ("clinvar-accession", ["resolve", "VCV000012345"], "chrom:pos:ref>alt"),
    ("dbsnp-rsid", ["resolve", "rs334"], "chrom:pos:ref>alt"),
]


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "ACCTGAAGACTTACGCATACTGG" + ("ACGT" * 200) + "\n")
    return path


def _run(fasta: Path, argv: list[str]) -> str:
    result = CliRunner().invoke(app, [*argv, "--reference-fasta", str(fasta)])
    assert result.exit_code != 0, result.output
    return result.output + result.stderr


@pytest.mark.parametrize("name, argv, remedy", _FAILING, ids=[c[0] for c in _FAILING])
def test_the_refusal_names_a_remedy_the_command_line_has(
    fasta: Path, name: str, argv: list[str], remedy: str
) -> None:
    assert remedy in _run(fasta, argv), name


@pytest.mark.parametrize("name, argv, remedy", _FAILING, ids=[c[0] for c in _FAILING])
def test_the_refusal_does_not_offer_a_bare_python_keyword(
    fasta: Path, name: str, argv: list[str], remedy: str
) -> None:
    message = _run(fasta, argv)
    offenders = _PYTHON_KEYWORD.findall(_unquoted(message))
    assert not offenders, (name, offenders, message)


def test_the_pattern_tells_the_two_spellings_apart() -> None:
    """A message may quote the Python form beside the CLI one; that is the fix."""
    ok = "set both budgets to zero (`--dna-bulges 0 --rna-bulges 0`), or "
    ok += "`dna_bulges=0, rna_bulges=0` from Python"
    assert not _PYTHON_KEYWORD.findall(_unquoted(ok)), ok
    bare = "set dna_bulges=0 and rna_bulges=0"
    assert _PYTHON_KEYWORD.findall(_unquoted(bare)) == ["dna_bulges=0", "rna_bulges=0"]


def test_the_named_remedy_actually_works(fasta: Path) -> None:
    """A remedy nobody tried is a guess. This one is run."""
    result = CliRunner().invoke(
        app,
        [
            "offtarget",
            "ACCTGAAGACTTACGCATAC",
            "--reference-fasta",
            str(fasta),
            "--scorer",
            "mit",
            "--dna-bulges",
            "0",
            "--rna-bulges",
            "0",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "scorer MIT" in result.output
