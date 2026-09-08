"""A cohort's two durable artifacts did not say which variant they were about.

`item_id` is the string the user typed. For the two database input forms it names no
locus at all — `VCV000000012` is a row a reader cannot place in the genome, and two
ClinVar releases can legitimately place it differently — and a coordinate is no safer,
since left-alignment routinely moves an indel away from the position that was typed.

So the summary TSV, the file a whole run gets forwarded in, identified each row only by
an input string, and the per-item menu JSON beside it recorded no variant either:
`build_report` takes the variant from *its* caller, which is why the single-design path
looked complete while the cohort had nowhere to get it from. `RankedMenu` now carries the
resolved variant, which is the one place both artifacts can read it.

The run header had the matching document-level gap. It pinned the reference genome's
shape and nothing else, while every per-item menu recorded the datasets it read — so a
cohort resolved through a ClinVar release could not say which release chose its loci.
Per-item honesty does not accumulate into document honesty: nobody opens 500 menus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.clinvar import ClinVarDB
from alleleforge.design.cohort import design_many
from alleleforge.design.cohort_summary import cohort_rows, cohort_to_tsv
from alleleforge.genome.reference import ReferenceGenome

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 30


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    return ReferenceGenome(fasta, build="hg38")


@pytest.fixture
def clinvar(tmp_path: Path) -> ClinVarDB:
    vcf = tmp_path / "clinvar.vcf"
    assert _SEQ[102] == "G"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "9\t103\t12\tG\tA\t.\t.\tCLNSIG=Pathogenic\n"
    )
    db = ClinVarDB.from_vcf(vcf)
    db.dataset_version = _descriptor()  # type: ignore[attr-defined]
    return db


def _descriptor() -> object:
    from alleleforge.types.provenance import DatasetVersion

    return DatasetVersion(name="clinvar", version="sha256:deadbeef", sha256="deadbeef")


def _run(reference: ReferenceGenome, **kwargs: object) -> object:
    return design_many(
        ["VCV000000012", "chr9:103:G>A"], reference=reference, run_offtarget=False, **kwargs
    )


def test_every_row_names_the_variant_it_designed_against(
    reference: ReferenceGenome, clinvar: ClinVarDB
) -> None:
    report = _run(reference, clinvar=clinvar)
    rows = cohort_rows(report)
    by_id = {r["item_id"]: r for r in rows}
    # The accession is the case `item_id` cannot answer, and both inputs are the same
    # variant — which the table could not previously show.
    assert by_id["VCV000000012"]["variant"] == "chr9:102:G>A", by_id
    assert by_id["chr9:103:G>A"]["variant"] == "chr9:102:G>A", by_id
    header = next(line for line in cohort_to_tsv(rows).splitlines() if not line.startswith("#"))
    assert header.split("\t")[:2] == ["item_id", "variant"], header


def test_a_failed_row_leaves_the_column_empty_rather_than_guessing(
    reference: ReferenceGenome,
) -> None:
    """An item that never resolved has no variant, and must not borrow its input."""
    report = design_many(["chr9:103:T>A"], reference=reference, run_offtarget=False)
    (row,) = cohort_rows(report)
    assert row["status"] == "error"
    assert row["variant"] is None, row


def test_the_run_header_pins_the_datasets_its_items_read(
    reference: ReferenceGenome, clinvar: ClinVarDB
) -> None:
    report = _run(reference, clinvar=clinvar)
    names = [d["name"] for d in report.provenance["datasets"]]
    assert "clinvar" in names, report.provenance["datasets"]
    notes = [
        line
        for line in cohort_to_tsv(cohort_rows(report), report.provenance).splitlines()
        if line.startswith("#")
    ]
    assert any("clinvar sha256:deadbeef" in line for line in notes), notes


def test_a_run_that_read_no_pinned_dataset_says_so_rather_than_omitting_the_line(
    reference: ReferenceGenome,
) -> None:
    """An absent line and "nothing was pinned" are different facts about a run."""
    report = design_many(["chr9:103:G>A"], reference=reference, run_offtarget=False)
    tsv = cohort_to_tsv(cohort_rows(report), report.provenance)
    assert any(line.startswith("# datasets:") for line in tsv.splitlines()), tsv


@pytest.mark.parametrize("workers", [1, 4])
def test_the_dataset_pin_does_not_depend_on_how_many_workers_ran(
    workers: int, tmp_path: Path, clinvar: ClinVarDB
) -> None:
    """A performance flag must not change a byte-reproducible artifact."""
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    # The parallel path opens a reference per worker, so it takes a factory rather than
    # an open handle (pyfaidx is not thread-safe to share).
    report = design_many(
        ["VCV000000012", "chr9:103:G>A", "chr9:123:G>A"],
        reference_factory=lambda: ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
        clinvar=clinvar,
        max_workers=workers,
    )
    assert [d["name"] for d in report.provenance["datasets"]] == sorted(
        d["name"] for d in report.provenance["datasets"]
    )
    assert "clinvar" in [d["name"] for d in report.provenance["datasets"]]
