#!/usr/bin/env python
"""Generate the synthetic CRISPR-Bench dataset fixtures and frozen splits.

Run from the repo root: ``python scripts/make_benchmark_fixtures.py``. The output
is fully deterministic — every value is derived from a SHA-256 of the row id, so
re-running produces byte-identical files and the committed content hashes stay
stable. Splits hold out a whole cell context into the test fold (a cross-context
generalization split) and record the dataset content hash so a frozen split is
invalidated the moment the data changes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from alleleforge.benchmark._canon import content_hash

BENCH = Path("src/alleleforge/benchmark")
FIXTURES = BENCH / "datasets" / "fixtures"
SPLITS = BENCH / "splits"

CONTEXTS = ["K562", "HEK293T", "HepG2"]
HELDOUT = "HepG2"  # the cross-context test fold


def u01(key: str) -> float:
    """Return a deterministic float in [0, 1) from a string key."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def seq(key: str, n: int) -> str:
    """Return a deterministic DNA sequence of length n from a string key."""
    bases = "ACGT"
    out = []
    for i in range(n):
        h = int(hashlib.sha256(f"{key}:{i}".encode()).hexdigest()[:2], 16)
        out.append(bases[h % 4])
    return "".join(out)


def dist(key: str, cats: list[str]) -> dict[str, float]:
    """Return a deterministic normalized distribution over cats."""
    raw = {c: u01(f"{key}:{c}") + 0.05 for c in cats}
    total = sum(raw.values())
    return {c: round(v / total, 6) for c, v in raw.items()}


def context_for(i: int) -> str:
    """Round-robin a cell context for row i."""
    return CONTEXTS[i % len(CONTEXTS)]


def write_dataset(name: str, meta: dict[str, Any], examples: list[dict[str, Any]]) -> None:
    """Write a dataset fixture JSON file."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    payload = {**meta, "name": name, "examples": examples}
    (FIXTURES / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n")


def dataset_content_hash(examples: list[dict[str, Any]]) -> str:
    """Mirror BenchmarkDataset.content_hash over raw example dicts."""
    payload = [
        {"example_id": e["example_id"], "inputs": e["inputs"], "label": e["label"]}
        for e in examples
    ]
    return content_hash(payload)


def write_split(task: str, dataset: str, examples: list[dict[str, Any]], rationale: str) -> None:
    """Write a frozen, content-hashed v1 split with a held-out test fold.

    Rows carrying a ``cell_type`` are split cross-context (the HELDOUT context
    becomes the entire test fold); rows without one (off-target pairs) fall back
    to holding out the trailing third of guides.
    """
    has_context = any("cell_type" in e["inputs"] for e in examples)
    if has_context:
        test = [e["example_id"] for e in examples if e["inputs"].get("cell_type") == HELDOUT]
        rest = [e["example_id"] for e in examples if e["inputs"].get("cell_type") != HELDOUT]
    else:
        cut = (len(examples) * 2) // 3
        rest = [e["example_id"] for e in examples[:cut]]
        test = [e["example_id"] for e in examples[cut:]]
    val = rest[::4]  # every fourth remaining row to validation
    train = [i for i in rest if i not in set(val)]
    binding = {
        "split_version": "v1",
        "task": task,
        "dataset": dataset,
        "dataset_sha256": dataset_content_hash(examples),
        "train": train,
        "val": val,
        "test": test,
    }
    split = {**binding, "rationale": rationale, "split_sha256": content_hash(binding)}
    SPLITS.mkdir(parents=True, exist_ok=True)
    (SPLITS / f"{task}.v1.json").write_text(json.dumps(split, indent=2) + "\n")


def build_regression(name: str, chem: str, n: int, length: int) -> list[dict[str, Any]]:
    """Build a regression dataset of (context -> efficiency) rows."""
    rows = []
    for i in range(n):
        eid = f"{name}-{i:03d}"
        rows.append(
            {
                "example_id": eid,
                "inputs": {"context": seq(eid, length), "cell_type": context_for(i)},
                "label": round(u01(eid), 6),
            }
        )
    return rows


def build_distribution(name: str, cats: list[str], n: int, length: int) -> list[dict[str, Any]]:
    """Build a distribution dataset of (context -> outcome frequencies) rows."""
    rows = []
    for i in range(n):
        eid = f"{name}-{i:03d}"
        rows.append(
            {
                "example_id": eid,
                "inputs": {"context": seq(eid, length), "cell_type": context_for(i)},
                "label": dist(eid, cats),
            }
        )
    return rows


def build_offtarget(name: str, n: int) -> list[dict[str, Any]]:
    """Build a classification dataset of (on/off pair -> 0/1) rows."""
    rows = []
    for i in range(n):
        eid = f"{name}-{i:03d}"
        on = seq(f"{eid}:on", 20)
        mm = int(u01(f"{eid}:mm") * 6)  # 0..5 mismatches
        off = list(on)
        for j in range(mm):
            pos = int(u01(f"{eid}:pos:{j}") * 20)
            off[pos] = "ACGT"[(("ACGT".index(off[pos])) + 1) % 4]
        # bona-fide off-targets cluster at low mismatch counts
        label = 1 if u01(f"{eid}:label") > (mm / 6.0) else 0
        rows.append(
            {
                "example_id": eid,
                "inputs": {"pair": {"on": on, "off": "".join(off), "mismatches": mm}},
                "label": label,
            }
        )
    return rows


def main() -> None:
    """Generate every fixture and split."""
    datasets = {
        "rs3-validation": (
            {
                "version": "synthetic-v1",
                "license": "CC-BY-4.0",
                "citation": "DeWeirdt & Doench, Nat Commun 2022 (Rule Set 3) — synthetic stand-in",
                "source_url": "https://github.com/gpp-rnd/rs3",
                "redistributable": False,
                "synthetic": True,
            },
            "cas9-efficiency",
            build_regression("rs3", "cas9_nuclease", 30, 23),
            "Cross-cell-type: the HepG2 context is held out entirely into test.",
        ),
        "forecast-outcomes": (
            {
                "version": "synthetic-v1",
                "license": "CC-BY-4.0",
                "citation": "Allen et al., Nat Biotechnol 2019 (FORECasT) — synthetic stand-in",
                "source_url": "https://partslab.sanger.ac.uk/FORECasT",
                "redistributable": False,
                "synthetic": True,
            },
            "cas9-outcome",
            build_distribution(
                "forecast",
                ["ins_1bp", "del_1bp", "del_2bp", "del_large", "unmodified"],
                24,
                40,
            ),
            "Cross-cell-type: HepG2 outcomes are held out into test.",
        ),
        "be-hive-outcomes": (
            {
                "version": "synthetic-v1",
                "license": "CC-BY-4.0",
                "citation": "Arbab et al., Cell 2020 (BE-Hive) — synthetic stand-in",
                "source_url": "https://www.crisprbehive.design",
                "redistributable": False,
                "synthetic": True,
            },
            "be-outcome",
            build_distribution(
                "behive",
                ["C_to_T_p5", "C_to_T_p6", "C_to_G", "C_to_A", "unedited"],
                24,
                40,
            ),
            "Cross-cell-type: HepG2 base-edit outcomes are held out into test.",
        ),
        "pridict2-library": (
            {
                "version": "synthetic-v1",
                "license": "CC-BY-4.0",
                "citation": "Mathis et al., Nat Biotechnol 2023 (PRIDICT2) — synthetic stand-in",
                "source_url": "https://www.pridict.it",
                "redistributable": False,
                "synthetic": True,
            },
            "pe-efficiency",
            build_regression("pridict2", "prime", 24, 30),
            "Cross-cell-type: HepG2 pegRNAs are held out into test.",
        ),
        "guideseq-offtarget": (
            {
                "version": "synthetic-v1",
                "license": "CC-BY-4.0",
                "citation": "Tsai et al., Nat Biotechnol 2015 (GUIDE-seq) — synthetic stand-in",
                "source_url": "https://github.com/tsailabSJ/guideseq",
                "redistributable": False,
                "synthetic": True,
            },
            "offtarget-classification",
            build_offtarget("guideseq", 36),
            "Held-out guides: the last third of guides form the test fold.",
        ),
    }

    for name, (meta, task, rows, rationale) in datasets.items():
        write_dataset(name, meta, rows)
        write_split(task, name, rows, rationale)
        print(f"wrote {name}: {len(rows)} examples")


if __name__ == "__main__":
    main()
