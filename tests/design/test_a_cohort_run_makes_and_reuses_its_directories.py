"""A cohort run creates the directories it writes into, and can write into them again.

A constant-mutation sweep found both `mkdir(parents=True, exist_ok=True)` calls in
`design_many` free to lose either flag: every fixture passed a manifest and an output
directory whose parent already existed, and none ran twice into one output directory.
Both are ordinary: a batch pointed at `results/2026-10/run.jsonl`, and a second cohort
written into the same results folder under a new manifest.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome

_SEQ = "ACGTTGCAAGGCTTACCGTA" * 30


def test_nested_paths_are_created_and_an_existing_output_dir_is_reused(tmp_path: Path) -> None:
    fasta = tmp_path / "chr9.fa"
    fasta.write_text(">chr9\n" + _SEQ + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    out = tmp_path / "results" / "2026-10" / "menus"
    for run in ("first", "second"):
        # One nested folder for both: the first run creates it, the second reuses it.
        manifest = tmp_path / "manifests" / "2026-10" / f"{run}.jsonl"
        report = design_many(
            ["chr9:31:G>A"],
            reference=reference,
            manifest_path=manifest,
            output_dir=out,
            run_offtarget=False,
        )
        assert manifest.is_file(), run
        assert report.provenance is not None
    assert out.is_dir() and any(out.iterdir())
