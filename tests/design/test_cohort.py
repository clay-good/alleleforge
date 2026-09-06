"""Tests for cohort-scale batch design (R4): streaming, resumable, bounded."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from alleleforge.design.cohort import CohortItemResult, design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.offtarget import OffTargetReport, OffTargetSite, ScoreMethod
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import Variant

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


def test_provenance_seed_reflects_passed_settings(reference: ReferenceGenome) -> None:
    # The run-level provenance seed must be the seed that actually governed the run
    # (threaded via settings=), not the process-singleton default — it is the anchor
    # `aforge verify` reads, and a --seed-overridden batch stamping the singleton seed
    # contradicts the per-item menus it summarizes and disagrees with `af design`.
    from alleleforge.config import Settings

    report = design_many(
        [OK_1], reference=reference, intent=EditIntent.INSTALL, settings=Settings(seed=777001)
    )
    assert report.provenance["seed"] == 777001


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


def test_atomic_write_uses_utf8_not_platform_locale(tmp_path: Path) -> None:
    # The per-item payload is model_dump_json(), which preserves non-ASCII. A bare
    # write_text encodes with the platform locale — crashing under C/POSIX and
    # writing mojibake under Windows cp1252, corrupting the "lossless" export. The
    # write is pinned to UTF-8 so a non-ASCII gene name round-trips everywhere.
    from alleleforge.design.cohort import _atomic_write_text

    out = tmp_path / "menu.json"
    _atomic_write_text(out, '{"gene": "β-globin 中文"}')
    assert out.read_bytes().decode("utf-8") == '{"gene": "β-globin 中文"}'


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


def test_a_skipped_offtarget_search_reports_none_not_zero(reference: ReferenceGenome) -> None:
    """ "We did not look" must not render as the reassuring value.

    A cohort manifest is triaged by scanning a column. `worst_offtarget = 0.0`
    reads as "measured, nothing dangerous"; defaulting an unmeasured axis to it
    makes a run with the search switched off indistinguishable from a clean one —
    on the single axis where that confusion is unsafe.
    """
    skipped = design_many(
        [OK_1], reference=reference, intent=EditIntent.INSTALL, run_offtarget=False
    )
    summary = skipped.items[0].summary
    assert summary is not None
    assert summary["worst_offtarget"] is None
    assert summary["best_specificity"] is None

    searched = design_many(
        [OK_1], reference=reference, intent=EditIntent.INSTALL, run_offtarget=True
    )
    measured = searched.items[0].summary
    assert measured is not None
    assert isinstance(measured["worst_offtarget"], float), (
        "a run that did search must report a number, so the two are distinguishable"
    )


def _report(score: float) -> OffTargetReport:
    """An off-target report whose worst site scores ``score`` (empty at 0.0)."""
    sites = (
        ()
        if score == 0.0
        else (
            OffTargetSite(
                locus=GenomicInterval(chrom="chr9", start=10, end=30, strand=Strand.PLUS),
                mismatches=2,
                score=score,
                score_method=ScoreMethod.CFD,
            ),
        )
    )
    return OffTargetReport(spacer="A" * 20, pam="NGG", sites=sites)


def _candidate(*, spacer: str, offtarget: OffTargetReport | None = None) -> DesignCandidate:
    return DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=Guide(
            spacer=Spacer(sequence=DNASequence(spacer)),
            pam=PAM(pattern="NGG"),
            pam_sequence=DNASequence("TGG"),
            placement=GenomicInterval(chrom="chr2", start=0, end=20, strand=Strand.PLUS),
            cut_site=17,
        ),
        offtarget=offtarget,
    )


def test_the_triage_columns_describe_the_same_candidate() -> None:
    """`worst_offtarget` and `best_specificity` sat side by side describing different reagents.

    `worst_offtarget` was the maximum over *every* candidate in the menu while
    `best_specificity` came from the top one, so a variant whose recommended pegRNA
    was spotless still reported `worst_offtarget = 1.0` because an alternative ranked
    #301 of 470 was not — a self-contradictory row (`1.0` worst yet `1.0` specificity)
    on the column a reader scans to decide which variants need a closer look.
    """
    from alleleforge.design.cohort import _summarize

    clean = _report(0.0)
    dirty = _report(0.9)
    menu = RankedMenu(
        candidates=(
            _candidate(spacer="ACGTACGTACGTACGTACGT", offtarget=clean),
            _candidate(spacer="ACGTACGTACGTACGTACGA", offtarget=dirty),
        )
    )
    summary = _summarize(menu)

    assert summary["worst_offtarget"] == pytest.approx(clean.worst_score())
    assert summary["best_specificity"] == pytest.approx(clean.specificity_score())
    # The dirty alternative must not leak into the recommended candidate's row —
    # asserted against its actual value, so a max() over the menu is caught.
    assert summary["worst_offtarget"] != pytest.approx(dirty.worst_score())

    # ...and an unsearched recommendation still reports None, never a reassuring 0.0.
    unsearched = RankedMenu(candidates=(_candidate(spacer="ACGTACGTACGTACGTACGT"),))
    assert _summarize(unsearched)["worst_offtarget"] is None


def test_the_cohort_summary_never_reports_a_bare_efficiency() -> None:
    """ "Never a bare float" is the project's stated principle; this surface broke it.

    A cohort summary is scanned across hundreds of variants to decide which deserve a
    closer look. It reported `best_efficiency` alone — so a confident prediction and an
    out-of-distribution guess were the same number, at exactly the moment nobody is
    reading the detail. The interval, the in-distribution flag and the recommended
    candidate's hazards travel with it now.
    """
    from alleleforge.design.cohort import _summarize

    ood = Prediction[float](
        value=0.42,
        interval=(0.1, 0.74),
        method=UncertaintyMethod.ENSEMBLE,
        in_distribution=False,
    )
    candidate = _candidate(spacer="ACGTACGTACGTACGTACGT").model_copy(
        update={"efficiency": ood, "flags": ("close-nick", "epegRNA:tevopreQ1")}
    )
    summary = _summarize(RankedMenu(candidates=(candidate,)))

    assert summary["best_efficiency"] == pytest.approx(0.42)
    assert summary["best_efficiency_low"] == pytest.approx(0.1)
    assert summary["best_efficiency_high"] == pytest.approx(0.74)
    # The flag that makes the number untrustworthy, not just the number.
    assert summary["best_efficiency_in_distribution"] is False
    # Hazards, filtered to the ones that ask something of the reader.
    assert summary["best_caveats"] == ["close-nick"]

    # A menu with nothing to summarize reports None, not a reassuring zero.
    empty = _summarize(RankedMenu(candidates=()))
    assert empty["best_efficiency"] is None
    assert empty["best_efficiency_low"] is None
    assert empty["best_efficiency_in_distribution"] is None
    assert empty["best_caveats"] == []


def test_a_generator_safety_input_reaches_every_cohort_item(reference: ReferenceGenome) -> None:
    """`design_kwargs` is forwarded verbatim to every item, and to every worker thread.

    A one-shot input among them is consumed by the first variant, leaving every later
    one screened without it — and in parallel, the winner is whichever thread arrives
    first. `design()` materializes such an input for its own use, which does not help
    here: the exhausted original is what the next item receives.
    """
    from alleleforge.data.haplotypes import Haplotype

    panel = [
        Haplotype(
            hap_id="H1",
            interval=GenomicInterval(chrom="chr2", start=0, end=80, strand=Strand.PLUS),
            variants=(Variant(chrom="chr2", pos=26, ref="A", alt="C"),),
            frequencies={"afr": 0.2},
            source="1000g",
        )
    ]

    def _run(haplotypes: object) -> list[dict[str, int] | None]:
        report = design_many(
            [OK_1, OK_2],
            reference=reference,
            intent=EditIntent.INSTALL,
            haplotypes=haplotypes,  # type: ignore[arg-type]
            populations=("afr",),
        )
        # Which sources each item was actually screened against — the candidate counts
        # do not move, so this is the only place the difference is visible.
        return [(item.summary or {}).get("offtarget_sources") for item in report.items]

    from_list = _run(list(panel))
    assert len(from_list) == 2
    assert all(sources == {"haplotypes": 1} for sources in from_list), from_list

    # A generator must screen every item the same way. Before the fix the first item
    # consumed the panel and the second ran without it.
    assert _run(iter(panel)) == from_list

    # ...and the generator really is drained once, at the top, rather than per item.
    drained: list[str] = []

    def _generator() -> Iterator[Haplotype]:
        drained.append("read")
        yield from panel

    _run(_generator())
    assert drained == ["read"]


def test_skipped_counts_requests_not_the_manifest(
    reference: ReferenceGenome, tmp_path: Path
) -> None:
    """`skipped` was `len(done)` — a property of the file, not of this run.

    Reusing a manifest across a narrower variant list therefore reported every
    previously-done item as skipped now, while `total` counted only what ran. The two
    numbers described different populations and could not be added, so a resumed run
    could report "0 items, 5 skipped" for a two-item request.
    """
    manifest = tmp_path / "run.jsonl"

    first = design_many(
        [OK_1, OK_2, NEW_ITEM],
        reference=reference,
        intent=EditIntent.INSTALL,
        manifest_path=manifest,
    )
    assert first.total == 3 and first.skipped == 0

    # A later run asking for only one already-done item plus nothing new.
    resumed = design_many(
        [OK_1], reference=reference, intent=EditIntent.INSTALL, manifest_path=manifest
    )
    assert resumed.skipped == 1, "counted the manifest, not the requests"
    assert resumed.total == 0
    # The invariant that makes the two numbers addable: they cover the same population.
    assert resumed.total + resumed.skipped == 1

    # And a genuine resume of the original list.
    again = design_many(
        [OK_1, OK_2, NEW_ITEM],
        reference=reference,
        intent=EditIntent.INSTALL,
        manifest_path=manifest,
    )
    assert again.total + again.skipped == 3
    assert again.skipped == 3  # all three already recorded


def test_an_item_with_no_candidates_records_why(tmp_path: Path) -> None:
    """A cohort row said `ok` with every column blank and no reason.

    The single-variant path explains an empty result in full — which chemistries were
    routed out, which rejected every protospacer and for what — and the cohort summary
    dropped all of it. A cohort is the one surface where a reader *cannot* re-run the
    item by hand to find out: there are five hundred rows and forty say `ok, n=0`.
    """
    contig = "A" * 40 + "ACACACACACACACACACAC" * 5 + "A" * 40
    fasta = tmp_path / "empty.fa"
    fasta.write_text(f">chr1\n{contig}\n")
    reference = ReferenceGenome(fasta, build="hg38")
    report = design_many(
        [f"chr1:61:{contig[60]}>G"], reference=reference, intent=EditIntent.INSTALL
    )

    (item,) = report.items
    assert item.status == "ok"
    assert item.summary is not None
    assert item.summary["n_candidates"] == 0
    reason = item.summary["no_candidate_reason"]
    assert reason, "an item that designed nothing recorded no reason"
    assert isinstance(reason, str) and "\n" not in reason  # survives a TSV cell


def test_a_designed_item_records_no_decline_reason(reference: ReferenceGenome) -> None:
    """The field is for empty results; a successful item must not carry noise."""
    report = design_many(["chr2:26:A>G"], reference=reference, intent=EditIntent.INSTALL)

    (item,) = report.items
    assert item.summary is not None
    if item.summary["n_candidates"]:
        assert item.summary["no_candidate_reason"] is None
