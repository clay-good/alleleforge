"""Tests for cohort-scale batch design (R4): streaming, resumable, bounded."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.cohort import CohortItemResult, design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent

PAD = "T" * 20
ABE_PROTO = "TTTAAACGTTTTTTTTTTTT"  # in-window A at chr2:26 (1-based), NGG PAM downstream
CONTIG = PAD + ABE_PROTO + "TGG" + PAD

#: 1-based 24/25/26 are all 'A' (ABE-installable A>G); the wrong-ref item errors.
OK_1 = "chr2:26:A>G"
OK_2 = "chr2:25:A>G"
NEW_ITEM = "chr2:24:A>G"
BAD_REF = "chr2:26:C>G"  # asserts ref 'C' where the reference has 'A' -> hard error


def _write_fasta(path: Path) -> None:
    path.write_text(f">chr2\n{CONTIG}\n")


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "cohort.fa"
    _write_fasta(fasta)
    return ReferenceGenome(fasta, build="hg38")


@pytest.fixture
def ref_factory(tmp_path: Path) -> Callable[[], ReferenceGenome]:
    fasta = tmp_path / "cohort_factory.fa"
    _write_fasta(fasta)
    # Pre-build the pyfaidx .fai sidecar so the parallel workers' concurrent opens
    # read an existing index rather than racing to create it (the factory contract:
    # references must be safely openable concurrently — i.e. pre-indexed).
    ReferenceGenome(fasta, build="hg38").close()
    return lambda: ReferenceGenome(fasta, build="hg38")


def test_designs_cohort_and_summarizes(reference: ReferenceGenome) -> None:
    report = design_many([OK_1, OK_2], reference=reference, intent=EditIntent.INSTALL)
    assert (report.total, report.succeeded, report.failed) == (2, 2, 0)
    assert {r.item_id for r in report.items} == {OK_1, OK_2}
    best = next(r for r in report.items if r.item_id == OK_1)
    assert best.summary is not None and best.summary["best_chemistry"] == "base_abe"
    # The cohort summary carries the best candidate's aggregate specificity for triage.
    spec = best.summary["best_specificity"]
    assert spec is None or 0.0 < spec <= 1.0
    # ...and, for base-editor cohorts, the best candidate's bystander burden.
    burden = best.summary["best_bystander_burden"]
    assert burden is not None and burden >= 0.0


def test_per_item_error_is_captured_not_fatal(reference: ReferenceGenome) -> None:
    report = design_many([OK_1, BAD_REF], reference=reference, intent=EditIntent.INSTALL)
    assert (report.succeeded, report.failed) == (1, 1)
    failed = next(r for r in report.items if r.status == "error")
    assert failed.item_id == BAD_REF and failed.summary is None
    assert "reference mismatch" in (failed.error or "")


def test_provenance_is_recorded(reference: ReferenceGenome) -> None:
    report = design_many([OK_1], reference=reference, intent=EditIntent.INSTALL)
    prov = report.provenance
    assert prov["reference_build"] == "hg38"
    assert prov["intent"] == "install"
    assert prov["seed"] and prov["alleleforge_version"]


def test_manifest_written_and_resume_skips(reference: ReferenceGenome, tmp_path: Path) -> None:
    manifest = tmp_path / "run.jsonl"
    first = design_many(
        [OK_1, OK_2, BAD_REF],
        reference=reference,
        intent=EditIntent.INSTALL,
        manifest_path=manifest,
    )
    assert first.total == 3 and first.skipped == 0
    # header + one line per item
    assert len(manifest.read_text().splitlines()) == 4

    second = design_many(
        [OK_1, OK_2, BAD_REF],
        reference=reference,
        intent=EditIntent.INSTALL,
        manifest_path=manifest,
    )
    assert second.total == 0 and second.skipped == 3  # everything already recorded
    # A genuinely new item is still processed on resume.
    third = design_many(
        [OK_1, OK_2, BAD_REF, NEW_ITEM],
        reference=reference,
        intent=EditIntent.INSTALL,
        manifest_path=manifest,
    )
    assert third.total == 1 and third.skipped == 3


def test_streaming_mode_keeps_items_empty(reference: ReferenceGenome) -> None:
    seen: list[CohortItemResult] = []
    report = design_many(
        [OK_1, OK_2], reference=reference, intent=EditIntent.INSTALL, on_result=seen.append
    )
    assert report.items == ()  # not accumulated in streaming mode
    assert {r.item_id for r in seen} == {OK_1, OK_2}
    assert report.succeeded == 2


def test_output_dir_writes_per_item_menu_json(reference: ReferenceGenome, tmp_path: Path) -> None:
    import json

    out = tmp_path / "menus"
    design_many([OK_1], reference=reference, intent=EditIntent.INSTALL, output_dir=out)
    written = list(out.glob("*.json"))
    assert len(written) == 1
    assert "chr2_26_A_G" in written[0].name  # id sanitized for the filesystem
    # The write is atomic (temp file + os.replace): the file is complete valid
    # JSON and no half-written temp file is left behind.
    json.loads(written[0].read_text())
    assert not list(out.glob("*.tmp"))


def test_safe_name_is_injective_across_sanitization_collisions() -> None:
    # Distinct ids that differ only in characters the sanitizer maps to `_` used
    # to share a filename and silently overwrite (torn-write, in parallel) each
    # other; the appended digest of the raw id keeps the stem injective.
    from alleleforge.design.cohort import _safe_name

    a, b = "chr1:100:A:T", "chr1:100:A/T"  # both sanitize to chr1_100_A_T
    assert _safe_name(a).split(".")[0] == _safe_name(b).split(".")[0]  # same slug
    assert _safe_name(a) != _safe_name(b)  # but distinct filenames
    assert _safe_name(a) == _safe_name(a)  # and stable for a given id


def test_lazy_streaming_does_not_materialize_input(reference: ReferenceGenome) -> None:
    consumed: list[str] = []

    def gen() -> object:
        for v in (OK_1, OK_2):
            consumed.append(v)
            yield v

    report = design_many(gen(), reference=reference, intent=EditIntent.INSTALL)
    assert report.succeeded == 2 and consumed == [OK_1, OK_2]


def test_parallel_consumes_lazily_within_a_bounded_window(
    ref_factory: Callable[[], ReferenceGenome],
) -> None:
    # The parallel path must NOT eagerly drain the whole input (as ThreadPoolExecutor
    # .map does). With a bounded window of max_workers=2 over a 3-item cohort, at most
    # 2 items are pulled before the first result is recorded — so the first callback
    # sees fewer than the full cohort consumed, proving O(max_workers) consumption.
    consumed: list[str] = []
    consumed_at_first_result: list[int] = []

    def gen() -> object:
        for v in (OK_1, OK_2, NEW_ITEM):
            consumed.append(v)
            yield v

    def on_result(_: CohortItemResult) -> None:
        if not consumed_at_first_result:
            consumed_at_first_result.append(len(consumed))

    report = design_many(
        gen(),
        reference_factory=ref_factory,
        intent=EditIntent.INSTALL,
        max_workers=2,
        on_result=on_result,
    )
    assert report.succeeded == 3
    assert consumed_at_first_result[0] <= 2  # bounded window, not the full cohort
    assert consumed == [OK_1, OK_2, NEW_ITEM]  # every item still processed


def test_parallel_matches_sequential(
    reference: ReferenceGenome, ref_factory: Callable[[], ReferenceGenome]
) -> None:
    cohort = [OK_1, OK_2, BAD_REF]
    seq = design_many(cohort, reference=reference, intent=EditIntent.INSTALL)
    # max_workers < len(cohort) so at least one worker reuses its thread-local
    # reference across items (the safe, per-thread-handle path).
    par = design_many(
        cohort, reference_factory=ref_factory, intent=EditIntent.INSTALL, max_workers=2
    )
    assert (par.succeeded, par.failed) == (seq.succeeded, seq.failed)
    # A factory run cannot name one run-wide build (it is per worker thread).
    assert par.provenance["reference_build"] is None
    by_id = {r.item_id: r for r in par.items}
    for r in seq.items:
        assert by_id[r.item_id].status == r.status
        assert by_id[r.item_id].summary == r.summary


def test_resume_tolerates_blank_lines_in_manifest(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    manifest = tmp_path / "padded.jsonl"
    design_many([OK_1], reference=reference, intent=EditIntent.INSTALL, manifest_path=manifest)
    manifest.write_text(manifest.read_text() + "\n\n")  # trailing blank lines
    again = design_many(
        [OK_1], reference=reference, intent=EditIntent.INSTALL, manifest_path=manifest
    )
    assert again.total == 0 and again.skipped == 1


def test_parallel_requires_factory(reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError, match="reference_factory"):
        design_many([OK_1], reference=reference, max_workers=2)


def test_requires_a_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        design_many([OK_1])


def test_custom_item_id(reference: ReferenceGenome, tmp_path: Path) -> None:
    manifest = tmp_path / "ids.jsonl"
    design_many(
        [OK_1, OK_2],
        reference=reference,
        intent=EditIntent.INSTALL,
        manifest_path=manifest,
        item_id=lambda v: f"sample::{v}",
    )
    text = manifest.read_text()
    assert "sample::chr2:26:A>G" in text


def test_unexpected_defect_is_tagged_in_cohort(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A per-item unexpected exception (a code defect) is captured with a distinct,
    # actionable tag rather than an indistinguishable generic error.
    import alleleforge.design.cohort as cohort_mod

    def _defect(*args: object, **kwargs: object) -> object:
        raise AttributeError("boom")

    monkeypatch.setattr(cohort_mod, "design", _defect)
    report = design_many([OK_1], reference=reference, intent=EditIntent.INSTALL)
    failed = next(r for r in report.items if r.status == "error")
    assert "unexpected AttributeError" in (failed.error or "")
    assert "defect" in (failed.error or "")
