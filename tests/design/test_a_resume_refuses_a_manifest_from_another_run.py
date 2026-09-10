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
    """A *new* manifest with `resume=False` designs the item under the new release.

    The remedy used to read "re-run with `--no-resume`", on this manifest — which
    appended a second record per item under the first run's `_run` header, so the file
    described one run and contained two and a later resume would skip both without
    choosing. `--no-resume` into an existing manifest is refused now, and the remedy says
    to point `--manifest` at a new file, which is what this checks.
    """
    manifest = tmp_path / "run.jsonl"
    _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    fresh = tmp_path / "rerun.jsonl"
    report = _run(reference, fresh, _release(tmp_path, "b", 123, "G", "A"), resume=False)
    assert report.succeeded == 1  # type: ignore[attr-defined]
    (item,) = report.items  # type: ignore[attr-defined]
    assert item.summary["variant"] == "chr9:122:G>A", item.summary
    # One run's records, in one file, under one header.
    assert len([line for line in fresh.read_text().splitlines() if '"item_id"' in line]) == 1


def test_a_manifest_with_no_header_is_still_resumable(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """A manifest from before the header existed must not become unusable."""
    manifest = tmp_path / "old.jsonl"
    manifest.write_text(json.dumps({"item_id": "VCV000000012", "status": "ok"}) + "\n")
    report = _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    assert report.skipped == 1  # type: ignore[attr-defined]


def test_an_empty_manifest_file_is_not_a_refusal(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """A run killed before its first write leaves exactly this."""
    manifest = tmp_path / "run.jsonl"
    manifest.write_text("")
    report = _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))
    assert report.succeeded == 1  # type: ignore[attr-defined]


def test_a_corrupt_first_line_still_reaches_the_corrupt_manifest_refusal(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """Reading the header leniently must not weaken the check after it.

    `_run_header` shrugs at a first line it cannot parse, because a manifest without a
    header is legitimate. That must not turn a *corrupt* manifest into a silently
    header-less one: skipping a bad line would silently recompute or silently drop an
    item, which is what the reader refuses on.
    """
    manifest = tmp_path / "run.jsonl"
    manifest.write_text("{not json\n" + json.dumps({"item_id": "x", "status": "ok"}) + "\n")
    with pytest.raises(ValueError, match="corrupt"):
        _run(reference, manifest, _release(tmp_path, "a", 103, "G", "A"))


def test_a_second_genome_of_the_same_shape_is_caught(tmp_path: Path) -> None:
    """The weakness the off-target cache key had, one layer up.

    `_reference_snapshot` pins contig names and lengths and says so: it is a *shareable*
    descriptor, so it cannot carry a local path or afford to hash a genome. Two FASTAs of
    one shape share it — which is exactly the case that let a warm cache serve one
    genome's off-target report for another. A resume decision is local to this machine,
    so it compares an opaque digest of the file's identity as well.
    """
    first = tmp_path / "one.fa"
    first.write_text(">chr9\n" + _SEQ + "\n")
    second = tmp_path / "two.fa"
    second.write_text(">chr9\n" + _SEQ[:-4] + "TTTT\n")
    manifest = tmp_path / "run.jsonl"
    release = _release(tmp_path, "a", 103, "G", "A")
    _run(ReferenceGenome(first, build="hg38"), manifest, release)
    with pytest.raises(ValueError) as excinfo:
        _run(ReferenceGenome(second, build="hg38"), manifest, release)
    message = str(excinfo.value)
    assert "reference_file:" in message, message
    # The innocent cause is named, so a reader does not go looking for corrupted data.
    assert "re-copied or re-downloaded" in message, message


def test_a_genome_of_a_different_shape_is_reported_readably(tmp_path: Path) -> None:
    """The `reference` field is structured too, and gets the same rendering treatment."""
    first = tmp_path / "one.fa"
    first.write_text(">chr9\n" + _SEQ + "\n")
    second = tmp_path / "two.fa"
    second.write_text(">chr9\n" + _SEQ + "ACGT\n")
    manifest = tmp_path / "run.jsonl"
    release = _release(tmp_path, "a", 103, "G", "A")
    _run(ReferenceGenome(first, build="hg38"), manifest, release)
    with pytest.raises(ValueError) as excinfo:
        _run(ReferenceGenome(second, build="hg38"), manifest, release)
    message = str(excinfo.value)
    assert "reference: manifest has 1 contig(s), sha " in message, message
    assert "'contigs':" not in message, message
    # Two fields differ here, so the reference-file-only note must NOT appear.
    assert "re-copied or re-downloaded" not in message, message
