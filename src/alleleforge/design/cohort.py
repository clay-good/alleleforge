"""Cohort-scale batch design: stream many variants through :func:`design`.

A single-variant :func:`~alleleforge.design.designer.design` call is the unit;
:func:`design_many` is the cohort multiplier. It is built for scale, with three
guarantees that matter when the input is a whole VCF rather than three rows:

* **Streaming, bounded memory.** The input is *consumed lazily* (any iterable —
  a ``cyvcf2`` stream, a generator, a list), and only the per-item working set is
  ever held: each ranked menu is summarized (and optionally written to disk) and
  then released, so peak memory does not grow with the cohort size. Pass
  ``on_result`` to consume results as they complete and keep the run truly
  ``O(1)`` in the number of variants.
* **Resumable.** Every completed item is appended to a JSONL **run manifest**; a
  re-run with the same manifest **skips items already recorded**, so an
  interrupted cohort resumes where it stopped instead of recomputing.
* **Provenance.** The manifest opens with a run header (version, seed, reference
  build, intent, start time) and the run emits a ``CohortRunReport`` with the
  final counts — every batch run is auditable.

Per-item failures are **captured, not fatal**: an unresolvable or un-designable
variant is recorded with its error and the cohort continues.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import local
from typing import Any

from alleleforge._version import __version__
from alleleforge.config import get_settings
from alleleforge.design.designer import _EXPECTED_DESIGN_FAILURES, design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import caveats
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import EditIntent
from alleleforge.variant.resolver import ResolvedVariant, ResolveInput

#: A cohort input item: anything :func:`design` accepts.
CohortInput = ResolveInput | ResolvedVariant


@dataclass(frozen=True)
class CohortItemResult:
    """The compact outcome of one cohort item (never the full menu).

    Attributes:
        item_id: Stable identifier used for resume de-duplication.
        status: ``"ok"`` or ``"error"``.
        summary: Compact design summary (counts, best chemistry/efficiency,
            worst off-target, best-candidate aggregate specificity, chemistries
            reached), or ``None`` on error.
        error: The error string when ``status == "error"``, else ``None``.
    """

    item_id: str
    status: str
    summary: dict[str, Any] | None
    error: str | None

    def to_manifest_line(self) -> str:
        """Return the JSONL manifest line for this item."""
        return json.dumps(
            {
                "item_id": self.item_id,
                "status": self.status,
                "summary": self.summary,
                "error": self.error,
            }
        )


@dataclass(frozen=True)
class CohortRunReport:
    """Aggregate outcome of a :func:`design_many` run.

    Attributes:
        total: Items seen this run (excludes those skipped by resume).
        succeeded: Items designed without error.
        failed: Items that raised (captured, not fatal).
        skipped: Items **from this run's input** that the manifest already recorded.
            Not the manifest's size: reusing a manifest across a narrower variant list
            would otherwise report every previously-done item as skipped now.
        items: Per-item results — empty when an ``on_result`` consumer was given
            (streaming mode keeps the run ``O(1)`` in cohort size).
        provenance: Run-level provenance (version, seed, reference build, intent).
        manifest_path: The JSONL manifest written, if any.
    """

    total: int
    succeeded: int
    failed: int
    skipped: int
    items: tuple[CohortItemResult, ...]
    provenance: dict[str, Any]
    manifest_path: str | None


def _summarize(menu: RankedMenu) -> dict[str, Any]:
    """Return the compact, memory-cheap summary kept for one designed variant.

    ``worst_offtarget`` and ``best_specificity`` both describe the **recommended**
    candidate, so a row is internally consistent: a reader comparing them is comparing
    two facts about one reagent.

    ``worst_offtarget`` is ``None`` when the recommended candidate carries no
    off-target report — the search was skipped — and a number only when one was
    actually run. The
    distinction is the whole point: a cohort manifest is triaged by scanning a
    column, and ``0.0`` there is the *reassuring* value. Defaulting an unmeasured
    axis to it makes "we did not look" indistinguishable from "we looked and it is
    clean", on the one axis where that confusion is dangerous.
    """
    best = menu.best
    # Scoped to the *recommended* candidate, not the whole menu. These two numbers sit
    # side by side in a triage table, and taking the max over every candidate while
    # `best_specificity` describes only the top one made them describe different
    # reagents: a variant whose recommended pegRNA is spotless still reported
    # `worst_offtarget = 1.0` because some alternative ranked #301 of 470 was not. A
    # column read to decide "which variants need a closer look" has to be about the
    # reagent the reader would actually use.
    worst_ot = best.offtarget.worst_score() if best and best.offtarget is not None else None
    best_specificity = (
        best.offtarget.specificity_score() if best and best.offtarget is not None else None
    )
    return {
        "n_candidates": len(menu.candidates),
        "chemistries": sorted({c.chemistry.value for c in menu.candidates}),
        "best_chemistry": best.chemistry.value if best else None,
        # Interval and OOD flag beside the point estimate, not the point estimate alone.
        # "Every numeric prediction carries a calibrated interval, never a bare float" is
        # the project's stated principle, and this is the surface where it matters most:
        # a cohort summary is scanned across hundreds of variants to decide which to look
        # at, and a bare `eff=0.61` makes a confident prediction and an out-of-distribution
        # guess look identical at exactly the moment nobody is reading the detail.
        "best_efficiency": (best.efficiency.value if best and best.efficiency else None),
        "best_efficiency_low": (best.efficiency.interval[0] if best and best.efficiency else None),
        "best_efficiency_high": (best.efficiency.interval[1] if best and best.efficiency else None),
        "best_efficiency_in_distribution": (
            best.efficiency.in_distribution if best and best.efficiency else None
        ),
        # The recommended candidate's hazards, so a triage scan surfaces the rows that
        # need a closer look rather than only the ones with a poor number.
        "best_caveats": ([flag for flag, _ in caveats(best.flags)] if best is not None else []),
        "best_bystander_burden": (
            best.bystander_burden.value if best and best.bystander_burden else None
        ),
        # Which safety sources actually contributed for this variant. A cohort is where
        # a per-item difference hides: one variant screened against a haplotype panel
        # and the next screened without it produce identical-looking rows, and the row
        # is what a reader scans. It is also the only place the difference is
        # observable — the candidate counts do not move.
        "offtarget_sources": (
            dict(best.offtarget.sources_considered)
            if best is not None and best.offtarget is not None
            else None
        ),
        "worst_offtarget": worst_ot,
        "best_specificity": best_specificity,
    }


def _read_done_ids(manifest_path: Path) -> set[str]:
    """Return the item ids already recorded in ``manifest_path`` (for resume)."""
    done: set[str] = set()
    if not manifest_path.exists():
        return done
    for line in manifest_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if "item_id" in record:
            done.add(record["item_id"])
    return done


def design_many(
    variants: Iterable[CohortInput],
    *,
    reference: ReferenceGenome | None = None,
    reference_factory: Callable[[], ReferenceGenome] | None = None,
    intent: EditIntent = EditIntent.CORRECT,
    manifest_path: str | Path | None = None,
    resume: bool = True,
    on_result: Callable[[CohortItemResult], None] | None = None,
    output_dir: str | Path | None = None,
    max_workers: int = 1,
    item_id: Callable[[CohortInput], str] | None = None,
    **design_kwargs: Any,
) -> CohortRunReport:
    """Design a whole cohort, streaming and resumable.

    Args:
        variants: The cohort, consumed lazily (a VCF stream, generator, or list).
        reference: The reference genome (sequential runs, ``max_workers == 1``).
        reference_factory: A zero-arg factory returning a *fresh* reference per
            worker thread; **required** for ``max_workers > 1`` because a
            :class:`ReferenceGenome` (a pyfaidx handle) is not thread-safe to
            share. The FASTA it opens must already carry its ``.fai`` index, so
            the concurrent first-opens read it rather than racing to build it
            (open the reference once before the parallel run, or ship the
            ``.fai`` alongside the FASTA).
        intent: The edit intent applied to every variant.
        manifest_path: JSONL run manifest to append to; enables resume.
        resume: Skip items already recorded in ``manifest_path``.
        on_result: Called with each :class:`CohortItemResult` as it completes; when
            given, results are streamed (not accumulated) for ``O(1)`` memory.
        output_dir: If set, each item's full menu JSON is written atomically to
            ``<output_dir>/<sanitized-item_id>.<hash>.json`` (the hash keeps the
            filename collision-free) so reports survive the run.
        max_workers: Thread pool size (needs ``reference_factory`` when ``> 1``).
        item_id: Maps an input to its stable id (default ``str``); used for resume
            de-duplication and the per-item output filename.
        **design_kwargs: Forwarded verbatim to :func:`design` (e.g. ``clinvar``,
            ``gnomad``, ``populations``, ``weights``, ``run_offtarget``).

    Returns:
        A :class:`CohortRunReport` with the run counts and provenance.

    Raises:
        ValueError: If neither/both of ``reference``/``reference_factory`` fit the
            requested ``max_workers``.
    """
    if max_workers > 1 and reference_factory is None:
        raise ValueError("parallel cohort runs (max_workers > 1) require a reference_factory")
    if reference is None and reference_factory is None:
        raise ValueError("design_many needs a reference or a reference_factory")
    # `design_kwargs` is forwarded verbatim to every item — and, with `max_workers > 1`,
    # to every worker thread. A one-shot safety input among them is consumed by the
    # first item, leaving every later variant screened without it; in parallel the
    # winner is whichever thread gets there first. `design()` materializes such an
    # input for its own use, which does not help here, because the exhausted original
    # is what the next item receives.
    #
    # Only a true `Iterator` is converted, so a `HaplotypePanel` or `_PatientVariants`
    # keeps the provenance descriptor it carries as an attribute. That half is not
    # observable from here — a cohort keeps summaries and discards the per-item menus
    # that would carry the record — so it is pinned where it is visible, in `design()`.
    for shared in ("haplotypes", "patient_vcf"):
        value = design_kwargs.get(shared)
        if isinstance(value, Iterator):
            design_kwargs[shared] = list(value)

    id_of = item_id or str

    manifest = Path(manifest_path) if manifest_path is not None else None
    done = _read_done_ids(manifest) if (manifest is not None and resume) else set()
    provenance = {
        "alleleforge_version": __version__,
        # The seed that actually governs the run is the one threaded into every
        # design() call via `settings=` — not the process singleton. Stamping the
        # singleton made a `--seed`-overridden batch record the wrong seed, so the
        # run header contradicted its own per-item menus and disagreed with what
        # `af design` records for the same seed. Fall back to the singleton only
        # when no settings were passed (matching design()'s own default).
        "seed": (design_kwargs.get("settings") or get_settings()).seed,
        "reference_build": _build_name(reference, reference_factory),
        "intent": intent.value,
        "started_at": datetime.now(UTC).isoformat(),
    }
    if manifest is not None and not manifest.exists():
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"_run": provenance}) + "\n")

    out_dir = Path(output_dir) if output_dir is not None else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    tl = local()

    def _reference() -> ReferenceGenome:
        if reference_factory is None:
            assert reference is not None
            return reference
        ref = getattr(tl, "ref", None)
        if ref is None:
            ref = reference_factory()
            tl.ref = ref
        return ref

    def _design_one(item: CohortInput) -> CohortItemResult:
        iid = id_of(item)
        try:
            menu = design(item, reference=_reference(), intent=intent, **design_kwargs)
        except _EXPECTED_DESIGN_FAILURES as exc:
            return CohortItemResult(
                item_id=iid, status="error", summary=None, error=f"{type(exc).__name__}: {exc}"
            )
        except Exception as exc:  # noqa: BLE001 - a defect is recorded distinctly, not hidden
            # An unexpected exception type is a code defect, not a per-item data
            # problem; tag it so the error column is actionable rather than a
            # generic "error" indistinguishable from "no design".
            return CohortItemResult(
                item_id=iid,
                status="error",
                summary=None,
                error=f"unexpected {type(exc).__name__} (likely a defect): {exc}",
            )
        if out_dir is not None:
            _atomic_write_text(out_dir / f"{_safe_name(iid)}.json", menu.model_dump_json())
        return CohortItemResult(iid, "ok", _summarize(menu), None)

    # Count the *requests* this run skipped, not the manifest's size. `len(done)` is a
    # property of the manifest file, so reusing one across a narrower variant list
    # reported "5 skipped" for a two-item request — and with `total` counting only what
    # ran, the summary's numbers described two different populations and could not be
    # added together. Counted here as the stream is consumed, so a lazy input stays lazy.
    skipped_requests = 0

    def _pending() -> Iterator[CohortInput]:
        nonlocal skipped_requests
        for item in variants:
            if id_of(item) in done:
                skipped_requests += 1
                continue
            yield item

    pending = _pending()
    results: list[CohortItemResult] = []
    counts = {"ok": 0, "error": 0}

    def _record(result: CohortItemResult) -> None:
        counts[result.status] += 1
        if manifest is not None:
            with manifest.open("a") as fh:
                fh.write(result.to_manifest_line() + "\n")
        if on_result is not None:
            on_result(result)
        else:
            results.append(result)

    if max_workers > 1:
        _run_windowed(_design_one, pending, _record, max_workers)
    else:
        for item in pending:
            _record(_design_one(item))

    return CohortRunReport(
        total=counts["ok"] + counts["error"],
        succeeded=counts["ok"],
        failed=counts["error"],
        skipped=skipped_requests,
        items=tuple(results),
        provenance=provenance,
        manifest_path=str(manifest) if manifest is not None else None,
    )


def _run_windowed(
    design_one: Callable[[CohortInput], CohortItemResult],
    pending: Iterator[CohortInput],
    record: Callable[[CohortItemResult], None],
    max_workers: int,
) -> None:
    """Run ``pending`` through a thread pool with a bounded in-flight window.

    ``ThreadPoolExecutor.map`` is eager — it submits one task per input up front,
    draining the whole (possibly VCF-stream) generator and holding an O(n) list of
    futures, which breaks the "consumed lazily / bounded memory" guarantee for the
    parallel path. Instead this keeps at most ``max_workers`` futures in flight,
    pulling the next input only as each completes, so peak memory is O(max_workers)
    regardless of cohort size. Results are recorded in completion order (the manifest
    and resume are set-keyed on ``item_id``, so order is not load-bearing).
    """
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        in_flight: set[Future[CohortItemResult]] = set()

        def _submit_next() -> None:
            try:
                item = next(pending)
            except StopIteration:
                return
            in_flight.add(pool.submit(design_one, item))

        for _ in range(max_workers):  # prime the window
            _submit_next()
        while in_flight:
            finished, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
            for fut in finished:
                record(fut.result())
                _submit_next()


def _build_name(
    reference: ReferenceGenome | None, factory: Callable[[], ReferenceGenome] | None
) -> str | None:
    """Return the reference build name without forcing a factory open."""
    if reference is not None:
        return reference.build
    return None  # a factory's build is per-worker; recorded per item, not run-wide


def _safe_name(item_id: str) -> str:
    """Return a filesystem-safe, collision-free stem for a per-item output file.

    The sanitizer maps every non-``[alnum-._]`` character to ``_``, so distinct
    ids that differ only in such characters (e.g. ``chr1:100:A:T`` vs
    ``chr1:100:A/T``, both → ``chr1_100_A_T``) would share a filename and silently
    overwrite each other — escalated to a torn write when two collide in flight on
    the parallel path. Appending a short digest of the *raw* id makes the stem
    injective while keeping it human-readable.
    """
    slug = "".join(c if c.isalnum() or c in "-._" else "_" for c in item_id)
    digest = hashlib.sha1(item_id.encode("utf-8")).hexdigest()[:8]
    return f"{slug}.{digest}"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file in the same dir + rename).

    A plain ``write_text`` leaves a window in which a concurrent reader (or a
    crash) sees a truncated file; ``os.replace`` of a fully-written temp file is
    atomic on POSIX and Windows, so a per-item report is never observed partial.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    # Pin UTF-8: the payload is `model_dump_json()`, which preserves non-ASCII
    # (a gene name / rationale like "β-globin"), but a bare `write_text` encodes
    # with the platform locale — crashing under a non-UTF-8 locale (C/POSIX) and
    # writing mojibake under Windows cp1252, corrupting the "lossless" export.
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
