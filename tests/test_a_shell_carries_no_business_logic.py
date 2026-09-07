"""The cohort summary — a product — lived in the CLI, so only the CLI could make one.

The README says of both shells that they carry "no business logic of its own". The
per-item summary flattening and its TSV writer were in `cli/main.py`: about 170 lines
that turn a `CohortRunReport` into one row per patient and lead it with the research-use
disclaimer, the coordinate convention, the reference genome's identity and the seed.

That is a product, not plumbing. It is the file a run over a patient VCF gets forwarded
in, and a Python caller had to re-implement all of it — including the note block — while
`/api/batch` could not serve it at all. The single-design flat table went through exactly
this correction, on the argument that a flat table is what a pipeline reads. A per-patient
table is more pipeline-shaped than that one.

The check is deliberately narrow. A shell legitimately parses its own arguments, loads
files from paths, formats for a terminal and chooses exit codes. What it may not do is
*compute a result* that its siblings then cannot obtain.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from alleleforge.design import cohort_summary


def test_the_summary_is_importable_from_the_library() -> None:
    assert callable(cohort_summary.cohort_rows)
    assert callable(cohort_summary.cohort_to_tsv)
    assert Path(cohort_summary.__file__).parts[-3:] == (
        "alleleforge",
        "design",
        "cohort_summary.py",
    )


def test_a_python_caller_can_produce_the_cohort_table(tmp_path: Path) -> None:
    """The property the move exists for, exercised rather than asserted structurally."""
    from alleleforge.design.cohort import design_many
    from alleleforge.genome.reference import ReferenceGenome

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")

    report = design_many(
        ["chr2:71:A>C"],
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
    )
    tsv = cohort_summary.cohort_to_tsv(cohort_summary.cohort_rows(report), report.provenance)
    notes = [line for line in tsv.splitlines() if line.startswith("#")]
    body = [line for line in tsv.splitlines() if not line.startswith("#")]

    assert any("research tool" in note for note in notes), notes
    assert any("0-based" in note for note in notes), notes
    assert any("hg38" in note for note in notes), notes
    assert body[0].split("\t")[0] == "item_id"
    assert len(body) == 2, body


def test_the_cli_calls_the_library_rather_than_carrying_a_copy() -> None:
    """A second copy in the shell is the same defect with the tests still passing."""
    from alleleforge.cli import main as cli

    assert cli._batch_rows is cohort_summary.cohort_rows
    assert cli._batch_tsv is cohort_summary.cohort_to_tsv


@pytest.mark.parametrize("name", ["cohort_rows", "cohort_to_tsv"])
def test_the_moved_functions_kept_their_documentation(name: str) -> None:
    """A product's docstring is part of it; a move that drops it costs the caller more."""
    doc = inspect.getdoc(getattr(cohort_summary, name)) or ""
    assert len(doc) > 80, (name, doc)


def test_the_shell_did_not_keep_the_note_block() -> None:
    """The `#` notes are the part a re-implementer would get wrong, so they moved too."""
    source = Path(cohort_summary.__file__).read_text(encoding="utf-8")
    assert "RESEARCH_USE_DISCLAIMER" in source
    assert "COORDINATE_NOTE" in source

    cli_source = (Path(__file__).resolve().parents[1] / "src/alleleforge/cli/main.py").read_text()
    assert "def _batch_tsv" not in cli_source, "the CLI grew its own copy back"
    assert "def _batch_rows" not in cli_source
