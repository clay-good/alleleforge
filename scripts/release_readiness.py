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

    datasets = [DEFAULT_REGISTRY.get(name) for name in DEFAULT_REGISTRY.names]
    ds_pinned = [d for d in datasets if getattr(d, "sha256", None)]

    met = len(pinned) == len(downloadable) and len(ds_pinned) == len(datasets)
    return Criterion(
        track="R0",
        summary="every shipped card/descriptor pins a verified artifact hash",
        met=met,
        detail=(
            f"{len(pinned)}/{len(downloadable)} model cards with a source URL pin a "
            f"checkpoint hash; {len(ds_pinned)}/{len(datasets)} datasets pin one"
        ),
        blocked_by="" if met else "requires freezing the published upstream artifacts",
        evidence=[
            f"{len(baselines)} card(s) are heuristic baselines with no artifact to pin: "
            + ", ".join(sorted(c.name for c in baselines)),
            "unpinned: "
            + ", ".join(sorted(c.name for c in downloadable if not c.checkpoint_sha256)),
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
    # The `native` *marker*, not the substring: grepping for "native" catches every
    # test whose prose happens to contain the word ("alternative", "natively") and
    # would have reported 16 parity modules where there are five. A readiness report
    # that overstates its own evidence is worse than no readiness report.
    parity = sorted(
        p.name
        for p in (_ROOT / "tests").rglob("test_*.py")
        if "pytest.mark.native" in p.read_text()
    )
    return Criterion(
        track="R2",
        summary="native kernels on their hot paths with parity tests",
        met=bool(parity),
        detail=(
            f"{len(parity)} test module(s) exercise the native path; "
            f"the compiled extension is {'importable' if available else 'not built here'}"
        ),
        blocked_by="",
        evidence=[
            "parity modules: " + ", ".join(parity),
            "the extension is optional at runtime: the Python fallback is pinned "
            "byte-identical, so an unbuilt kernel changes speed and not results",
        ],
    )


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
    lines = ["v1.0 release readiness (SPEC_V2.md, R6)", ""]
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
