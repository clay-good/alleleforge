#!/usr/bin/env python
"""Reproducibility audit: re-derive a canonical design run and diff it (R0).

The honesty contract is that an AlleleForge run is **reproducible from config +
seed**. This script makes that auditable: it re-derives a fixed, weight-free
design menu (a ClinVar accession -> full ranked menu, the §16.1 acceptance
scenario) twice, asserts the two runs are byte-identical (determinism), and
diffs a canonicalized digest of the *scientific* result against a committed
golden manifest.

Volatile, environment-specific provenance (the package version and the config
snapshot's cache paths) is stripped before hashing, and floats are rounded so a
last-ULP difference across platforms is not a spurious failure; everything that
defines the result — candidates, scores, intervals, outcomes, off-targets — is
kept.

The golden manifest stores the canonical body alongside its digest, so a drift is a
readable diff in review and the gate can name the values that moved instead of
printing two hashes and leaving the bisection to a human.

Usage:
    python scripts/reproduce.py            # diff against the golden; exit 1 on drift
    python scripts/reproduce.py --update    # regenerate the golden manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alleleforge.data.clinvar import (
    ClinicalSignificance,
    ClinVarDB,
    ClinVarRecord,
)
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import ClinVarAccession, Variant

#: Where the golden manifest lives (next to this script).
GOLDEN = Path(__file__).with_name("reproduce_golden.json")

#: Fixed run timestamp so provenance is stable across runs.
FIXED_TS = datetime(2024, 5, 1, tzinfo=UTC)

#: The canonical scenario: a 20-nt ABE-correctable protospacer + NGG PAM, padded.
_PAD = "T" * 20
_ABE_PROTO = "TTTAAACGTTTTTTTTTTTT"

#: Provenance keys whose value is environment-specific, not part of the result.
_VOLATILE_KEYS = frozenset({"alleleforge_version", "config_snapshot"})

#: Decimal places floats are rounded to before hashing (cross-platform tolerance).
_FLOAT_PRECISION = 6


def _canonicalize(obj: Any) -> Any:
    """Strip volatile provenance keys and round floats, recursively."""
    if isinstance(obj, dict):
        return {k: _canonicalize(v) for k, v in sorted(obj.items()) if k not in _VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_canonicalize(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, _FLOAT_PRECISION)
    return obj


def _run() -> str:
    """Build the canonical menu and return its serialized JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        fasta = Path(tmp) / "reproduce.fa"
        fasta.write_text(f">chr2\n{_PAD}{_ABE_PROTO}TGG{_PAD}\n")
        reference = ReferenceGenome(fasta, build="hg38")

        pos = 25  # the in-window A to install A->G
        iv = GenomicInterval(chrom="chr2", start=pos, end=pos + 1, strand=Strand.PLUS)
        ref_base = str(reference.fetch(iv))
        accession = ClinVarAccession(value="VCV000012345")
        variant = Variant(
            chrom="chr2", pos=pos, ref=ref_base, alt="G", build="hg38", clinvar=accession
        )
        clinvar = ClinVarDB(
            [
                ClinVarRecord(
                    variant=variant,
                    accession=accession,
                    significance=ClinicalSignificance.PATHOGENIC,
                    gene="DEMO",
                )
            ]
        )
        menu = design(
            accession,
            reference=reference,
            intent=EditIntent.INSTALL,
            clinvar=clinvar,
            timestamp=FIXED_TS,
        )
        return menu.model_dump_json()


def _digest() -> tuple[str, dict[str, Any]]:
    """Run twice (asserting determinism) and return the digest + canonical body."""
    first = _run()
    second = _run()
    if first != second:
        raise SystemExit("non-deterministic: two identical-config runs differed")
    body = _canonicalize(json.loads(first))
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest(), body


def _changed_paths(golden: Any, current: Any, prefix: str = "") -> list[str]:
    """Return dotted paths where ``current`` differs from ``golden``, deepest-first.

    A blocking gate that fails with two 64-character hashes and nothing else leaves a
    developer to bisect by hand for a drift the script already has both sides of. This
    walks the two canonical bodies together and names the leaves that moved.
    """
    if isinstance(golden, dict) and isinstance(current, dict):
        out: list[str] = []
        for key in sorted(set(golden) | set(current)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in golden:
                out.append(f"{path}: added ({current[key]!r})")
            elif key not in current:
                out.append(f"{path}: removed (was {golden[key]!r})")
            else:
                out += _changed_paths(golden[key], current[key], path)
        return out
    if isinstance(golden, list) and isinstance(current, list):
        if len(golden) != len(current):
            return [f"{prefix}: length {len(golden)} -> {len(current)}"]
        return [
            p
            for i, (g, c) in enumerate(zip(golden, current, strict=True))
            for p in _changed_paths(g, c, f"{prefix}[{i}]")
        ]
    if golden != current:
        return [f"{prefix}: {golden!r} -> {current!r}"]
    return []


#: How many changed leaves a drift report prints before truncating. A wholesale
#: change (a renamed field, a new default) moves hundreds; the first few identify it.
_MAX_REPORTED_CHANGES = 25


def main(argv: list[str] | None = None) -> int:
    """Diff (or update) the golden reproducibility manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="regenerate the golden manifest")
    args = parser.parse_args(argv)

    digest, body = _digest()
    n_candidates = len(body.get("candidates", []))

    if args.update:
        GOLDEN.write_text(
            json.dumps(
                {"sha256": digest, "n_candidates": n_candidates, "body": body},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        print(f"updated {GOLDEN.name}: sha256={digest} ({n_candidates} candidates)")
        return 0

    if not GOLDEN.exists():
        raise SystemExit(f"no golden manifest at {GOLDEN}; run with --update to create it")
    golden = json.loads(GOLDEN.read_text())
    if golden["sha256"] != digest:
        print("REPRODUCIBILITY DRIFT", file=sys.stderr)
        print(f"  golden : {golden['sha256']}", file=sys.stderr)
        print(f"  current: {digest}", file=sys.stderr)
        changes = _changed_paths(golden.get("body", {}), body) if "body" in golden else []
        if changes:
            print(f"  {len(changes)} changed value(s):", file=sys.stderr)
            for line in changes[:_MAX_REPORTED_CHANGES]:
                print(f"    {line}", file=sys.stderr)
            if len(changes) > _MAX_REPORTED_CHANGES:
                print(
                    f"    … and {len(changes) - _MAX_REPORTED_CHANGES} more",
                    file=sys.stderr,
                )
        else:
            print(
                "  (the golden manifest predates the stored body; run --update to "
                "record it, so the next drift can name what moved)",
                file=sys.stderr,
            )
        return 1
    print(f"reproduced: sha256={digest} ({n_candidates} candidates) matches golden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
