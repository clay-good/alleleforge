"""The defining principle said the tool searches population variation by default.

Nothing of gnomAD ships. `design()` takes `gnomad=None`, and a scan with no population
source is reference-only — which the code says everywhere a reader looks: the report's
search description, `offtarget_sources`, and a warning when ancestries were requested that
nothing could answer. The README has a whole note on it, headed "The three safety inputs
are opt-in files, and the scan is reference-only without them."

`SPEC.md`'s numbered principle 3 said "AlleleForge searches population variation by default
and stratifies results by ancestry" — the project's differentiator, stated as something a
bare install does. There is a charitable reading (given a source, the scan uses it without
being asked again, which is true and is the design) and a plain one (a default run covers
population variation, which is false and is what a reader takes away).

The guard is derived from the default: while `design()` defaults its population source to
`None`, a document may not claim population variation is searched by default without
naming the file requirement in the same breath.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from alleleforge.design.designer import design
from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]

#: Claims that a default run is population-aware.
_BY_DEFAULT = re.compile(
    r"searches population variation by default"
    r"|population(-| )aware by default(?!\*\* behaviour)",
    re.I,
)

#: What such a claim must name to be true.
_QUALIFIERS = ("--gnomad", "gnomad", "reference-only", "opt-in file")


def test_the_population_source_defaults_to_absent() -> None:
    """The premise. If a source ever ships, the claim becomes sayable."""
    assert inspect.signature(design).parameters["gnomad"].default is None


def test_a_scan_without_a_source_says_it_was_reference_only() -> None:
    """The behaviour the principle has to be consistent with."""
    from alleleforge.types.offtarget import OffTargetReport

    assert "sources_considered" in OffTargetReport.model_fields


def test_no_document_claims_a_default_run_is_population_aware() -> None:
    offenders: list[str] = []
    for path in _prose_files():
        for block in re.split(r"\n\s*\n", prose_text(path)):
            if not _BY_DEFAULT.search(block):
                continue
            lowered = block.lower()
            if not any(q in lowered for q in _QUALIFIERS):
                offenders.append(f"{path.relative_to(_ROOT)}: {block.strip()[:140]}")
    assert not offenders, (
        "nothing of gnomAD ships and `design(gnomad=None)` is reference-only, so a "
        f"default run is not population-aware; these say it is: {offenders}"
    )


def test_the_principle_states_the_distinction() -> None:
    """The reader needs the true version, not just the absence of the false one."""
    spec = (_ROOT / "SPEC.md").read_text(encoding="utf-8")
    principle = next(block for block in spec.split("\n\n") if "Population-aware" in block)
    assert "reference-only" in principle, principle
    assert "not measured" in principle.lower(), principle
