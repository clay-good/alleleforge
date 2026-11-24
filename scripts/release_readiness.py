#!/usr/bin/env python
"""Report how far the repository is from the v1.0 criteria in `SPEC_V2.md` (R6).

`SPEC_V2.md` lists five conditions for cutting v1.0 and nothing measured any of them,
so "how close are we" was a question answered by reading five bullet points and
guessing. Most of the criteria are gated on work that is blocked outside this
repository — real model weights, real benchmark corpora, a posted preprint — and that
is exactly why a measurement is worth having: it distinguishes *blocked* from
*forgotten*, and it will notice the day one of them stops being blocked.

This reports; it does not judge. Each criterion prints what is mechanically true today
and the evidence behind it. The exit code is non-zero while any criterion is unmet, so
it can serve as a release gate, but "unmet" here mostly means "the upstream artifact
has not been frozen yet", which is a fact about the world and not a defect.

Usage:
    python scripts/release_readiness.py            # human table; exit 1 if not ready
    python scripts/release_readiness.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Criterion:
    """One v1.0 condition, its verdict, and the evidence for that verdict."""

    track: str
    summary: str
    met: bool
    detail: str
    #: Why it is not met, when the reason lies outside this repository.
    blocked_by: str = ""
    evidence: list[str] = field(default_factory=list)


#: URL path shapes that name a *downloadable artifact* rather than a project. A release
#: asset, a model-hub blob, or any path whose last segment carries a file extension can
#: be fetched and hashed; a repository or model-card landing page cannot.
_ARTIFACT_PATH = re.compile(r"(/releases/download/|/resolve/|/raw/|/blob/|\.[A-Za-z0-9]{1,5}$)")


def _names_an_artifact(url: str) -> bool:
    """Whether ``url`` points at bytes that can be fetched and checksummed.

    `source_url` carries two different things today and the distinction decides what
    pinning a card would even mean. `rule-set-3` names a release asset — one file, a
    stable URL, a hash. Most of the others name a GitHub repository or a Hugging Face
    model page: there is no single artifact there to hash, and recording the hash of the
    landing page would pin an HTML document while reporting the criterion as met.

    So the two are counted separately. Treating them as one made R0 read as eleven
    downloads away, when eleven of them first need somebody to decide *which file* the
    weights are — and for several upstreams no such stable file is published.
    """
    without_scheme = url.split("://", 1)[-1]
    path = without_scheme[without_scheme.find("/") :] if "/" in without_scheme else ""
    return bool(path) and bool(_ARTIFACT_PATH.search(path))


#: Path segments that mean "whatever is newest", not a particular release.
_MOVING_SEGMENTS = frozenset(
    {"latest", "latest_release", "master", "main", "current", "head", "dev", "nightly"}
)


def _names_a_moving_target(url: str) -> bool:
    """Whether ``url`` names a file whose bytes upstream may replace in place.

    `dbsnp` points at `/snp/latest_release/VCF/GCF_000001405.40.gz`. That names a file,
    so :func:`_names_an_artifact` is satisfied and the card-side triage would report it
    as one fetch-and-hash away — which is wrong. The hash would be of whatever
    `latest_release` meant on the day it was taken, and the next upstream release
    silently invalidates it. Worse than a stale number: the consent gate refuses an
    artifact whose digest does not match, so pinning this URL would *break* the dataset
    the first time NCBI publishes again.

    The two datasets that *are* pinned both name an immutable path — a dated ClinVar
    archive and a numbered GENCODE release — which is what makes their hashes mean
    something. So this is a third thing that can stand in the way of R0, alongside "go
    fetch it" and "upstream publishes no single file": *upstream publishes the file only
    at a floating address, and a versioned one has to be found first.*

    A bundled descriptor is exempt by construction and never reaches this: its hash is
    of the bytes shipped inside the package, so the URL is provenance rather than a
    fetch target.
    """
    without_scheme = url.split("://", 1)[-1]
    path = without_scheme[without_scheme.find("/") :] if "/" in without_scheme else ""
    segments = {segment.lower() for segment in path.split("/") if segment}
    return bool(segments & _MOVING_SEGMENTS)


def _artifact_pinning() -> Criterion:
    """R0: every shipped card/descriptor pins a real, verified artifact hash."""
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.model_zoo.registry import default_registry

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    # A baseline has no external artifact, so it has nothing to pin and must not be
    # counted against the criterion — the denominator is cards that name a source.
    downloadable = [c for c in cards if c.source_url]
    pinned = [c for c in downloadable if c.checkpoint_sha256]
    baselines = [c for c in cards if not c.source_url]
    # Split the unpinned by what is actually in the way: a fetch, or a decision about
    # which file to fetch. The criterion is unmet either way — this changes nothing
    # about the verdict and everything about what the verdict means.
    unpinned = [c for c in downloadable if not c.checkpoint_sha256]
    fetchable = [c for c in unpinned if _names_an_artifact(c.source_url or "")]
    referenced = [
        c
        for c in unpinned
        if not _names_an_artifact(c.source_url or "") and c.source_snapshot is None
    ]
    # Counted separately and deliberately NOT folded into `pinned`. A revision pin makes
    # a load reproducible — the bytes behind a 40-hex commit cannot change — but it is
    # not "a verified artifact hash", which is what this criterion asks for: the blob
    # digests are checked by the hub client against upstream's metadata, not recomputed
    # here. Folding these in would move the number without meeting the criterion, which
    # is how a release gate turns into a formality.
    snapshotted = [c for c in unpinned if c.source_snapshot is not None]

    datasets = [DEFAULT_REGISTRY.get(name) for name in DEFAULT_REGISTRY.names]
    ds_pinned = [d for d in datasets if getattr(d, "sha256", None)]
    # The same split the cards get, for the same reason. Without it the report stated a
    # dataset count and then accounted for none of it, so a reader could not tell the
    # unpinned five from forgotten work — which is the one distinction this report
    # exists to draw.
    ds_unpinned = [d for d in datasets if not getattr(d, "sha256", None)]
    ds_named = [(d, getattr(d, "source_url", None) or "") for d in ds_unpinned]
    ds_fetchable = [
        d for d, u in ds_named if _names_an_artifact(u) and not _names_a_moving_target(u)
    ]
    ds_moving = [d for d, u in ds_named if _names_an_artifact(u) and _names_a_moving_target(u)]
    ds_referenced = [d for d, u in ds_named if not _names_an_artifact(u)]
    # Applied to the *pinned* descriptors too, which it never was. A hash beside a moving
    # address is a pin with an expiry date: the next upstream release invalidates it and
    # the consent gate then refuses a dataset that loaded yesterday. `dbsnp` showed the
    # cheaper version of the same defect while unpinned — `latest_release` had moved to
    # b157 while the descriptor still declared b156, so a run would have fetched one
    # build and recorded another. Both addresses are now archived or commit-pinned, so
    # this reports zero; it is here to keep it that way.
    ds_drifting = [
        d
        for d in datasets
        if getattr(d, "sha256", None)
        and not getattr(d, "bundled", False)
        and _names_a_moving_target(getattr(d, "source_url", None) or "")
    ]

    # What needs somebody to decide *which file*: the cards that name a page, plus the
    # datasets that name a portal, plus the ones that name a file at a floating address.
    # Counting only the cards understated this by the whole dataset side.
    undecided = len(referenced) + len(ds_referenced) + len(ds_moving)

    met = len(pinned) == len(downloadable) and len(ds_pinned) == len(datasets)
    return Criterion(
        track="R0",
        summary="every shipped card/descriptor pins a verified artifact hash",
        met=met,
        detail=(
            f"{len(pinned)}/{len(downloadable)} model cards with a source URL pin a "
            f"checkpoint hash; {len(ds_pinned)}/{len(datasets)} datasets pin one"
        ),
        blocked_by=(
            ""
            if met
            else (
                "requires freezing the published upstream artifacts — and for "
                f"{undecided} of them, first deciding which file that is"
                + (
                    f" ({len(snapshotted)} now pin an upstream revision instead, which "
                    "makes the load reproducible but is not a hash this project verified)"
                    if snapshotted
                    else ""
                )
            )
        ),
        evidence=[
            f"{len(baselines)} card(s) are heuristic baselines with no artifact to pin: "
            + ", ".join(sorted(c.name for c in baselines)),
            f"{len(fetchable)} unpinned card(s) name a downloadable artifact, so a "
            "fetch-and-hash would pin them"
            + (": " + ", ".join(sorted(c.name for c in fetchable)) if fetchable else ""),
            f"{len(snapshotted)} card(s) pin an immutable upstream revision "
            "(`source_snapshot`) because their loader consumes a snapshot or a checkout "
            "rather than one file — reproducible, but the blob digests are the hub "
            "client's to check, so they do not count toward this criterion"
            + (": " + ", ".join(sorted(c.name for c in snapshotted)) if snapshotted else ""),
            f"{len(referenced)} unpinned card(s) name a repository or model page with no "
            "snapshot pin either, and hashing a landing page would report this criterion "
            "met while pinning an HTML document. (Not 'nothing to hash': Hugging Face does "
            "publish a digest per blob at a revision. The obstacle is that these loaders "
            "consume a set of files, so one blob's hash would leave the rest unpinned — "
            "see specs/r0-artifact-pinning.md)"
            + (": " + ", ".join(sorted(c.name for c in referenced)) if referenced else ""),
            f"{len(ds_drifting)} pinned dataset(s) name an address upstream can replace, "
            "so their hash expires at the next upstream release and the consent gate then "
            "refuses a dataset that used to load"
            + (": " + ", ".join(sorted(d.name for d in ds_drifting)) if ds_drifting else ""),
            f"{len(ds_fetchable)} unpinned dataset(s) name a fixed single artifact, so a "
            "fetch-and-hash would pin them"
            + (": " + ", ".join(sorted(d.name for d in ds_fetchable)) if ds_fetchable else ""),
            f"{len(ds_moving)} unpinned dataset(s) name a file at a moving path, so the "
            "hash would be of whatever that address meant on the day it was taken and the "
            "next upstream release would invalidate it — the consent gate would then refuse "
            "the dataset, so a versioned URL has to be found first"
            + (": " + ", ".join(sorted(d.name for d in ds_moving)) if ds_moving else ""),
            f"{len(ds_referenced)} unpinned dataset(s) name a portal or a directory, not a "
            "single artifact, so there is nothing there to hash"
            + (": " + ", ".join(sorted(d.name for d in ds_referenced)) if ds_referenced else ""),
            "the consent gate refuses a null-hash fetch, so an unpinned artifact "
            "cannot be loaded rather than being loaded unverified",
        ],
    )


def _real_corpora() -> Criterion:
    """R1 + R5: scorers reproduce published numbers on real data."""
    from alleleforge.benchmark.datasets import available_datasets, load_dataset

    loaded = [load_dataset(name) for name in sorted(available_datasets())]
    real = [d for d in loaded if not d.synthetic]
    met = bool(real) and len(real) == len(loaded)
    return Criterion(
        track="R1+R5",
        summary="scorers load real weights and reproduce published numbers",
        met=met,
        detail=f"{len(real)}/{len(loaded)} benchmark datasets are real corpora",
        blocked_by="" if met else "the bundled corpora are synthetic stand-ins",
        evidence=[
            "synthetic: " + ", ".join(sorted(d.name for d in loaded if d.synthetic)),
            "every result over a synthetic dataset is labelled as such in its "
            "scientific body, so a real run cannot be confused with one of these",
        ],
    )


def _native_kernels() -> Criterion:
    """R2: the native kernels are on their hot paths, with parity tests."""
    from alleleforge import _native

    available = _native.NATIVE_AVAILABLE
    # Importable is not the same as current. An extension built before a kernel was
    # added imports fine, reports the same version (the crate version is single-sourced
    # from the package version and does not change between builds), and makes that
    # kernel's parity module skip every test in it — while this report counted the
    # module as evidence and called the extension "importable". That is the third time
    # this criterion has had to stop grading itself generously; the first two are in the
    # comments below.
    stale = sorted(_native.missing_native_functions())
    # The `native` *marker*, not the substring: grepping for "native" catches every
    # test whose prose happens to contain the word ("alternative", "natively") and
    # would have reported 16 parity modules where there are five. A readiness report
    # that overstates its own evidence is worse than no readiness report.
    parity = sorted(
        p.name
        for p in (_ROOT / "tests").rglob("test_*.py")
        if "pytest.mark.native" in p.read_text()
    )
    # The criterion has two halves — "with parity tests **and a recorded speedup**" —
    # and the first version of this checked only the first, so it reported MET on half
    # the evidence. A readiness report that grades itself generously is the failure
    # mode it exists to prevent.
    harness = _ROOT / "scripts" / "native_speedup.py"
    recorded = _has_native_speedup_record(_ROOT)
    return Criterion(
        track="R2",
        summary="native kernels on their hot paths with parity tests and a recorded speedup",
        met=bool(parity) and recorded,
        detail=(
            f"{len(parity)} test module(s) exercise the native path; "
            f"speedup harness {'present and cited in the README' if recorded else 'missing'}; "
            "the compiled extension is "
            + (
                f"stale here (no {', '.join(stale)}), so those parity tests skip"
                if stale
                else "importable and current here"
                if available
                else "not built here"
            )
        ),
        blocked_by="" if (parity and recorded) else "no recorded speedup",
        evidence=[
            "parity modules: " + ", ".join(parity),
            f"speedup harness: {harness.relative_to(_ROOT)}",
            *(
                [
                    "a stale build silently withdraws the parity tests that prove the "
                    "kernel matches the Python fallback: rebuild with `maturin develop`"
                ]
                if stale
                else []
            ),
            "the extension is optional at runtime: the Python fallback is pinned "
            "byte-identical, so an unbuilt kernel changes speed and not results",
        ],
    )


def _has_native_speedup_record(root: Path) -> bool:
    """Return whether the README records reproducible results for all 3 R2 kernels.

    Merely naming the harness is not a recorded speedup. The release criterion needs
    a link a reader can rerun, plus one measured ratio for each kernel the criterion
    names. Ratios below 1 are valid evidence: a measured regression is still a result,
    and is the reason the FM-index and k-mer prefilter remain opt-in.
    """
    harness = root / "scripts" / "native_speedup.py"
    readme = root / "README.md"
    if not harness.is_file() or not readme.is_file():
        return False
    _before, heading, tail = readme.read_text().partition("## Native acceleration")
    if not heading:
        return False
    section = tail.partition("\n## ")[0]
    if "[benchmark harness](scripts/native_speedup.py)" not in section:
        return False
    for kernel in ("bwt", "kmer", "haplotype"):
        row = next((line for line in section.splitlines() if f"| `{kernel}` |" in line), "")
        if not re.search(r"\b\d+(?:\.\d+)?x\b", row):
            return False
    return True


def _calibration_on_real_data() -> Criterion:
    """R5: ECE measured on real data, generalization gap documented."""
    from alleleforge.benchmark.datasets import available_datasets, load_dataset

    synthetic = [n for n in sorted(available_datasets()) if load_dataset(n).synthetic]
    study = _ROOT / "scripts" / "calibration_study.py"
    return Criterion(
        track="R5",
        summary="calibration measured on real data; generalization gap documented",
        met=not synthetic,
        detail=(
            "the calibration study runs end to end and reports ECE, the "
            "cross-cell-type gap, and conformal recalibration — over synthetic inputs"
            if synthetic
            else "measured on real corpora"
        ),
        blocked_by="the bundled corpora are synthetic stand-ins" if synthetic else "",
        evidence=[
            f"machinery present: {study.relative_to(_ROOT)}",
            "the generated report states that its numbers are SYNTHETIC and are not "
            "measurements of any model",
        ],
    )


def _preprint_and_doi() -> Criterion:
    """R5 + R0: the methods preprint is posted and the Zenodo DOI minted."""
    preprint = _ROOT / "docs" / "paper" / "preprint.md"
    citation = (_ROOT / "CITATION.cff").read_text() if (_ROOT / "CITATION.cff").is_file() else ""
    has_doi = "doi:" in citation.lower()
    return Criterion(
        track="R5+R0",
        summary="methods preprint posted and Zenodo DOI minted",
        met=preprint.is_file() and has_doi,
        detail=(
            f"draft {'present' if preprint.is_file() else 'missing'}; "
            f"DOI {'recorded' if has_doi else 'not recorded in CITATION.cff'}"
        ),
        blocked_by="" if has_doi else "the DOI is minted on the first tagged release",
        evidence=["accuracy-vs-published numbers in the draft are marked [pending R1]"],
    )


def criteria() -> list[Criterion]:
    """Return every v1.0 criterion with its current, mechanically-derived status."""
    return [
        _artifact_pinning(),
        _real_corpora(),
        _native_kernels(),
        _calibration_on_real_data(),
        _preprint_and_doi(),
    ]


def _render(items: list[Criterion]) -> str:
    # The track labels below are the R6 *criteria*, which are narrower than the
    # roadmap phases of the same names: `[MET ] R2` says the v1.0 condition about
    # native kernels holds, not that SPEC_V2's R2 phase is finished — that phase has
    # its own deliverable list and the README shows it in progress. Two documents
    # printing "R2" with different verdicts is a contradiction a reader has to be told
    # is not one.
    lines = [
        "v1.0 release readiness (SPEC_V2.md, R6)",
        "these are the R6 release criteria, not the roadmap phase statuses they are "
        "named after — a phase can be in progress while its v1.0 criterion is met",
        "",
    ]
    for c in items:
        mark = "MET " if c.met else "open"
        lines.append(f"[{mark}] {c.track:6} {c.summary}")
        lines.append(f"         {c.detail}")
        if c.blocked_by:
            lines.append(f"         blocked: {c.blocked_by}")
        for line in c.evidence:
            lines.append(f"         · {line}")
        lines.append("")
    met = sum(1 for c in items if c.met)
    lines.append(f"{met}/{len(items)} criteria met.")
    if met < len(items):
        lines.append(
            "Every open criterion above is blocked on something outside this "
            "repository. The public release stays v0.1.0."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the readiness report; exit non-zero while any criterion is unmet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    items = criteria()
    if args.json:
        print(json.dumps([c.__dict__ for c in items], indent=2))
    else:
        print(_render(items))
    return 0 if all(c.met for c in items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
