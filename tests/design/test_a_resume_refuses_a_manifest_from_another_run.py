"""Resume skipped work under inputs that would have produced different answers.

Resume keys on `item_id`, which is the *request*. The same request under different
result-determining inputs is a different run, and the manifest header has recorded what
the first run was since it was introduced — nothing ever read it back.

Demonstrated with the case that motivated it: the same cohort of ClinVar accessions
against a second release that places one of them at a different locus. Every item was
"already done", the command exited 0, and the summary was written with no rows — so the
user's artifact is designed against the release they did not name, and nothing in it says
so. A different genome, a different seed and a different intent are the same hazard.

Refusing rather than warning: the alternative result is silently a mixture of two runs,
and both ways forward — `--no-resume`, or a new manifest — are one flag away. The refusal
names them, and this file runs them, because a remedy nobody tried is a guess.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.config import Settings
from alleleforge.data.clinvar import ClinVarDB
from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.provenance import DatasetVersion

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 30


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _release(tmp_path: Path, name: str, pos: int, ref: str, alt: str) -> ClinVarDB:
    """A one-record ClinVar release, pinned the way the CLI pins a supplied file."""
    vcf = tmp_path / f"{name}.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        f"9\t{pos}\t12\t{ref}\t{alt}\t.\t.\tCLNSIG=Pathogenic\n"
    )
    db = ClinVarDB.from_vcf(vcf)
    db.dataset_version = DatasetVersion(  # type: ignore[attr-defined]
        name="clinvar", version=f"sha256:{name}", sha256=name * 8, caller_supplied=True
    )
    return db


def _run(
    reference: ReferenceGenome, manifest: Path, clinvar: ClinVarDB, **kwargs: object
) -> object:
    return design_many(
        ["VCV000000012"],
        reference=reference,
        manifest_path=manifest,
        run_offtarget=False,
        clinvar=clinvar,
        **kwargs,
    )


def test_a_second_release_is_refused_rather_than_silently_skipped(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    assert _SEQ[102] == "G" and _SEQ[122] == "G"
    manifest = tmp_path / "run.jsonl"
    first = _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    assert first.succeeded == 1  # type: ignore[attr-defined]

    with pytest.raises(ValueError) as excinfo:
        _run(reference, manifest, _release(tmp_path, "b", 123, "G", "A"))
    message = str(excinfo.value)
    assert "clinvar sha256:a" in message and "clinvar sha256:b" in message, message
    # Readable, not a wall of `None`s: the dicts are rendered as name + version.
    assert "'source_url'" not in message, message
    assert "--no-resume" in message, message


def test_the_same_inputs_still_resume(reference: ReferenceGenome, tmp_path: Path) -> None:
    """The refusal must not cost the feature it guards."""
    manifest = tmp_path / "run.jsonl"
    release = _release(tmp_path, "a", 103, "G", "A")
    _run(reference, manifest, release)
    again = _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    assert again.skipped == 1 and again.total == 0  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("seed", {"settings": Settings(seed=999)}),
        ("intent", {"intent": "knock_out"}),
    ],
)
def test_other_result_determining_changes_are_refused_too(
    field: str, kwargs: dict[str, object], reference: ReferenceGenome, tmp_path: Path
) -> None:
    from alleleforge.types.edit import EditIntent

    if "intent" in kwargs:
        kwargs = {"intent": EditIntent.KNOCK_OUT}
    manifest = tmp_path / "run.jsonl"
    release = _release(tmp_path, "a", 103, "G", "A")
    _run(reference, manifest, release)
    with pytest.raises(ValueError, match=field):
        _run(reference, manifest, release, **kwargs)


def test_the_remedy_the_refusal_names_works(reference: ReferenceGenome, tmp_path: Path) -> None:
    """`resume=False` on the same manifest designs the item under the new release."""
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    report = _run(reference, manifest, _release(tmp_path, "b", 123, "G", "A"), resume=False)
    assert report.succeeded == 1  # type: ignore[attr-defined]
    (item,) = report.items  # type: ignore[attr-defined]
    assert item.summary["variant"] == "chr9:122:G>A", item.summary


def test_a_manifest_with_no_header_is_still_resumable(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """A manifest from before the header existed must not become unusable."""
    manifest = tmp_path / "old.jsonl"
    manifest.write_text(json.dumps({"item_id": "VCV000000012", "status": "ok"}) + "\n")
    report = _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    assert report.skipped == 1  # type: ignore[attr-defined]
