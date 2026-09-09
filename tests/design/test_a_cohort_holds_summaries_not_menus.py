"""The bounded-memory guarantee is a claim about what a finished run still points at.

`design_many`'s module docstring opens with it: "only the per-item working set is ever
held: each ranked menu is summarized (and optionally written to disk) and then released,
so peak memory does not grow with the cohort size". That is why `aforge batch` can be
pointed at a whole VCF, and it is the reason `CohortItemResult` says "never the full menu"
in its own first line.

Peak memory is not testable here — it is a property of a run on a machine, and this repo's
own notes say cross-run measurements are not baselines. What *is* exact is the premise the
claim rests on: **no ranked menu, candidate or off-target report is reachable from a
finished `CohortRunReport`.** Retaining one is the single change that would falsify the
guarantee, it is the change someone would make for a good reason ("keep the menu, the TSV
needs the sites"), and it would be invisible until a 300-variant run on a real genome.

Measured for scale: a per-item summary is ~540 bytes of JSON, so a 300-variant cohort
retains around 160 KiB of results. A retained menu is 1.25 MiB *each*.
"""

from __future__ import annotations

import json
import random
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.offtarget import OffTargetReport

#: What a cohort must not still be holding when it finishes.
_HEAVY = (RankedMenu, DesignCandidate, OffTargetReport)


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(37)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(20_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _variants(reference: ReferenceGenome) -> list[str]:
    bases = "".join(Path(reference.path).read_text().split("\n")[1:])
    out = []
    for position in (5_000, 10_000, 15_000):
        base = bases[position - 1]
        out.append(f"chr1:{position}:{base}>{'A' if base != 'A' else 'G'}")
    return out


def _walk(value: Any, seen: set[int] | None = None) -> list[Any]:
    """Return every object reachable from ``value``, without cycling."""
    seen = seen if seen is not None else set()
    if id(value) in seen:
        return []
    seen.add(id(value))
    found = [value]
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            found += _walk(getattr(value, field.name), seen)
    elif isinstance(value, dict):
        for key, item in value.items():
            found += _walk(key, seen) + _walk(item, seen)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            found += _walk(item, seen)
    elif not isinstance(value, type) and hasattr(type(value), "model_fields"):
        for name in type(value).model_fields:
            found += _walk(getattr(value, name, None), seen)
    return found


def test_a_finished_cohort_points_at_no_menu(reference: ReferenceGenome) -> None:
    report = design_many(_variants(reference), reference=reference, max_candidates_per_chemistry=2)
    assert report.succeeded, "the fixture designed nothing; this check would be vacuous"

    retained = [obj for obj in _walk(report) if isinstance(obj, _HEAVY)]
    assert not retained, (
        f"a finished cohort still points at {[type(o).__name__ for o in retained][:5]}. "
        "The module's bounded-memory guarantee — 'each ranked menu is summarized and then "
        "released' — is false the moment one is kept, and a 300-variant run is where "
        "anyone would notice."
    )


def test_the_walker_would_notice_one(reference: ReferenceGenome) -> None:
    """Guard the guard: a traversal that finds nothing proves nothing."""
    from alleleforge.design.designer import design
    from alleleforge.variant.resolver import resolve

    menu = design(
        resolve(_variants(reference)[0], reference=reference),
        reference=reference,
        run_offtarget=False,
        max_candidates_per_chemistry=1,
    )
    report = design_many(_variants(reference), reference=reference, max_candidates_per_chemistry=2)
    smuggled = report.items[0]
    object.__setattr__(smuggled, "summary", {**(smuggled.summary or {}), "menu": menu})
    assert [obj for obj in _walk(report) if isinstance(obj, _HEAVY)], "the walker is blind"


def test_a_summary_is_plain_data(reference: ReferenceGenome) -> None:
    """It has to survive a JSONL manifest line, which is the other half of the design."""
    report = design_many(_variants(reference), reference=reference, max_candidates_per_chemistry=2)
    for item in report.items:
        if item.summary is None:
            continue
        rendered = json.dumps(item.summary)
        # ~540 bytes per item is what makes a 300-variant cohort ~160 KiB of results;
        # a retained menu would be 1.25 MiB each.
        assert len(rendered) < 8_192, (item.item_id, len(rendered))
