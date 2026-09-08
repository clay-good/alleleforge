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
from threading import Lock, local
from typing import Any
from uuid import uuid4

from alleleforge._version import __version__
from alleleforge.config import get_settings
from alleleforge.design.designer import (
    _EXPECTED_DESIGN_FAILURES,
    _reference_snapshot,
    design,
)
from alleleforge.errors import reason
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import caveats
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import EditIntent
from alleleforge.types.provenance import DatasetVersion
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


def _decline_reason(menu: RankedMenu) -> str | None:
    """Return a one-line summary of why a menu has no candidates.

    Built from the rationale's per-chemistry notes — the lines the single-variant
    report shows under "How this menu was assembled" — flattened onto one line so it
    survives a TSV cell. ``None`` when the menu recorded no rationale at all.

    The run notes lead, then the declined chemistries. Both blocks are kept: a cohort
    row is often the only thing a reader sees for that variant. But they answer
    different questions, and only one is about *this* variant. A no-op input
    (``chr2:1200:A>A``) produced::

        base_abe: Adenine base editing installs an A->G / T->C transition in a narrow
        window with no double-strand break — ... | base_cbe: ... | cas9_nuclease: ... |
        prime: eligible but no actionable candidate enumerated — the requested edit does
        not change the sequence ...

    Three definitions of what a chemistry is for, and then the one sentence that says
    what went wrong with the input, 700 characters in. The blocks became separable when
    the rationale gained its own heading for run notes.
    """
    if not menu.rationale:
        return None
    declined: list[str] = []
    run_notes: list[str] = []
    target = declined
    for raw in menu.rationale.splitlines():
        line = raw.strip()
        if line.startswith("Run notes:"):
            target = run_notes
        elif line.startswith("- "):
            target.append(line.removeprefix("- ").strip())
    notes = run_notes + declined
    return " | ".join(notes) if notes else None


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
        # What this row is *about*. `item_id` is the string the user typed, and for the
        # two database input forms it names no locus — `VCV000000012` is a row a reader
        # cannot place in the genome, and two ClinVar releases can place it differently.
        # A coordinate is not safe either: left-alignment moves an indel, so the id and
        # the designed locus routinely differ. This is the only column that says where
        # the reagents in the rest of the row actually go.
        "variant": menu.variant,
        # The reason a row was requested by accession at all. A cohort of `VCV…` inputs
        # is exactly the run where this matters — hundreds of rows, triaged by scanning
        # — and the classification lived only in each item's rationale, which the
        # summary does not carry and nobody opens five hundred of.
        "clinical_significance": menu.clinical_significance,
        "n_candidates": len(menu.candidates),
        # Why nothing was found, when nothing was. The single-variant path explains an
        # empty result in full — which chemistries were routed out and why, which
        # rejected every protospacer and for what reason — and the cohort dropped all
        # of it, leaving a row that reads `ok` with every column blank. A cohort is
        # the one surface where a reader *cannot* re-run the item by hand to find out:
        # there are five hundred rows and forty of them say `ok, n=0`.
        "no_candidate_reason": _decline_reason(menu) if not menu.candidates else None,
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
        # With its interval, like `best_efficiency` two fields up and for the same
        # stated reason: "every numeric prediction carries a calibrated interval, never
        # a bare float". `bystander_burden` is a `Prediction[float]` too, and this row
        # kept the point estimate and dropped the envelope — the rule applied to one
        # column of a triage table and not to its neighbour.
        "best_bystander_burden": (
            best.bystander_burden.value if best and best.bystander_burden else None
        ),
        "best_bystander_burden_low": (
            best.bystander_burden.interval[0] if best and best.bystander_burden else None
        ),
        "best_bystander_burden_high": (
            best.bystander_burden.interval[1] if best and best.bystander_burden else None
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
    """Return the item ids a resume may skip: the ones that **succeeded**.

    Two things a manifest written by an interrupted run actually contains, neither of
    which the first version of this handled:

    * **Failed items.** Recording an id was enough to skip it, so a cohort of 10,000
      that finished with 200 errors skipped all 10,000 on the next run -- reporting
      ``total=0, failed=0`` and exiting 0, where the first run had exited non-zero.
      Re-running until it passes worked, by doing nothing. A failed item did no work
      worth preserving; resume exists to avoid recomputing results, and an error is not
      one. Retrying is also cheap, since these fail at resolution before any search.
    * **A truncated last line.** An append interrupted mid-write leaves exactly that,
      and it raised ``JSONDecodeError`` from the one code path whose whole purpose is
      recovering from an interrupted run. Only the final line is forgiven -- that is the
      crash signature. A malformed line anywhere else means a corrupted or hand-edited
      manifest, and silently skipping it would silently recompute or silently drop.
    """
    done: set[str] = set()
    if not manifest_path.exists():
        return done
    lines = manifest_path.read_text().splitlines()
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            if number == len(lines):
                # The interrupted append. The item it half-described is simply not
                # recorded, so it runs again -- which is what resume is for.
                break
            raise ValueError(
                f"{manifest_path}: line {number} is not valid JSON ({exc.msg}). Only a "
                "truncated *final* line is treated as an interrupted append; a bad line "
                "in the middle means the manifest is corrupt, and skipping it would "
                "silently recompute or silently drop an item."
            ) from exc
        if "item_id" in record and record.get("status") == "ok":
            done.add(record["item_id"])
    return done


#: Header fields a resume must agree with. Everything here changes what a design
#: *produces*, so reusing a result computed under a different value is not resuming a
#: run, it is mixing two. `started_at` and the counts are deliberately absent: they
#: describe the attempt, not the answer.
_RESUME_CRITICAL = (
    "alleleforge_version",
    "seed",
    "reference_build",
    "reference",
    "reference_file",
    "intent",
    "inputs",
)


def _reference_file_digest(reference: ReferenceGenome | None) -> str | None:
    """Return an opaque, machine-local digest of the reference file's identity.

    ``None`` when there is no run-wide reference (the parallel path opens one per
    worker) or the file cannot be stat'd, in which case the comparison falls back to the
    shape — no worse than before, and every ordinary run is safer.
    """
    if reference is None:
        return None
    try:
        stat = Path(reference.path).resolve().stat()
    except OSError:
        return None
    parts = f"{Path(reference.path).resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(parts.encode()).hexdigest()[:12]


def _input_descriptors(design_kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the provenance descriptors of the data sources a run was handed.

    The same attribute `_collect_datasets` reads off gnomAD, ClinVar, a haplotype panel
    and the rest — read here, before any item runs, because a resume decision needs them
    and the observed union is only available once the run is over.
    """
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for value in design_kwargs.values():
        version = getattr(value, "dataset_version", None)
        if isinstance(version, DatasetVersion):
            found.setdefault((version.name, version.version), version.model_dump(mode="json"))
    return [found[key] for key in sorted(found)]


def _run_header(manifest_path: Path) -> dict[str, Any]:
    """Return the `_run` block a manifest was opened with, or ``{}`` if it has none."""
    if not manifest_path.exists():
        return {}
    first = manifest_path.read_text().splitlines()
    if not first:
        return {}
    try:
        record = json.loads(first[0])
    except json.JSONDecodeError:
        return {}
    header = record.get("_run")
    return header if isinstance(header, dict) else {}


def _render(key: str, value: Any) -> str:
    """Render one header value for a refusal a human has to act on.

    The two structured fields are a list of dataset descriptors and a reference shape.
    Dumped as `repr`, one differing ClinVar release filled three lines with `None`s and
    buried the two hashes that differ — a message that is technically complete and
    practically unreadable is the failure mode this project keeps correcting.
    """
    if key == "inputs" and isinstance(value, list):
        return ", ".join(f"{d.get('name')} {d.get('version')}" for d in value) or "nothing"
    if key == "reference_file":
        return f"file {value}" if value else "no run-wide reference"
    if key == "reference" and isinstance(value, dict):
        return f"{value.get('contigs')} contig(s), sha {str(value.get('sha256'))[:8]}"
    return repr(value)


def _refuse_a_mismatched_resume(manifest_path: Path, provenance: dict[str, Any]) -> None:
    """Refuse to resume a manifest opened under different result-determining inputs.

    Resume keys on `item_id` alone, which is the *request*, not the answer. Re-running
    the same cohort against a second ClinVar release — same accessions, different loci —
    skipped every item as "already done", exited 0, and wrote a summary with no rows.
    The user believes the run used the release they named; it used the previous one, and
    nothing in the artifact says so. The same holds for a different genome, a different
    seed and a different intent.

    The manifest header already records what the first run was, and nothing had ever read
    it back. Refusing is the right answer rather than warning: the alternative is a
    result that is silently a mixture of two runs, and the two ways forward (`--no-resume`,
    or a fresh manifest) are both one flag away.
    """
    header = _run_header(manifest_path)
    if not header:
        return
    differing = [
        f"{key}: manifest has {_render(key, header.get(key))}, "
        f"this run has {_render(key, provenance.get(key))}"
        for key in _RESUME_CRITICAL
        if key in header and header.get(key) != provenance.get(key)
    ]
    if differing:
        raise ValueError(
            f"{manifest_path} was written by a run with different inputs, so resuming it "
            "would mix two runs into one result:\n  "
            + "\n  ".join(differing)
            + "\nRe-run with resume disabled (`--no-resume`) to design every item under "
            "these inputs, or point --manifest at a new file."
            # The innocent cause is common enough to name: a genome moved, re-copied or
            # re-downloaded is a different file to this check even when its bytes are
            # identical, and a reader should not go looking for corrupted data.
            + (
                "\n(`reference_file` is an identity, not a checksum of the bases: a "
                "genome moved, re-copied or re-downloaded reads as a different file "
                "even when its bytes are identical.)"
                if all(d.startswith("reference_file:") for d in differing)
                else ""
            )
        )


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
            share. It is called once up front, before any worker starts, so a
            FASTA with no ``.fai`` yet has one by the time the concurrent opens
            happen rather than racing to build it.
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
    if max_workers > 1 and reference_factory is not None:
        # Open once here so the `.fai` exists before any worker opens the FASTA. The
        # docstring above asks the caller to do this, and both callers in this tree do
        # -- but a documented precondition whose violation is a *race* is a bad trade:
        # it fails non-deterministically, only under parallelism, and reports
        # `KeyError: unknown contig 'chr2'`, which names the one thing that is not
        # wrong. The contig is there; the index was mid-write when a second thread read
        # it. One extra open makes the precondition unnecessary rather than documented.
        reference_factory().close()
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
        # The build is a *label*; two different FASTAs both carrying "hg38" give
        # different off-target verdicts. The per-item menus record the genome's shape
        # (see `_reference_snapshot`); the run header recorded only the name, so a
        # cohort summary could not say which genome the whole cohort was screened
        # against. `None` under the parallel path, where the reference is opened
        # per worker and there is no run-wide one to describe.
        "reference": None if reference is None else _reference_snapshot(reference),
        # The snapshot pins contig names and lengths, deliberately and by its own
        # statement — it is a *shareable* descriptor, so it cannot carry a local path
        # and cannot afford to hash a genome. Two FASTAs of one shape therefore have one
        # snapshot, which is the weakness that let a warm off-target cache serve one
        # genome's report for another. A resume decision is local to this machine, so it
        # can compare more: an opaque digest of the file's identity, which leaks no path
        # into an artifact and still tells the two files apart.
        "reference_file": _reference_file_digest(reference),
        "intent": intent.value,
        # The result-determining *data* this run was given, named up front rather than
        # observed at the end: a resume has to compare them before it decides what to
        # skip. Each entry is whatever descriptor the source carries (a content hash for
        # a caller-supplied file), sorted so the header is stable.
        "inputs": _input_descriptors(design_kwargs),
        "started_at": datetime.now(UTC).isoformat(),
    }
    if manifest is not None and resume:
        _refuse_a_mismatched_resume(manifest, provenance)
    done = _read_done_ids(manifest) if (manifest is not None and resume) else set()
    if manifest is not None and not manifest.exists():
        from alleleforge.report.builder import COORDINATE_NOTE, RESEARCH_USE_DISCLAIMER

        manifest.parent.mkdir(parents=True, exist_ok=True)
        # The header says what this run *was*; it also has to say what the run's output
        # *is*. The per-item menu files are exempt from the every-artifact rule on the
        # grounds that "the run that wrote it puts the context in the summary TSV and
        # the manifest header beside it" — and the manifest header did not, so a
        # `--manifest --output-dir` run with no `--summary-tsv` left a directory of
        # menus and an index, with nothing in it saying what any of it was.
        manifest.write_text(
            json.dumps(
                {
                    "_run": {
                        "disclaimer": RESEARCH_USE_DISCLAIMER,
                        "coordinate_note": COORDINATE_NOTE,
                        **provenance,
                    }
                }
            )
            + "\n"
        )

    out_dir = Path(output_dir) if output_dir is not None else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    # The run header pinned the reference genome's shape and nothing else, while every
    # per-item menu recorded the datasets it read — so the one artifact a whole cohort is
    # forwarded in could not say which ClinVar release chose its loci or which gnomAD
    # file made its scans population-aware. Per-item honesty does not accumulate into
    # document honesty; the reader of the summary never opens 500 menus.
    #
    # Collected from the items rather than recomputed, so it states what the run actually
    # consumed. A lock because the parallel path records from worker threads, and sorted
    # at the end because a set's iteration order would make a byte-reproducible artifact
    # depend on --max-workers.
    seen_datasets: dict[tuple[str, str], dict[str, Any]] = {}
    datasets_lock = Lock()

    def _record_datasets(menu: RankedMenu) -> None:
        prov = menu.provenance
        for dataset in getattr(prov, "datasets", ()) or ():
            with datasets_lock:
                seen_datasets.setdefault((dataset.name, dataset.version), dataset.model_dump())

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
                item_id=iid,
                status="error",
                summary=None,
                error=f"{type(exc).__name__}: {reason(exc)}",
            )
        except Exception as exc:  # noqa: BLE001 - a defect is recorded distinctly, not hidden
            # An unexpected exception type is a code defect, not a per-item data
            # problem; tag it so the error column is actionable rather than a
            # generic "error" indistinguishable from "no design".
            return CohortItemResult(
                item_id=iid,
                status="error",
                summary=None,
                error=f"unexpected {type(exc).__name__} (likely a defect): {reason(exc)}",
            )
        _record_datasets(menu)
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
            iid = id_of(item)
            if iid in done:
                skipped_requests += 1
                continue
            if accumulating:
                order.setdefault(iid, len(order))
            yield item

    pending = _pending()
    results: list[CohortItemResult] = []
    counts = {"ok": 0, "error": 0}
    # Input position per item, kept only when this run is accumulating a report. The
    # streaming path (`on_result`) holds nothing and must keep holding nothing: its
    # whole point is O(max_workers) memory over a VCF of any size.
    order: dict[str, int] = {}
    accumulating = on_result is None

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

    # Input order, not completion order. `_run_windowed` records results as they
    # finish and says so, reasoning that "the manifest and resume are set-keyed on
    # item_id, so order is not load-bearing" — true of both, and of neither of the
    # things a person reads. The summary TSV, the cohort JSON, the HTTP response and
    # the browser's table all render `items` in the order they arrive, so the same
    # cohort run twice with `--max-workers 4` produced two byte-different tables whose
    # rows had merely moved. In a project whose promise is byte-reproducibility, a
    # performance flag must not change the artifact.
    #
    # The manifest stays completion-ordered: it is an append-as-you-go progress log,
    # and a resumed run reads it as a set.
    ordered = sorted(results, key=lambda r: order.get(r.item_id, len(order)))
    provenance["datasets"] = [seen_datasets[key] for key in sorted(seen_datasets)]
    return CohortRunReport(
        total=counts["ok"] + counts["error"],
        succeeded=counts["ok"],
        failed=counts["error"],
        skipped=skipped_requests,
        items=tuple(ordered),
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
    regardless of cohort size.

    Results are *recorded* in completion order, which is right for the two consumers
    that see them as they arrive: the manifest is a progress log and a resumed run reads
    it as a set. The report `design_many` returns is re-sorted into input order there,
    because everything a person reads — the summary TSV, the cohort JSON, the HTTP
    response, the browser's table — renders it in sequence, and a cohort whose rows move
    between identical runs cannot be diffed.
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
    # Unique per call, not per process. `_atomic_write_text` runs inside `_design_one`,
    # which runs in a worker thread, so a pid-scoped name is shared by every thread --
    # and two items with the same id (a variant repeated in a VCF, which is ordinary)
    # resolve to the same output path and therefore the same temp path. Both threads
    # then write one file and both rename it: the second `os.replace` raises
    # FileNotFoundError, which the cohort records as "unexpected ... (likely a defect)",
    # and the surviving bytes are whatever the interleaving left.
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    # Pin UTF-8: the payload is `model_dump_json()`, which preserves non-ASCII
    # (a gene name / rationale like "β-globin"), but a bare `write_text` encodes
    # with the platform locale — crashing under a non-UTF-8 locale (C/POSIX) and
    # writing mojibake under Windows cp1252, corrupting the "lossless" export.
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
